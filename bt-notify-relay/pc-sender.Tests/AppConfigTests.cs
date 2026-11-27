using System.Runtime.CompilerServices;
using BtNotifySender;
using Xunit;

public class AppConfigTests
{
    private static string RepoFile(string relative, [CallerFilePath] string here = "") =>
        Path.GetFullPath(Path.Combine(Path.GetDirectoryName(here)!, "..", relative));

    [Fact]
    public void ShippedConfig_Parses()
    {
        var config = AppConfig.Parse(File.ReadAllText(RepoFile("pc-sender/config.json")));
        Assert.Equal("S25", config.TargetDeviceName);
        Assert.True(config.EnableOutlookCom);
        Assert.Equal(new[] { 10, 5, 0 }, config.ReminderMinutesBefore);
        Assert.Equal(2, config.CustomReminders.Count);
        Assert.All(config.CustomReminders, r => Assert.True(ReminderClock.TryParseTimeOfDay(r.Time, out _)));
    }

    [Fact]
    public void AllowsCommentsAndTrailingCommas()
    {
        var config = AppConfig.Parse("""
            {
              // スマホの表示名の一部
              "target_device_name": "Pixel",
              "ics_sources": ["https://example.com/a.ics",],
            }
            """);
        Assert.Equal("Pixel", config.TargetDeviceName);
        Assert.Single(config.IcsSources);
        Assert.Equal("23:00", config.QuietHoursStart); // 書いていない項目は既定値
    }

    [Fact]
    public void Load_CreatesDefaultFileWhenMissing()
    {
        var dir = Directory.CreateTempSubdirectory();
        try
        {
            var path = Path.Combine(dir.FullName, "config.json");
            var config = AppConfig.Load(path, out var error);
            Assert.Null(error);
            Assert.True(File.Exists(path));
            Assert.Equal(config.TargetDeviceName, AppConfig.Parse(File.ReadAllText(path)).TargetDeviceName);
        }
        finally
        {
            dir.Delete(true);
        }
    }

    [Fact]
    public void Load_BrokenJson_FallsBackToDefaults()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, "{ \"target_device_name\": ");
            var config = AppConfig.Load(path, out var error);
            Assert.NotNull(error);
            Assert.Equal("S25", config.TargetDeviceName);
        }
        finally
        {
            File.Delete(path);
        }
    }
}
