package io.github.masahiroc1203.nasbackup.core

import java.io.IOException
import java.io.InputStream
import java.nio.file.FileAlreadyExistsException
import java.security.MessageDigest
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

enum class Layout { DATE, FLAT }

data class BackupSettings(
    /** 共有フォルダの中の保存先フォルダ (例: "SmartphoneBackup")。空なら共有フォルダの直下。 */
    val baseDir: String,
    /** 家族ごとのフォルダ名 (例: "papa")。空ならフォルダを分けない。 */
    val owner: String = "",
    val layout: Layout = Layout.DATE,
)

/** バックアップするファイル (スマホ側)。 */
data class MediaFile(
    val id: Long,
    val name: String,
    val size: Long,
    /** 撮影日時 (UNIX ミリ秒) */
    val takenAtMillis: Long,
    val open: () -> InputStream,
)

sealed interface BackupResult {
    /** NAS 上の保存先 (共有フォルダ内のパス) */
    val path: String

    data class Uploaded(override val path: String) : BackupResult
    data class AlreadyBackedUp(override val path: String) : BackupResult
}

class BackupCancelledException : IOException("cancelled")

/**
 * スマホのファイルを NAS に保存する処理 (サーバー版 nas-backup と同じフォルダ構成・重複判定)。
 *
 * 保存先: <baseDir>/<owner>/<YYYY>/<YYYY-MM>/<ファイル名>
 * 送信途中のファイルは <baseDir>/.nasbackup/tmp/ に置き、続きから再開できるようにする。
 */
class BackupEngine(
    private val fs: RemoteFs,
    settings: BackupSettings,
    private val zone: ZoneId = ZoneId.systemDefault(),
) {
    private val base = normalizeDir(settings.baseDir)
    private val owner = sanitizeName(settings.owner.trim(), 64) ?: ""
    private val layout = settings.layout
    private val tmpDir = joinPath(base, ".nasbackup", "tmp")

    private val yearFmt = DateTimeFormatter.ofPattern("yyyy")
    private val monthFmt = DateTimeFormatter.ofPattern("yyyy-MM")

    /** ファイルの保存先フォルダ */
    fun targetDir(file: MediaFile): String {
        val dateParts = if (layout == Layout.DATE) {
            val t = Instant.ofEpochMilli(file.takenAtMillis).atZone(zone)
            arrayOf(yearFmt.format(t), monthFmt.format(t))
        } else {
            emptyArray()
        }
        return joinPath(base, owner, *dateParts)
    }

    private fun fileName(file: MediaFile): String =
        sanitizeName(file.name) ?: "file_${file.id}"

    /**
     * NAS にすでにバックアップ済みのファイルを調べる。
     * 保存先フォルダごとに一覧を 1 回だけ取得するので、ファイル数が多くても速い。
     * 戻り値: ファイル ID → NAS 上のパス
     */
    fun findBackedUp(files: List<MediaFile>, isCancelled: () -> Boolean = { false }): Map<Long, String> {
        val listings = HashMap<String, Map<String, Long>>()
        val result = HashMap<Long, String>()
        for (file in files) {
            if (isCancelled()) break
            val dir = targetDir(file)
            val entries = listings.getOrPut(dir) {
                fs.list(dir).filter { !it.isDirectory }.associate { it.name.lowercase() to it.size }
            }
            val name = fileName(file)
            var i = 0
            while (true) {
                val candidate = numberedName(name, i)
                val size = entries[candidate.lowercase()] ?: break
                if (size == file.size) {
                    result[file.id] = joinPath(dir, candidate)
                    break
                }
                i++
            }
        }
        return result
    }

    /**
     * 1 ファイルをバックアップする。
     * 途中で失敗・中断しても、もう一度呼べば送信済みの続きから再開する。
     */
    fun backup(
        file: MediaFile,
        chunkSize: Int = 1 shl 20,
        onProgress: (sentBytes: Long) -> Unit = {},
        isCancelled: () -> Boolean = { false },
    ): BackupResult {
        val dir = targetDir(file)
        val name = fileName(file)

        // 同じ名前・同じサイズのファイルがあればバックアップ済み
        findSlot(dir, name, file.size)?.let { existing ->
            onProgress(file.size)
            return BackupResult.AlreadyBackedUp(existing)
        }

        val tmp = joinPath(tmpDir, "android-${tmpKey(file)}.part")
        fs.mkdirs(tmpDir)
        var offset = fs.stat(tmp)?.size ?: 0L
        if (offset > file.size) {
            fs.delete(tmp)
            offset = 0L
        }
        onProgress(offset)

        if (offset < file.size || file.size == 0L) {
            upload(file, tmp, offset, chunkSize, onProgress, isCancelled)
        }
        val uploaded = fs.stat(tmp)?.size
        if (uploaded != file.size) {
            throw IOException("送信したサイズが一致しません ($uploaded / ${file.size})")
        }

        // 保存先へ移動 (同じ名前で中身が違うファイルがあれば "名前 (1).拡張子" にする)
        fs.mkdirs(dir)
        var i = 0
        while (true) {
            val candidate = joinPath(dir, numberedName(name, i))
            val existing = fs.stat(candidate)
            if (existing == null) {
                try {
                    fs.rename(tmp, candidate)
                } catch (e: FileAlreadyExistsException) {
                    continue // 確認した直後に別の端末が保存した: もう一度確認する
                }
                runCatching { fs.setTimes(candidate, file.takenAtMillis) }
                return BackupResult.Uploaded(candidate)
            }
            if (!existing.isDirectory && existing.size == file.size) {
                fs.delete(tmp)
                return BackupResult.AlreadyBackedUp(candidate)
            }
            if (++i > 9999) throw IOException("同じ名前のファイルが多すぎます: $name")
        }
    }

    private fun findSlot(dir: String, name: String, size: Long): String? {
        var i = 0
        while (true) {
            val candidate = joinPath(dir, numberedName(name, i))
            val existing = fs.stat(candidate) ?: return null
            if (!existing.isDirectory && existing.size == size) return candidate
            i++
        }
    }

    private fun upload(
        file: MediaFile,
        tmp: String,
        startOffset: Long,
        chunkSize: Int,
        onProgress: (Long) -> Unit,
        isCancelled: () -> Boolean,
    ) {
        file.open().use { input ->
            skipFully(input, startOffset)
            fs.openForWrite(tmp).use { writer ->
                val buf = ByteArray(chunkSize)
                var pos = startOffset
                if (file.size == 0L) {
                    writer.write(0, buf, 0)
                }
                while (pos < file.size) {
                    if (isCancelled()) throw BackupCancelledException()
                    val want = minOf(chunkSize.toLong(), file.size - pos).toInt()
                    val n = readFully(input, buf, want)
                    if (n <= 0) throw IOException("スマホのファイルを最後まで読めませんでした")
                    writer.write(pos, buf, n)
                    pos += n
                    onProgress(pos)
                }
            }
        }
    }

    private fun tmpKey(file: MediaFile): String {
        val key = "$owner\u0000${file.name}\u0000${file.size}\u0000${file.takenAtMillis}"
        val digest = MessageDigest.getInstance("SHA-256").digest(key.toByteArray())
        return digest.take(16).joinToString("") { "%02x".format(it) }
    }

    companion object {
        private fun skipFully(input: InputStream, n: Long) {
            var left = n
            while (left > 0) {
                val skipped = input.skip(left)
                if (skipped > 0) {
                    left -= skipped
                } else {
                    if (input.read() < 0) throw IOException("スマホのファイルを読めませんでした")
                    left--
                }
            }
        }

        private fun readFully(input: InputStream, buf: ByteArray, len: Int): Int {
            var total = 0
            while (total < len) {
                val n = input.read(buf, total, len - total)
                if (n < 0) break
                total += n
            }
            return total
        }
    }
}
