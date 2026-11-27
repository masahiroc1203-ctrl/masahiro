using Windows.Foundation.Metadata;
using Windows.UI.Notifications;
using Windows.UI.Notifications.Management;

namespace BtNotifySender;

public class NotificationWatcher
{
    private readonly UserNotificationListener _listener;
    private readonly AppConfig _config;
    private readonly Func<string, string, string, string, Task> _onNotify;
    private readonly Queue<uint> _processedIds = new();
    private readonly HashSet<uint> _idSet = new();

    public NotificationWatcher(AppConfig config, Func<string, string, string, string, Task> onNotify)
    {
        _config = config;
        _onNotify = onNotify;
        _listener = UserNotificationListener.Current;
    }

    public async Task<string> StartAsync()
    {
        if (!ApiInformation.IsTypePresent("Windows.UI.Notifications.Management.UserNotificationListener"))
        {
            return "OS非対応";
        }

        var accessStatus = await _listener.RequestAccessAsync();
        if (accessStatus != UserNotificationListenerAccessStatus.Allowed)
        {
            return $"通知アクセス拒否 ({accessStatus})";
        }

        _listener.NotificationChanged += OnNotificationChanged;
        return "通知監視中";
    }

    private async void OnNotificationChanged(UserNotificationListener sender, UserNotificationChangedEventArgs args)
    {
        if (args.ChangeKind != UserNotificationChangedKind.Added) return;

        lock (_idSet)
        {
            if (_idSet.Contains(args.UserNotificationId)) return;
            _idSet.Add(args.UserNotificationId);
            _processedIds.Enqueue(args.UserNotificationId);
            if (_processedIds.Count > 100)
            {
                var oldest = _processedIds.Dequeue();
                _idSet.Remove(oldest);
            }
        }

        if (IsQuietHours()) return;

        var notif = sender.GetNotification(args.UserNotificationId);
        if (notif == null) return;

        string appName = notif.AppInfo?.DisplayInfo?.DisplayName ?? "Windows";

        if (_config.AllowedApps.Count > 0 &&
            !_config.AllowedApps.Any(a => appName.Contains(a, StringComparison.OrdinalIgnoreCase)))
        {
            return;
        }

        var binding = notif.Notification?.Visual?.GetBinding(KnownNotificationBindings.ToastGeneric);
        var textElements = binding?.GetTextElements().ToList();
        string title = textElements?.FirstOrDefault()?.Text ?? appName;
        string body = textElements != null && textElements.Count > 1
            ? string.Join("\n", textElements.Skip(1).Select(t => t.Text))
            : "";

        string combined = $"{title} {body}";
        if (_config.ExcludeKeywords.Any(k => combined.Contains(k, StringComparison.OrdinalIgnoreCase)))
        {
            return;
        }

        await _onNotify($"win-notif-{args.UserNotificationId}", appName, title, body);
    }

    private bool IsQuietHours()
    {
        if (!TimeSpan.TryParse(_config.QuietHoursStart, out var start) ||
            !TimeSpan.TryParse(_config.QuietHoursEnd, out var end))
        {
            return false;
        }

        var now = DateTime.Now.TimeOfDay;
        return start <= end ? (now >= start && now <= end) : (now >= start || now <= end);
    }
}
