package io.github.masahiroc1203.nasbackup.core

import com.hierynomus.msdtyp.AccessMask
import com.hierynomus.msdtyp.FileTime
import com.hierynomus.mserref.NtStatus
import com.hierynomus.msfscc.FileAttributes
import com.hierynomus.msfscc.fileinformation.FileBasicInformation
import com.hierynomus.mssmb2.SMB2CreateDisposition
import com.hierynomus.mssmb2.SMB2CreateOptions
import com.hierynomus.mssmb2.SMB2ShareAccess
import com.hierynomus.mssmb2.SMBApiException
import com.hierynomus.security.bc.BCSecurityProvider
import com.hierynomus.smbj.SMBClient
import com.hierynomus.smbj.SmbConfig
import com.hierynomus.smbj.auth.AuthenticationContext
import com.hierynomus.smbj.auth.NtlmAuthenticator
import com.hierynomus.smbj.connection.Connection
import com.hierynomus.smbj.session.Session
import com.hierynomus.smbj.share.DiskShare
import java.io.IOException
import java.nio.file.FileAlreadyExistsException
import java.util.EnumSet
import java.util.concurrent.TimeUnit

/** NAS への接続設定 */
data class NasConfig(
    /** NAS の IP アドレスまたはホスト名 */
    val host: String,
    /** 共有フォルダ名 (例: "share") */
    val share: String,
    /** ユーザー名。空ならゲストで接続する */
    val user: String = "",
    val password: String = "",
    val port: Int = 445,
)

/** SMB (Windows のファイル共有) で NAS の共有フォルダを操作する。 */
class SmbRemoteFs private constructor(
    private val client: SMBClient,
    private val connection: Connection,
    private val session: Session,
    private val share: DiskShare,
) : RemoteFs {

    companion object {
        private val NOT_FOUND = setOf(
            NtStatus.STATUS_OBJECT_NAME_NOT_FOUND,
            NtStatus.STATUS_OBJECT_PATH_NOT_FOUND,
            NtStatus.STATUS_NO_SUCH_FILE,
            NtStatus.STATUS_NOT_FOUND,
        )

        fun connect(config: NasConfig, timeoutSeconds: Long = 30): SmbRemoteFs {
            val smbConfig = SmbConfig.builder()
                // Android には SMB の認証に必要な暗号 (MD4 など) が無いので BouncyCastle を使う
                .withSecurityProvider(BCSecurityProvider())
                // Kerberos は家庭の NAS では使わない (Android では動かないクラスを避ける)
                .withAuthenticators(NtlmAuthenticator.Factory())
                .withTimeout(timeoutSeconds, TimeUnit.SECONDS)
                .withSoTimeout(timeoutSeconds, TimeUnit.SECONDS)
                .build()
            val client = SMBClient(smbConfig)
            try {
                val connection = client.connect(config.host.trim(), config.port)
                val auth = if (config.user.isBlank()) {
                    AuthenticationContext.guest()
                } else {
                    AuthenticationContext(config.user.trim(), config.password.toCharArray(), "")
                }
                val session = connection.authenticate(auth)
                val share = session.connectShare(config.share.trim().trim('/', '\\')) as? DiskShare
                    ?: throw IOException("「${config.share}」はファイル共有フォルダではありません")
                return SmbRemoteFs(client, connection, session, share)
            } catch (e: Exception) {
                client.close()
                throw e
            }
        }

        private fun smbPath(path: String) = path.trim('/').replace('/', '\\')
    }

    override fun stat(path: String): RemoteEntry? {
        val info = try {
            share.getFileInformation(smbPath(path))
        } catch (e: SMBApiException) {
            if (e.status in NOT_FOUND) return null
            throw e
        }
        return RemoteEntry(
            name = path.substringAfterLast('/'),
            size = info.standardInformation.endOfFile,
            isDirectory = info.standardInformation.isDirectory,
        )
    }

    override fun list(dir: String): List<RemoteEntry> {
        val entries = try {
            share.list(smbPath(dir))
        } catch (e: SMBApiException) {
            if (e.status in NOT_FOUND) return emptyList()
            throw e
        }
        return entries
            .filter { it.fileName != "." && it.fileName != ".." }
            .map {
                RemoteEntry(
                    name = it.fileName,
                    size = it.endOfFile,
                    isDirectory = it.fileAttributes and FileAttributes.FILE_ATTRIBUTE_DIRECTORY.value != 0L,
                )
            }
    }

    override fun mkdirs(dir: String) {
        var current = ""
        for (segment in dir.trim('/').split('/').filter { it.isNotEmpty() }) {
            current = if (current.isEmpty()) segment else "$current\\$segment"
            if (share.folderExists(current)) continue
            try {
                share.mkdir(current)
            } catch (e: SMBApiException) {
                if (e.status != NtStatus.STATUS_OBJECT_NAME_COLLISION) throw e
            }
        }
    }

    override fun openForWrite(path: String): RemoteWriter {
        val file = share.openFile(
            smbPath(path),
            EnumSet.of(AccessMask.GENERIC_WRITE),
            EnumSet.of(FileAttributes.FILE_ATTRIBUTE_NORMAL),
            SMB2ShareAccess.ALL,
            SMB2CreateDisposition.FILE_OPEN_IF,
            EnumSet.of(SMB2CreateOptions.FILE_NON_DIRECTORY_FILE),
        )
        return object : RemoteWriter {
            override fun write(offset: Long, data: ByteArray, length: Int) {
                if (length > 0) file.write(data, offset, 0, length)
            }

            override fun close() = file.close()
        }
    }

    override fun rename(from: String, to: String) {
        share.openFile(
            smbPath(from),
            EnumSet.of(AccessMask.DELETE, AccessMask.GENERIC_READ),
            null,
            SMB2ShareAccess.ALL,
            SMB2CreateDisposition.FILE_OPEN,
            EnumSet.of(SMB2CreateOptions.FILE_NON_DIRECTORY_FILE),
        ).use { file ->
            try {
                file.rename(smbPath(to), false)
            } catch (e: SMBApiException) {
                if (e.status == NtStatus.STATUS_OBJECT_NAME_COLLISION) throw FileAlreadyExistsException(to)
                throw e
            }
        }
    }

    override fun delete(path: String) {
        try {
            share.rm(smbPath(path))
        } catch (e: SMBApiException) {
            if (e.status !in NOT_FOUND) throw e
        }
    }

    override fun setTimes(path: String, epochMillis: Long) {
        val t = FileTime.ofEpochMillis(epochMillis)
        share.setFileInformation(
            smbPath(path),
            FileBasicInformation(t, FileBasicInformation.DONT_SET, t, FileBasicInformation.DONT_SET, 0),
        )
    }

    override fun space(): Pair<Long, Long>? = runCatching {
        val info = share.shareInformation
        info.callerFreeSpace to info.totalSpace
    }.getOrNull()

    override fun close() {
        runCatching { share.close() }
        runCatching { session.close() }
        runCatching { connection.close() }
        runCatching { client.close() }
    }
}

/** 例外をスマホに表示する日本語のメッセージにする。 */
fun describeError(e: Throwable): String {
    var cause: Throwable? = e
    while (cause != null) {
        if (cause is SMBApiException) {
            return when (cause.status) {
                NtStatus.STATUS_LOGON_FAILURE -> "ユーザー名またはパスワードが違います"
                NtStatus.STATUS_ACCOUNT_DISABLED, NtStatus.STATUS_PASSWORD_EXPIRED -> "NASのユーザーが使えない状態です"
                NtStatus.STATUS_BAD_NETWORK_NAME -> "共有フォルダが見つかりません。共有フォルダ名を確認してください"
                NtStatus.STATUS_ACCESS_DENIED -> "共有フォルダに書き込む権限がありません"
                NtStatus.STATUS_DISK_FULL -> "NASの空き容量が足りません"
                NtStatus.STATUS_OBJECT_NAME_INVALID -> "NASで使えないファイル名です"
                else -> "NASでエラーが発生しました (${cause.status})"
            }
        }
        if (cause is java.net.UnknownHostException) return "NASが見つかりません。IPアドレスを確認してください"
        if (cause is java.net.ConnectException || cause is java.net.NoRouteToHostException) {
            return "NASに接続できません。IPアドレスと、スマホが家のWi-Fiにつながっているか確認してください"
        }
        if (cause is java.net.SocketTimeoutException || cause is java.util.concurrent.TimeoutException) {
            return "NASからの応答がありません。NASがスリープしていないか確認してください"
        }
        cause = cause.cause
    }
    return e.message ?: e.javaClass.simpleName
}
