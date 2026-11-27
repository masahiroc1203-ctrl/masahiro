using System.Text;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Rfcomm;
using Windows.Devices.Enumeration;
using Windows.Networking.Sockets;
using Windows.Storage.Streams;

namespace BtNotifySender;

public enum LinkState { Searching, Waiting, Connected, Error }

/// <summary>
/// Android アプリ (RFCOMM サーバー) へ接続し、通知を 1 行 1 JSON で送る。
/// - 切れたら 5 秒から倍々 (最大 30 秒) で再接続する
/// - 30 秒ごとに ping を送り、pong が 75 秒返らなければ切れたとみなす
/// - 未接続のあいだの通知は最大 50 件・15 分まで保留し、つながったら送る
/// </summary>
public sealed class BluetoothClient : IDisposable
{
    private static readonly TimeSpan PingInterval = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan PongTimeout = TimeSpan.FromSeconds(75);
    private static readonly TimeSpan PendingMaxAge = TimeSpan.FromMinutes(15);
    private const int PendingMax = 50;
    private const int MinBackoffSeconds = 5;
    private const int MaxBackoffSeconds = 30;

    private readonly string _targetDeviceName;
    private readonly CancellationTokenSource _cts = new();
    private readonly SemaphoreSlim _sendLock = new(1, 1);
    private readonly object _stateLock = new();
    private readonly Queue<(string Line, DateTimeOffset QueuedAt)> _pending = new();

    private BluetoothDevice? _device;
    private StreamSocket? _socket;
    private DataWriter? _writer;
    private int _generation;
    private volatile bool _connected;
    private long _lastPongUtcTicks;
    private int _backoffSeconds = MinBackoffSeconds;
    private TaskCompletionSource _wake = NewWake();

    public event Action<LinkState, string>? StatusChanged;
    public bool IsConnected => _connected;
    public string ConnectedDeviceName { get; private set; } = "";

    public BluetoothClient(string targetDeviceName)
    {
        _targetDeviceName = targetDeviceName.Trim();
    }

    public void Start()
    {
        _ = Task.Run(() => ConnectionLoopAsync(_cts.Token));
        _ = Task.Run(() => KeepAliveLoopAsync(_cts.Token));
    }

    /// <summary>通知を送る。未接続なら保留して false を返す (つながったら自動で送る)</summary>
    public async Task<bool> SendNotificationAsync(string id, string appName, string title, string body)
    {
        string line = Protocol.NotificationLine(id, appName, title, body, DateTimeOffset.UtcNow);
        if (await TrySendLineAsync(line)) return true;

        lock (_pending)
        {
            _pending.Enqueue((line, DateTimeOffset.UtcNow));
            while (_pending.Count > PendingMax) _pending.Dequeue();
        }
        return false;
    }

    public int PendingCount
    {
        get { lock (_pending) return _pending.Count; }
    }

    /// <summary>待ち時間を飛ばして今すぐ接続し直す (スリープ復帰時やメニューから)</summary>
    public void ReconnectNow(string reason)
    {
        int gen;
        lock (_stateLock) gen = _generation;
        Disconnect(gen, reason);
        _backoffSeconds = MinBackoffSeconds;
        Interlocked.Exchange(ref _wake, NewWake()).TrySetResult();
    }

    private static TaskCompletionSource NewWake() => new(TaskCreationOptions.RunContinuationsAsynchronously);

    private async Task WaitAsync(TimeSpan delay, CancellationToken token)
    {
        var wake = Volatile.Read(ref _wake).Task;
        await Task.WhenAny(Task.Delay(delay, token), wake);
        token.ThrowIfCancellationRequested();
    }

    private async Task BackoffAsync(CancellationToken token)
    {
        await WaitAsync(TimeSpan.FromSeconds(_backoffSeconds), token);
        _backoffSeconds = Math.Min(_backoffSeconds * 2, MaxBackoffSeconds);
    }

    private void Report(LinkState state, string message) => StatusChanged?.Invoke(state, message);

    private async Task ConnectionLoopAsync(CancellationToken token)
    {
        try
        {
            while (!token.IsCancellationRequested)
            {
                if (_connected)
                {
                    await WaitAsync(TimeSpan.FromSeconds(2), token);
                    continue;
                }

                if (_targetDeviceName.Length == 0)
                {
                    Report(LinkState.Error, "config.json の target_device_name が空です");
                    await WaitAsync(TimeSpan.FromSeconds(MaxBackoffSeconds), token);
                    continue;
                }

                BluetoothDevice? device = null;
                StreamSocket? socket = null;
                try
                {
                    Report(LinkState.Searching, $"検索中: {_targetDeviceName}");
                    var paired = await DeviceInformation.FindAllAsync(BluetoothDevice.GetDeviceSelectorFromPairingState(true));
                    var target = paired.FirstOrDefault(d => d.Name.Contains(_targetDeviceName, StringComparison.OrdinalIgnoreCase));
                    if (target is null)
                    {
                        var names = string.Join(", ", paired.Select(d => d.Name).Take(5));
                        Report(LinkState.Error, $"ペアリング済みに「{_targetDeviceName}」なし ({names})");
                        await BackoffAsync(token);
                        continue;
                    }

                    device = await BluetoothDevice.FromIdAsync(target.Id);
                    if (device is null)
                    {
                        Report(LinkState.Error, $"{target.Name} を開けません (Bluetooth がオフ?)");
                        await BackoffAsync(token);
                        continue;
                    }

                    var services = await device.GetRfcommServicesForIdAsync(
                        RfcommServiceId.FromUuid(Protocol.ServiceUuid), BluetoothCacheMode.Uncached);
                    var service = services.Services.FirstOrDefault();
                    if (service is null)
                    {
                        string why = services.Error == BluetoothError.Success
                            ? "スマホのアプリで「サービス開始」を押してください"
                            : $"スマホに届きません ({services.Error})";
                        Report(LinkState.Waiting, $"{target.Name}: {why}");
                        device.Dispose();
                        device = null;
                        await BackoffAsync(token);
                        continue;
                    }

                    socket = new StreamSocket();
                    await socket.ConnectAsync(service.ConnectionHostName, service.ConnectionServiceName);

                    int gen;
                    var input = socket.InputStream;
                    lock (_stateLock)
                    {
                        gen = ++_generation;
                        _device = device;
                        _socket = socket;
                        _writer = new DataWriter(socket.OutputStream) { UnicodeEncoding = Windows.Storage.Streams.UnicodeEncoding.Utf8 };
                        Interlocked.Exchange(ref _lastPongUtcTicks, DateTime.UtcNow.Ticks);
                        _connected = true;
                    }
                    device = null;
                    socket = null; // 以降は Disconnect() が破棄する

                    ConnectedDeviceName = target.Name;
                    _backoffSeconds = MinBackoffSeconds;
                    Report(LinkState.Connected, $"接続中: {target.Name}");

                    _ = Task.Run(() => ReadLoopAsync(input, gen, token));
                    await FlushPendingAsync();
                }
                catch (OperationCanceledException) when (token.IsCancellationRequested)
                {
                    throw;
                }
                catch (Exception ex)
                {
                    try { socket?.Dispose(); } catch { }
                    try { device?.Dispose(); } catch { }
                    Report(LinkState.Waiting, $"再接続待ち: {ex.Message}".Trim());
                    await BackoffAsync(token);
                }
            }
        }
        catch (OperationCanceledException)
        {
            // 終了
        }
    }

    /// <summary>Android からの pong (や ping) を読む。読まないと相手の送信が詰まる</summary>
    private async Task ReadLoopAsync(IInputStream input, int gen, CancellationToken token)
    {
        var decoder = Encoding.UTF8.GetDecoder();
        var text = new StringBuilder();
        var bytes = new byte[512];
        var chars = new char[Encoding.UTF8.GetMaxCharCount(bytes.Length)];
        string reason = "スマホ側で切断されました";

        try
        {
            using var reader = new DataReader(input) { InputStreamOptions = InputStreamOptions.Partial };
            while (!token.IsCancellationRequested && IsCurrent(gen))
            {
                uint n = await reader.LoadAsync((uint)bytes.Length).AsTask(token);
                if (n == 0) break;

                var chunk = n == bytes.Length ? bytes : new byte[n];
                reader.ReadBytes(chunk);
                int charCount = decoder.GetChars(chunk, 0, (int)n, chars, 0);
                text.Append(chars, 0, charCount);

                int newline;
                while ((newline = IndexOf(text, '\n')) >= 0)
                {
                    string line = text.ToString(0, newline).Trim();
                    text.Remove(0, newline + 1);
                    await HandleIncomingAsync(line);
                }
                if (text.Length > 64 * 1024) text.Clear(); // 改行の無いゴミが溜まり続けないように
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            reason = $"受信エラー: {ex.Message}".Trim();
        }
        catch (OperationCanceledException)
        {
            return;
        }

        Disconnect(gen, reason);
    }

    private static int IndexOf(StringBuilder sb, char c)
    {
        for (int i = 0; i < sb.Length; i++) if (sb[i] == c) return i;
        return -1;
    }

    private async Task HandleIncomingAsync(string line)
    {
        switch (Protocol.MessageType(line))
        {
            case "pong":
                Interlocked.Exchange(ref _lastPongUtcTicks, DateTime.UtcNow.Ticks);
                break;
            case "ping":
                Interlocked.Exchange(ref _lastPongUtcTicks, DateTime.UtcNow.Ticks);
                await TrySendLineAsync(Protocol.PongLine(DateTimeOffset.UtcNow));
                break;
        }
    }

    private async Task KeepAliveLoopAsync(CancellationToken token)
    {
        try
        {
            while (!token.IsCancellationRequested)
            {
                await Task.Delay(PingInterval, token);
                if (!_connected) continue;

                int gen;
                lock (_stateLock) gen = _generation;
                var sincePong = DateTime.UtcNow - new DateTime(Interlocked.Read(ref _lastPongUtcTicks), DateTimeKind.Utc);
                if (sincePong > PongTimeout)
                {
                    Disconnect(gen, $"スマホから {sincePong.TotalSeconds:0} 秒応答なし");
                    continue;
                }
                await TrySendLineAsync(Protocol.PingLine(DateTimeOffset.UtcNow));
            }
        }
        catch (OperationCanceledException)
        {
            // 終了
        }
    }

    private async Task FlushPendingAsync()
    {
        while (true)
        {
            (string Line, DateTimeOffset QueuedAt) item;
            lock (_pending)
            {
                while (_pending.Count > 0 && DateTimeOffset.UtcNow - _pending.Peek().QueuedAt > PendingMaxAge)
                    _pending.Dequeue();
                if (_pending.Count == 0) return;
                item = _pending.Peek();
            }

            if (!await TrySendLineAsync(item.Line)) return; // 切れたら残りは次の接続で

            lock (_pending)
            {
                if (_pending.Count > 0 && ReferenceEquals(_pending.Peek().Line, item.Line)) _pending.Dequeue();
            }
        }
    }

    private bool IsCurrent(int gen)
    {
        lock (_stateLock) return _connected && gen == _generation;
    }

    private async Task<bool> TrySendLineAsync(string line)
    {
        if (!_connected) return false;

        await _sendLock.WaitAsync();
        int gen;
        DataWriter? writer;
        lock (_stateLock)
        {
            gen = _generation;
            writer = _connected ? _writer : null;
        }

        try
        {
            if (writer is null) return false;
            writer.WriteString(line);
            await writer.StoreAsync();
            return true;
        }
        catch (Exception ex)
        {
            Disconnect(gen, $"送信失敗: {ex.Message}".Trim());
            return false;
        }
        finally
        {
            _sendLock.Release();
        }
    }

    private void Disconnect(int gen, string reason)
    {
        DataWriter? writer;
        StreamSocket? socket;
        BluetoothDevice? device;
        lock (_stateLock)
        {
            if (!_connected || gen != _generation) return;
            _connected = false;
            writer = _writer; socket = _socket; device = _device;
            _writer = null; _socket = null; _device = null;
        }

        try { writer?.DetachStream(); } catch { }
        try { writer?.Dispose(); } catch { }
        try { socket?.Dispose(); } catch { }
        try { device?.Dispose(); } catch { }
        Report(LinkState.Waiting, $"切断 ({reason}) - 再接続します");
    }

    public void Dispose()
    {
        _cts.Cancel();
        int gen;
        lock (_stateLock) gen = _generation;
        Disconnect(gen, "終了");
    }
}
