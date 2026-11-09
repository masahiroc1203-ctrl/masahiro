package io.github.masahiroc1203.nasbackup.core

import java.io.Closeable

/** NAS 上のファイル・フォルダの情報。 */
data class RemoteEntry(
    val name: String,
    val size: Long,
    val isDirectory: Boolean,
)

/** 書き込み先ファイル。close するまで開いたままにして、続けて書き込める。 */
interface RemoteWriter : Closeable {
    /** offset の位置に data[0 until length] を書き込む。 */
    fun write(offset: Long, data: ByteArray, length: Int)
}

/**
 * NAS の共有フォルダを操作するためのインターフェース。
 * パスは共有フォルダの中のパスで、区切りは "/" (例: "SmartphoneBackup/2026/2026-11/IMG_0001.JPG")。
 */
interface RemoteFs : Closeable {
    /** ファイル・フォルダの情報。存在しなければ null。 */
    fun stat(path: String): RemoteEntry?

    /** フォルダの中身。フォルダが存在しなければ空のリスト。 */
    fun list(dir: String): List<RemoteEntry>

    /** フォルダを (親フォルダも含めて) 作る。すでにあれば何もしない。 */
    fun mkdirs(dir: String)

    /** 書き込み用に開く。ファイルが無ければ作り、あれば中身を残したまま開く。 */
    fun openForWrite(path: String): RemoteWriter

    /** 名前を変更する。移動先がすでにあれば [java.nio.file.FileAlreadyExistsException]。 */
    fun rename(from: String, to: String)

    /** ファイルを削除する。存在しなければ何もしない。 */
    fun delete(path: String)

    /** 更新日時・作成日時を設定する。 */
    fun setTimes(path: String, epochMillis: Long)

    /** 空き容量と全体容量 (バイト)。取得できなければ null。 */
    fun space(): Pair<Long, Long>? = null
}
