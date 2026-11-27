using System.Text.Json;
using BtNotifySender;
using Xunit;

public class ProtocolTests
{
    private static readonly DateTimeOffset Now = DateTimeOffset.FromUnixTimeSeconds(1795760000);

    [Fact]
    public void NotificationLine_IsOneJsonLineWithSpecFields()
    {
        string line = Protocol.NotificationLine("win-notif-1024", "Microsoft Teams", "定例ミーティング (5分前)",
            "15:30 から開始します\n2行目", Now);

        Assert.EndsWith("\n", line);
        Assert.DoesNotContain('\n', line[..^1]); // 本文の改行もエスケープされ、1 行に収まる

        using var doc = JsonDocument.Parse(line);
        var root = doc.RootElement;
        Assert.Equal("notification", root.GetProperty("type").GetString());
        Assert.Equal("win-notif-1024", root.GetProperty("id").GetString());
        Assert.Equal("Microsoft Teams", root.GetProperty("app_name").GetString());
        Assert.Equal("定例ミーティング (5分前)", root.GetProperty("title").GetString());
        Assert.Equal("15:30 から開始します\n2行目", root.GetProperty("body").GetString());
        Assert.Equal(1795760000, root.GetProperty("timestamp").GetInt64());
    }

    [Fact]
    public void PingAndPong_MatchSpec()
    {
        Assert.Equal("{\"type\":\"ping\",\"timestamp\":1795760000}\n", Protocol.PingLine(Now));
        Assert.Equal("{\"type\":\"pong\",\"timestamp\":1795760000}\n", Protocol.PongLine(Now));
    }

    [Theory]
    [InlineData("{\"type\":\"pong\",\"timestamp\":1795760030}", "pong")]
    [InlineData("{ \"type\": \"ping\" }", "ping")]
    [InlineData("not json", null)]
    [InlineData("{\"type\":1}", null)]
    [InlineData("[]", null)]
    [InlineData("{}", null)]
    [InlineData("", null)]
    public void MessageType_ReadsTypeOrNull(string line, string? expected)
    {
        Assert.Equal(expected, Protocol.MessageType(line));
    }

    [Fact]
    public void ServiceUuid_MatchesAndroidSide()
    {
        Assert.Equal(Guid.Parse("8ce255c0-200a-11e0-ac64-0800200c9a66"), Protocol.ServiceUuid);
    }
}
