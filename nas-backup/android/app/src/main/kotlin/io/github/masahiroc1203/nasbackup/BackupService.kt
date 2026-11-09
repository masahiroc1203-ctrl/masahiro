package io.github.masahiroc1203.nasbackup

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.hierynomus.mserref.NtStatus
import com.hierynomus.mssmb2.SMBApiException
import io.github.masahiroc1203.nasbackup.core.BackupCancelledException
import io.github.masahiroc1203.nasbackup.core.BackupEngine
import io.github.masahiroc1203.nasbackup.core.BackupResult
import io.github.masahiroc1203.nasbackup.core.SmbRemoteFs
import io.github.masahiroc1203.nasbackup.core.describeError
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.FileNotFoundException

/** バックアップの進み具合 (画面と通知に表示する) */
data class BackupProgress(
    val running: Boolean = false,
    val total: Int = 0,
    val uploaded: Int = 0,
    val skipped: Int = 0,
    val failed: Int = 0,
    val totalBytes: Long = 0,
    val sentBytes: Long = 0,
    val currentName: String? = null,
    /** 再接続中などの一時的なメッセージ */
    val message: String? = null,
    /** 全体を中断したエラー (パスワード違いなど) */
    val fatalError: String? = null,
    val finished: Boolean = false,
    val cancelled: Boolean = false,
) {
    val processed get() = uploaded + skipped + failed
    val fraction get() = if (totalBytes > 0) (sentBytes.toFloat() / totalBytes).coerceIn(0f, 1f) else 0f
}

/** 画面とバックアップ処理 (BackupService) の間で状態を共有する */
object BackupController {
    private val _progress = MutableStateFlow(BackupProgress())
    val progress: StateFlow<BackupProgress> = _progress

    /** NAS にあることが分かっているファイル (ID → NAS 上のパス) */
    val backedUp = MutableStateFlow<Map<Long, String>>(emptyMap())

    /** 失敗したファイル (ID → 理由) */
    val failures = MutableStateFlow<Map<Long, String>>(emptyMap())

    @Volatile
    internal var queue: List<MediaItem> = emptyList()

    @Volatile
    internal var cancelRequested = false

    internal fun update(f: (BackupProgress) -> BackupProgress) = _progress.update(f)

    fun start(context: Context, items: List<MediaItem>) {
        if (_progress.value.running || items.isEmpty()) return
        queue = items
        cancelRequested = false
        failures.update { it - items.map { i -> i.id }.toSet() }
        _progress.value = BackupProgress(
            running = true,
            total = items.size,
            totalBytes = items.sumOf { it.size.coerceAtLeast(0) },
        )
        ContextCompat.startForegroundService(context, Intent(context, BackupService::class.java))
    }

    fun stop() {
        cancelRequested = true
    }

    fun dismissResult() {
        if (!_progress.value.running) _progress.value = BackupProgress()
    }
}

/**
 * NAS への送信を行うサービス。
 * フォアグラウンドサービスにすることで、画面を消したり他のアプリに切り替えたりしても送信を続ける。
 */
class BackupService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var job: Job? = null
    private var lastNotify = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            BackupController.stop()
            return START_NOT_STICKY
        }
        createChannel()
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            progressNotification(BackupController.progress.value),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
        )
        if (job?.isActive != true) {
            job = scope.launch {
                try {
                    runBackup()
                } finally {
                    ServiceCompat.stopForeground(this@BackupService, ServiceCompat.STOP_FOREGROUND_REMOVE)
                    showFinishedNotification(BackupController.progress.value)
                    stopSelf()
                }
            }
        }
        return START_NOT_STICKY
    }

    // Android 15 以降: dataSync のサービスは 1 日 6 時間まで
    override fun onTimeout(startId: Int, fgsType: Int) {
        BackupController.stop()
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private suspend fun runBackup() {
        val items = BackupController.queue
        val settings = SettingsStore.get(this).settings.value
        val repo = MediaRepository(this)
        val wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "NasBackup:upload")
        wakeLock.acquire(6 * 60 * 60 * 1000L)

        var fs: SmbRemoteFs? = null
        var completedBytes = 0L
        try {
            itemLoop@ for (item in items) {
                if (BackupController.cancelRequested) break
                BackupController.update { it.copy(currentName = item.name, message = null) }
                var attempt = 0
                while (true) {
                    if (BackupController.cancelRequested) break@itemLoop
                    try {
                        val conn = fs ?: SmbRemoteFs.connect(settings.nasConfig()).also { fs = it }
                        val engine = BackupEngine(conn, settings.backupSettings())
                        val result = engine.backup(
                            repo.toMediaFile(item),
                            onProgress = { sent ->
                                BackupController.update { it.copy(sentBytes = completedBytes + sent, message = null) }
                                notifyProgress()
                            },
                            isCancelled = { BackupController.cancelRequested },
                        )
                        BackupController.backedUp.update { it + (item.id to result.path) }
                        BackupController.update {
                            if (result is BackupResult.Uploaded) it.copy(uploaded = it.uploaded + 1) else it.copy(skipped = it.skipped + 1)
                        }
                        break
                    } catch (e: BackupCancelledException) {
                        break@itemLoop
                    } catch (e: Exception) {
                        val reason = describeError(e)
                        if (isFatal(e)) {
                            // パスワード違いなど、続けても全部失敗するエラー
                            BackupController.update { it.copy(fatalError = reason) }
                            break@itemLoop
                        }
                        if (e is FileNotFoundException || e is SecurityException) {
                            // スマホからファイルが消された等
                            fail(item, reason)
                            break
                        }
                        // 通信エラー: つなぎ直して続きから再開する
                        fs?.close()
                        fs = null
                        attempt++
                        if (attempt > MAX_RETRY) {
                            fail(item, reason)
                            break
                        }
                        BackupController.update { it.copy(message = "再接続を待っています… ($attempt/$MAX_RETRY) $reason") }
                        notifyProgress(force = true)
                        delay(minOf(30_000L, 2_000L shl (attempt - 1)))
                    }
                }
                completedBytes += item.size.coerceAtLeast(0)
                BackupController.update { it.copy(sentBytes = completedBytes) }
                notifyProgress(force = true)
            }
        } finally {
            fs?.close()
            if (wakeLock.isHeld) wakeLock.release()
            BackupController.update {
                it.copy(
                    running = false,
                    finished = true,
                    cancelled = BackupController.cancelRequested,
                    currentName = null,
                    message = null,
                )
            }
        }
    }

    private fun fail(item: MediaItem, reason: String) {
        BackupController.failures.update { it + (item.id to reason) }
        BackupController.update { it.copy(failed = it.failed + 1) }
    }

    private fun isFatal(e: Throwable): Boolean {
        var c: Throwable? = e
        while (c != null) {
            if (c is SMBApiException) {
                return c.status in setOf(
                    NtStatus.STATUS_LOGON_FAILURE,
                    NtStatus.STATUS_ACCOUNT_DISABLED,
                    NtStatus.STATUS_PASSWORD_EXPIRED,
                    NtStatus.STATUS_BAD_NETWORK_NAME,
                    NtStatus.STATUS_ACCESS_DENIED,
                    NtStatus.STATUS_DISK_FULL,
                )
            }
            c = c.cause
        }
        return false
    }

    // ---------------------------------------------------------------- 通知

    private fun createChannel() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "バックアップ", NotificationManager.IMPORTANCE_LOW).apply {
                description = "NASへのバックアップの進み具合"
            },
        )
    }

    private fun openAppIntent() = PendingIntent.getActivity(
        this,
        0,
        Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun progressNotification(p: BackupProgress) = NotificationCompat.Builder(this, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.stat_sys_upload)
        .setContentTitle("NASにバックアップ中 ${minOf(p.processed + 1, p.total)}/${p.total}件")
        .setContentText(p.message ?: p.currentName ?: "準備しています…")
        .setProgress(1000, (p.fraction * 1000).toInt(), p.totalBytes == 0L)
        .setOngoing(true)
        .setOnlyAlertOnce(true)
        .setContentIntent(openAppIntent())
        .addAction(
            0,
            "停止",
            PendingIntent.getService(
                this,
                1,
                Intent(this, BackupService::class.java).setAction(ACTION_STOP),
                PendingIntent.FLAG_IMMUTABLE,
            ),
        )
        .build()

    private fun notifyProgress(force: Boolean = false) {
        val now = System.currentTimeMillis()
        if (!force && now - lastNotify < 1000) return
        lastNotify = now
        if (NotificationManagerCompat.from(this).areNotificationsEnabled()) {
            try {
                NotificationManagerCompat.from(this).notify(NOTIFICATION_ID, progressNotification(BackupController.progress.value))
            } catch (e: SecurityException) {
                // 通知が許可されていない
            }
        }
    }

    private fun showFinishedNotification(p: BackupProgress) {
        val title = when {
            p.fatalError != null -> "バックアップできませんでした"
            p.cancelled -> "バックアップを停止しました"
            p.failed > 0 -> "バックアップが終わりました (失敗 ${p.failed}件)"
            else -> "バックアップが完了しました"
        }
        val text = p.fatalError ?: "新規 ${p.uploaded}件・保存済み ${p.skipped}件"
        val n = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload_done)
            .setContentTitle(title)
            .setContentText(text)
            .setAutoCancel(true)
            .setContentIntent(openAppIntent())
            .build()
        try {
            NotificationManagerCompat.from(this).notify(DONE_NOTIFICATION_ID, n)
        } catch (e: SecurityException) {
            // 通知が許可されていない
        }
    }

    companion object {
        private const val CHANNEL_ID = "backup"
        private const val NOTIFICATION_ID = 1
        private const val DONE_NOTIFICATION_ID = 2
        private const val ACTION_STOP = "io.github.masahiroc1203.nasbackup.STOP"
        private const val MAX_RETRY = 6
    }
}
