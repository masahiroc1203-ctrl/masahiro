using System.Text.Json;
using System.Text.Json.Nodes;

namespace BtNotifySender;

/// <summary>
/// PC と Android の間の通信形式 (UTF-8 の改行区切り JSON。docs/spec.md の 3 章)。
/// Bluetooth に依存しない部分だけをここに置き、単体テストできるようにしている。
/// </summary>
public static class Protocol
{
    public static readonly Guid ServiceUuid = Guid.Parse("8ce255c0-200a-11e0-ac64-0800200c9a66");

    public static string NotificationLine(string id, string appName, string title, string body, DateTimeOffset now) =>
        ToLine(new JsonObject
        {
            ["type"] = "notification",
            ["id"] = id,
            ["app_name"] = appName,
            ["title"] = title,
            ["body"] = body,
            ["timestamp"] = now.ToUnixTimeSeconds(),
        });

    public static string PingLine(DateTimeOffset now) =>
        ToLine(new JsonObject { ["type"] = "ping", ["timestamp"] = now.ToUnixTimeSeconds() });

    public static string PongLine(DateTimeOffset now) =>
        ToLine(new JsonObject { ["type"] = "pong", ["timestamp"] = now.ToUnixTimeSeconds() });

    /// <summary>受信した 1 行の "type" を返す。JSON でない行や type が無い行は null。</summary>
    public static string? MessageType(string line)
    {
        try
        {
            return JsonNode.Parse(line) is JsonObject obj && obj["type"] is JsonValue v && v.TryGetValue(out string? type)
                ? type
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // 文字列中の改行は JSON のエスケープ (\n) になるので、1 メッセージは必ず 1 行になる
    private static string ToLine(JsonObject obj) => obj.ToJsonString() + "\n";
}
