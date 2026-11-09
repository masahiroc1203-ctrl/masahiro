package io.github.masahiroc1203.nasbackup.core

import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test
import java.io.IOException
import java.nio.file.FileAlreadyExistsException
import java.time.ZoneId
import java.time.ZonedDateTime
import java.util.UUID

/**
 * 実際の SMB サーバー (Samba) を使うテスト。
 * 環境変数 SMB_TEST_HOST / SMB_TEST_PORT / SMB_TEST_SHARE / SMB_TEST_USER / SMB_TEST_PASSWORD が
 * 設定されているときだけ実行する。
 */
class SmbRemoteFsIntegrationTest {
    private val host = System.getenv("SMB_TEST_HOST")
    private val config get() = NasConfig(
        host = host,
        share = System.getenv("SMB_TEST_SHARE") ?: "share",
        user = System.getenv("SMB_TEST_USER") ?: "",
        password = System.getenv("SMB_TEST_PASSWORD") ?: "",
        port = System.getenv("SMB_TEST_PORT")?.toInt() ?: 445,
    )
    private lateinit var fs: SmbRemoteFs
    private val root = "it-" + UUID.randomUUID().toString().take(8)

    @Before
    fun setUp() {
        assumeTrue("SMB_TEST_HOST is not set", !host.isNullOrBlank())
        fs = SmbRemoteFs.connect(config, timeoutSeconds = 10)
    }

    @After
    fun tearDown() {
        if (::fs.isInitialized) fs.close()
    }

    @Test
    fun basicFileOperations() {
        assertNull(fs.stat("$root/a/b"))
        assertTrue(fs.list("$root/none").isEmpty())

        fs.mkdirs("$root/写真/2026")
        fs.mkdirs("$root/写真/2026") // 2 回目もエラーにならない
        assertTrue(fs.stat("$root/写真/2026")!!.isDirectory)

        val path = "$root/写真/2026/テスト IMG_0001.JPG"
        val data = ByteArray(3_000_000) { (it % 253).toByte() }
        fs.openForWrite(path).use { w ->
            w.write(0, data, 1_000_000)
        }
        // 開き直して続きから書ける
        fs.openForWrite(path).use { w ->
            val rest = data.copyOfRange(1_000_000, data.size)
            w.write(1_000_000, rest, rest.size)
        }
        assertEquals(data.size.toLong(), fs.stat(path)!!.size)

        val listed = fs.list("$root/写真/2026")
        assertEquals(listOf("テスト IMG_0001.JPG"), listed.map { it.name })
        assertEquals(data.size.toLong(), listed.single().size)

        // 名前の変更。移動先があれば上書きしない
        fs.openForWrite("$root/other.bin").use { it.write(0, byteArrayOf(1, 2, 3), 3) }
        try {
            fs.rename("$root/other.bin", path)
            fail("rename should not overwrite")
        } catch (e: FileAlreadyExistsException) {
            // OK
        }
        assertEquals(data.size.toLong(), fs.stat(path)!!.size)
        fs.rename("$root/other.bin", "$root/写真/moved.bin")
        assertNull(fs.stat("$root/other.bin"))
        assertEquals(3L, fs.stat("$root/写真/moved.bin")!!.size)

        // Samba は大文字・小文字を区別しない (LS720D も同様)
        assertNotNull(fs.stat("$root/写真/MOVED.BIN"))

        fs.setTimes(path, 1_700_000_000_000)
        fs.delete("$root/写真/moved.bin")
        fs.delete("$root/写真/moved.bin") // 無いファイルの削除もエラーにならない
        assertNull(fs.stat("$root/写真/moved.bin"))
        assertNotNull(fs.space())
    }

    @Test
    fun backupEngineEndToEnd() {
        val tokyo = ZoneId.of("Asia/Tokyo")
        val taken = ZonedDateTime.of(2025, 12, 24, 20, 0, 0, 0, tokyo).toInstant().toEpochMilli()
        val data = ByteArray(2_500_000) { (it * 7 % 256).toByte() }
        val file = MediaFile(1, "IMG_9999.HEIC", data.size.toLong(), taken) { data.inputStream() }
        val engine = BackupEngine(fs, BackupSettings("$root/SmartphoneBackup", "papa"), tokyo)

        // 途中で中断 → 続きから再開
        var chunks = 0
        try {
            engine.backup(file, chunkSize = 512 * 1024, isCancelled = { ++chunks > 2 })
            fail("should be cancelled")
        } catch (e: BackupCancelledException) {
            // OK
        }
        var resumedFrom = -1L
        val r = engine.backup(file, chunkSize = 512 * 1024, onProgress = { if (resumedFrom < 0) resumedFrom = it })
        assertEquals(1024L * 1024, resumedFrom)
        assertEquals("$root/SmartphoneBackup/papa/2025/2025-12/IMG_9999.HEIC", r.path)
        assertTrue(r is BackupResult.Uploaded)

        // 2 回目はバックアップ済み。一覧からも見つかる
        assertTrue(engine.backup(file) is BackupResult.AlreadyBackedUp)
        assertEquals(mapOf(1L to r.path), engine.findBackedUp(listOf(file)))
        assertTrue(fs.list("$root/SmartphoneBackup/.nasbackup/tmp").isEmpty())
    }

    @Test
    fun wrongPasswordHasFriendlyMessage() {
        assumeTrue(config.user.isNotBlank())
        try {
            SmbRemoteFs.connect(config.copy(password = "wrong-password"), timeoutSeconds = 10).close()
            fail("should fail")
        } catch (e: Exception) {
            assertEquals("ユーザー名またはパスワードが違います", describeError(e))
        }
    }

    @Test
    fun unknownShareHasFriendlyMessage() {
        try {
            SmbRemoteFs.connect(config.copy(share = "no-such-share"), timeoutSeconds = 10).close()
            fail("should fail")
        } catch (e: Exception) {
            assertEquals("共有フォルダが見つかりません。共有フォルダ名を確認してください", describeError(e))
        }
    }

    @Test
    fun guestConnection() {
        SmbRemoteFs.connect(config.copy(user = "", password = ""), timeoutSeconds = 10).use { guest ->
            guest.mkdirs("$root/guest")
            assertTrue(guest.stat("$root/guest")!!.isDirectory)
        }
    }

    @Test
    fun unreachableHostHasFriendlyMessage() {
        try {
            SmbRemoteFs.connect(config.copy(host = "127.0.0.1", port = 1), timeoutSeconds = 5).close()
            fail("should fail")
        } catch (e: IOException) {
            assertTrue(describeError(e), describeError(e).startsWith("NASに接続できません"))
        }
    }
}
