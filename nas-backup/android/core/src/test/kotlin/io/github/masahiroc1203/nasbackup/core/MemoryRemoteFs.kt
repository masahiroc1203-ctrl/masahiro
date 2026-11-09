package io.github.masahiroc1203.nasbackup.core

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.nio.file.FileAlreadyExistsException

/** テスト用のメモリ上の NAS。LS720D (Samba) と同じく大文字・小文字を区別しない。 */
class MemoryRemoteFs : RemoteFs {
    val files = LinkedHashMap<String, ByteArray>() // key: 小文字のパス
    private val names = HashMap<String, String>()   // 小文字のパス → 実際のパス
    val dirs = HashSet<String>()
    val times = HashMap<String, Long>()

    /** 書き込みをこのバイト数で失敗させる (通信切断の再現) */
    var failAfterBytes: Long? = null
    private var written = 0L

    private fun key(p: String) = p.trim('/').lowercase()

    fun put(path: String, data: ByteArray) {
        files[key(path)] = data
        names[key(path)] = path.trim('/')
        var dir = path.trim('/').substringBeforeLast('/', "")
        while (dir.isNotEmpty()) {
            dirs += dir.lowercase()
            dir = dir.substringBeforeLast('/', "")
        }
    }

    fun read(path: String): ByteArray? = files[key(path)]

    fun paths(): List<String> = files.keys.map { names.getValue(it) }.sorted()

    override fun stat(path: String): RemoteEntry? {
        val k = key(path)
        files[k]?.let { return RemoteEntry(path.substringAfterLast('/'), it.size.toLong(), false) }
        if (k in dirs) return RemoteEntry(path.substringAfterLast('/'), 0, true)
        return null
    }

    override fun list(dir: String): List<RemoteEntry> {
        val prefix = key(dir) + "/"
        return files.filterKeys { it.startsWith(prefix) && !it.removePrefix(prefix).contains('/') }
            .map { (k, v) -> RemoteEntry(names.getValue(k).substringAfterLast('/'), v.size.toLong(), false) }
    }

    override fun mkdirs(dir: String) {
        var d = dir.trim('/')
        while (d.isNotEmpty()) {
            dirs += d.lowercase()
            d = d.substringBeforeLast('/', "")
        }
    }

    override fun openForWrite(path: String): RemoteWriter {
        val k = key(path)
        if (k !in files) put(path, ByteArray(0))
        return object : RemoteWriter {
            override fun write(offset: Long, data: ByteArray, length: Int) {
                val limit = failAfterBytes
                if (limit != null && written + length > limit) {
                    val partial = (limit - written).toInt().coerceAtLeast(0)
                    append(k, offset, data, partial)
                    written += partial
                    throw IOException("connection reset")
                }
                append(k, offset, data, length)
                written += length
            }

            override fun close() {}
        }
    }

    private fun append(k: String, offset: Long, data: ByteArray, length: Int) {
        val cur = files.getValue(k)
        require(offset == cur.size.toLong()) { "write at $offset but size is ${cur.size}" }
        files[k] = ByteArrayOutputStream().apply { write(cur); write(data, 0, length) }.toByteArray()
    }

    override fun rename(from: String, to: String) {
        if (stat(to) != null) throw FileAlreadyExistsException(to)
        val data = files.remove(key(from)) ?: throw IOException("not found: $from")
        names.remove(key(from))
        put(to, data)
    }

    override fun delete(path: String) {
        files.remove(key(path))
        names.remove(key(path))
    }

    override fun setTimes(path: String, epochMillis: Long) {
        times[key(path)] = epochMillis
    }

    override fun close() {}
}
