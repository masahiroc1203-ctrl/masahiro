using System.Text;
using System.Text.Json;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Rfcomm;
using Windows.Devices.Enumeration;
using Windows.Networking.Sockets;
using Windows.Storage.Streams;

namespace BtNotifySender;

public class BluetoothClient : IDisposable
{
    private static readonly Guid ServiceUuid = Guid.Parse("8ce255c0-200a-11e0-ac64-0800200c9a66");
    private readonly string _targetDeviceName;
    private readonly CancellationTokenSource _cts = new();
    private StreamSocket? _socket;
    private DataWriter? _writer;
    private readonly SemaphoreSlim _sendLock = new(1, 1);

    public event Action<string>? StatusChanged;
    public bool IsConnected { get; private set; }

    public BluetoothClient(string targetDeviceName)
    {
        _targetDeviceName = targetDeviceName;
        _ = Task.Run(() => ConnectionLoopAsync(_cts.Token));
        _ = Task.Run(() => KeepAliveLoopAsync(_cts.Token));
    }

    private async Task ConnectionLoopAsync(CancellationToken token)
    {
        int backoffSeconds = 5;

        while (!token.IsCancellationRequested)
        {
            if (!IsConnected)
            {
                try
                {
                    StatusChanged?.Invoke($"検索中: {_targetDeviceName}...");
                    string selector = BluetoothDevice.GetDeviceSelectorFromPairingState(true);
                    var devices = await DeviceInformation.FindAllAsync(selector);
                    var target = devices.FirstOrDefault(d =>
                        d.Name.Contains(_targetDeviceName, StringComparison.OrdinalIgnoreCase));

                    if (target == null)
                    {
                        StatusChanged?.Invoke($"未検出: {_targetDeviceName} (ペアリング確認)");
                        await Task.Delay(TimeSpan.FromSeconds(backoffSeconds), token);
                        continue;
                    }

                    using var btDevice = await BluetoothDevice.FromIdAsync(target.Id);
                    var rfcommResult = await btDevice.GetRfcommServicesForIdAsync(
                        RfcommServiceId.FromUuid(ServiceUuid), BluetoothCacheMode.Uncached);

                    var service = rfcommResult.Services.FirstOrDefault();
                    if (service == null)
                    {
                        StatusChanged?.Invoke("Android側アプリ待機待ち...");
                        await Task.Delay(TimeSpan.FromSeconds(backoffSeconds), token);
                        backoffSeconds = Math.Min(backoffSeconds * 2, 30);
                        continue;
                    }

                    var socket = new StreamSocket();
                    await socket.ConnectAsync(service.ConnectionHostName, service.ConnectionServiceName);

                    _socket = socket;
                    _writer = new DataWriter(socket.OutputStream) { UnicodeEncoding = Windows.Storage.Streams.UnicodeEncoding.Utf8 };
                    IsConnected = true;
                    backoffSeconds = 5;
                    StatusChanged?.Invoke($"接続中: {target.Name}");
                }
                catch (Exception ex)
                {
                    CleanupSocket();
                    StatusChanged?.Invoke($"再接続待機中: {ex.Message}");
                    await Task.Delay(TimeSpan.FromSeconds(backoffSeconds), token);
                    backoffSeconds = Math.Min(backoffSeconds * 2, 30);
                }
            }
            else
            {
                await Task.Delay(2000, token);
            }
        }
    }

    private async Task KeepAliveLoopAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            await Task.Delay(TimeSpan.FromSeconds(30), token);
            if (IsConnected)
            {
                await SendJsonAsync(new
                {
                    type = "ping",
                    timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
                });
            }
        }
    }

    public async Task SendNotificationAsync(string id, string appName, string title, string body)
    {
        await SendJsonAsync(new
        {
            type = "notification",
            id,
            app_name = appName,
            title,
            body,
            timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
        });
    }

    private async Task SendJsonAsync(object payload)
    {
        if (!IsConnected || _writer == null) return;

        await _sendLock.WaitAsync();
        try
        {
            string jsonLine = JsonSerializer.Serialize(payload) + "\n";
            _writer.WriteString(jsonLine);
            await _writer.StoreAsync();
        }
        catch
        {
            CleanupSocket();
            StatusChanged?.Invoke("切断検知 - 再接続します");
        }
        finally
        {
            _sendLock.Release();
        }
    }

    private void CleanupSocket()
    {
        IsConnected = false;
        try { _writer?.Dispose(); } catch { }
        try { _socket?.Dispose(); } catch { }
        _writer = null;
        _socket = null;
    }

    public void Dispose()
    {
        _cts.Cancel();
        CleanupSocket();
        _sendLock.Dispose();
    }
}
