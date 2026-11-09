package io.github.masahiroc1203.nasbackup.core

/**
 * ファイル名・フォルダ名として安全な文字列にする (サーバー版 nas-backup の sanitizeName と同じ規則)。
 * パス区切りや Windows で使えない文字を取り除き、".." などで保存先の外に出られないようにする。
 * 使える文字が残らなければ null。
 */
fun sanitizeName(name: String, maxBytes: Int = 200): String? {
    var s = name.replace('\\', '/').substringAfterLast('/')
    s = buildString {
        for (ch in s) {
            when {
                ch.code < 0x20 || ch.code == 0x7f || ch == '�' -> Unit
                ch in ":*?\"<>|" -> append('_')
                else -> append(ch)
            }
        }
    }
    s = s.trimEnd('.', ' ').trimStart('.', ' ')
    if (s.isEmpty()) return null
    if (s.toByteArray().size > maxBytes) {
        val dot = s.lastIndexOf('.')
        var ext = if (dot > 0) s.substring(dot) else ""
        if (ext.toByteArray().size > 16) ext = ""
        var base = s.removeSuffix(ext)
        while (base.isNotEmpty() && (base + ext).toByteArray().size > maxBytes) {
            base = base.dropLast(if (base.length >= 2 && base[base.length - 1].isLowSurrogate()) 2 else 1)
        }
        s = base + ext
    }
    return s
}

/** "photo\\Smartphone/" のような入力を "photo/Smartphone" に整える。不正な部分は取り除く。 */
fun normalizeDir(dir: String): String =
    dir.replace('\\', '/').split('/').mapNotNull { seg -> seg.trim().takeIf { it.isNotEmpty() }?.let { sanitizeName(it, 200) } }
        .joinToString("/")

/** "IMG_0001.JPG" → i=0: "IMG_0001.JPG", i=1: "IMG_0001 (1).JPG" */
fun numberedName(name: String, i: Int): String {
    if (i == 0) return name
    val dot = name.lastIndexOf('.')
    return if (dot > 0) "${name.substring(0, dot)} ($i)${name.substring(dot)}" else "$name ($i)"
}

fun joinPath(vararg parts: String): String = parts.filter { it.isNotEmpty() }.joinToString("/")
