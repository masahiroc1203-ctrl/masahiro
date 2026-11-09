package io.github.masahiroc1203.nasbackup.core

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.IOException
import java.time.ZoneId
import java.time.ZonedDateTime

class BackupEngineTest {
    private val tokyo = ZoneId.of("Asia/Tokyo")

    private fun millis(y: Int, m: Int, d: Int, h: Int = 12) =
        ZonedDateTime.of(y, m, d, h, 0, 0, 0, tokyo).toInstant().toEpochMilli()

    private fun media(id: Long, name: String, data: ByteArray, taken: Long = millis(2024, 5, 3)) =
        MediaFile(id, name, data.size.toLong(), taken) { data.inputStream() }

    private fun engine(fs: RemoteFs, owner: String = "papa", layout: Layout = Layout.DATE) =
        BackupEngine(fs, BackupSettings("SmartphoneBackup", owner, layout), tokyo)

    private fun bytes(n: Int, seed: Int = 1) = ByteArray(n) { ((it * 31 + seed) % 251).toByte() }

    @Test
    fun savesIntoCaptureMonthFolder() {
        val fs = MemoryRemoteFs()
        val data = bytes(5000)
        val r = engine(fs).backup(media(1, "IMG_0001.JPG", data), chunkSize = 700)
        assertEquals(BackupResult.Uploaded("SmartphoneBackup/papa/2024/2024-05/IMG_0001.JPG"), r)
        assertArrayEquals(data, fs.read(r.path))
        assertEquals(millis(2024, 5, 3), fs.times[r.path.lowercase()])
        assertEquals(listOf(r.path), fs.paths()) // 一時ファイルが残っていない
    }

    @Test
    fun monthUsesLocalTimeZone() {
        // 2023-12-31 23:30 UTC は日本時間では 2024-01-01
        val taken = ZonedDateTime.of(2023, 12, 31, 23, 30, 0, 0, ZoneId.of("UTC")).toInstant().toEpochMilli()
        val r = engine(MemoryRemoteFs(), owner = "").backup(media(1, "VID.MOV", bytes(10), taken))
        assertEquals("SmartphoneBackup/2024/2024-01/VID.MOV", r.path)
    }

    @Test
    fun flatLayout() {
        val r = engine(MemoryRemoteFs(), layout = Layout.FLAT).backup(media(1, "a.jpg", bytes(10)))
        assertEquals("SmartphoneBackup/papa/a.jpg", r.path)
    }

    @Test
    fun sameNameAndSizeIsAlreadyBackedUp() {
        val fs = MemoryRemoteFs()
        val data = bytes(100)
        engine(fs).backup(media(1, "IMG_0001.JPG", data))
        // 大文字・小文字が違っても同じファイル扱い (Samba は区別しない)
        val r = engine(fs).backup(media(1, "img_0001.jpg", data))
        assertTrue(r is BackupResult.AlreadyBackedUp)
        assertTrue(r.path.equals("SmartphoneBackup/papa/2024/2024-05/IMG_0001.JPG", ignoreCase = true))
        assertEquals(1, fs.paths().size)
    }

    @Test
    fun sameNameDifferentContentIsRenamed() {
        val fs = MemoryRemoteFs()
        val e = engine(fs)
        e.backup(media(1, "IMG_1.JPG", bytes(10)))
        val r2 = e.backup(media(2, "IMG_1.JPG", bytes(20)))
        val r3 = e.backup(media(3, "IMG_1.JPG", bytes(30)))
        assertEquals("SmartphoneBackup/papa/2024/2024-05/IMG_1 (1).JPG", r2.path)
        assertEquals("SmartphoneBackup/papa/2024/2024-05/IMG_1 (2).JPG", r3.path)
        // 2 番目と同じものをもう一度送ると "(1)" がバックアップ済みとして見つかる
        assertEquals(BackupResult.AlreadyBackedUp(r2.path), e.backup(media(2, "IMG_1.JPG", bytes(20))))
        assertArrayEquals(bytes(10), fs.read("SmartphoneBackup/papa/2024/2024-05/IMG_1.JPG"))
    }

    @Test
    fun resumesAfterConnectionLoss() {
        val fs = MemoryRemoteFs()
        val data = bytes(10_000)
        fs.failAfterBytes = 4_321
        try {
            engine(fs).backup(media(1, "BIG.MOV", data), chunkSize = 1000)
            fail("should fail")
        } catch (e: IOException) {
            // 通信切断
        }
        fs.failAfterBytes = null

        var firstProgress = -1L
        val r = engine(fs).backup(media(1, "BIG.MOV", data), chunkSize = 1000, onProgress = {
            if (firstProgress < 0) firstProgress = it
        })
        assertEquals(4_321L, firstProgress) // 続きから送っている
        assertTrue(r is BackupResult.Uploaded)
        assertArrayEquals(data, fs.read(r.path))
    }

    @Test
    fun cancelKeepsPartialForLater() {
        val fs = MemoryRemoteFs()
        val data = bytes(5_000)
        var calls = 0
        try {
            engine(fs).backup(media(1, "a.mov", data), chunkSize = 1000, isCancelled = { ++calls > 2 })
            fail("should be cancelled")
        } catch (e: BackupCancelledException) {
            // 中断
        }
        val partial = fs.paths().single()
        assertTrue(partial.startsWith("SmartphoneBackup/.nasbackup/tmp/android-"))
        assertEquals(2_000, fs.read(partial)!!.size)

        val r = engine(fs).backup(media(1, "a.mov", data), chunkSize = 1000)
        assertArrayEquals(data, fs.read(r.path))
    }

    @Test
    fun emptyFile() {
        val fs = MemoryRemoteFs()
        val r = engine(fs).backup(media(1, "empty.jpg", ByteArray(0)))
        assertTrue(r is BackupResult.Uploaded)
        assertEquals(0, fs.read(r.path)!!.size)
    }

    @Test
    fun findBackedUpListsEachFolderOnce() {
        val fs = MemoryRemoteFs()
        fs.put("SmartphoneBackup/papa/2024/2024-05/IMG_1.JPG", bytes(10))
        fs.put("SmartphoneBackup/papa/2024/2024-05/IMG_2.JPG", bytes(99)) // 名前は同じだがサイズ違い
        fs.put("SmartphoneBackup/papa/2024/2024-05/IMG_2 (1).JPG", bytes(20))
        val files = listOf(
            media(1, "IMG_1.JPG", bytes(10)),
            media(2, "IMG_2.JPG", bytes(20)),
            media(3, "IMG_3.JPG", bytes(30)),
            media(4, "IMG_1.JPG", bytes(10), millis(2024, 6, 1)), // 別の月
        )
        var lists = 0
        val counting = object : RemoteFs by fs {
            override fun list(dir: String): List<RemoteEntry> = fs.list(dir).also { lists++ }
        }
        val found = engine(counting).findBackedUp(files)
        assertEquals(
            mapOf(
                1L to "SmartphoneBackup/papa/2024/2024-05/IMG_1.JPG",
                2L to "SmartphoneBackup/papa/2024/2024-05/IMG_2 (1).JPG",
            ),
            found,
        )
        assertEquals(2, lists) // 2024-05 と 2024-06 の 2 回だけ
    }

    @Test
    fun unsafeNamesStayInsideBackupFolder() {
        val fs = MemoryRemoteFs()
        val r = engine(fs, owner = "../..").backup(media(1, "../../evil.jpg", bytes(5)))
        assertEquals("SmartphoneBackup/2024/2024-05/evil.jpg", r.path)
        val r2 = engine(fs, owner = "a/b").backup(media(2, "what?.jpg", bytes(5)))
        assertEquals("SmartphoneBackup/b/2024/2024-05/what_.jpg", r2.path)
    }

    @Test
    fun sanitizeNameRules() {
        assertEquals("IMG_0001.JPG", sanitizeName("IMG_0001.JPG"))
        assertEquals("写真 2024.heic", sanitizeName("写真 2024.heic"))
        assertEquals("d.jpg", sanitizeName("C:\\Users\\x\\d.jpg"))
        assertEquals("hidden", sanitizeName(".hidden"))
        assertEquals("spaced .jpg", sanitizeName(" spaced .jpg. "))
        assertNull(sanitizeName(".."))
        assertNull(sanitizeName("   "))
        val long = sanitizeName("あ".repeat(100) + ".jpg")!!
        assertTrue(long.toByteArray().size <= 200 && long.endsWith("あ.jpg"))
        assertEquals("photo/Smartphone", normalizeDir("\\photo\\Smartphone/"))
    }
}
