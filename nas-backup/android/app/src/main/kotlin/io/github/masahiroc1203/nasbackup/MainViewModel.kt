package io.github.masahiroc1203.nasbackup

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.masahiroc1203.nasbackup.core.BackupEngine
import io.github.masahiroc1203.nasbackup.core.SmbRemoteFs
import io.github.masahiroc1203.nasbackup.core.describeError
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** NAS の状態 */
sealed interface NasStatus {
    data object NotConfigured : NasStatus
    data object Checking : NasStatus
    data class Ok(val freeBytes: Long?, val totalBytes: Long?) : NasStatus
    data class Error(val message: String) : NasStatus
}

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val store = SettingsStore.get(app)
    val repo = MediaRepository(app)

    val settings: StateFlow<AppSettings> = store.settings

    private val _media = MutableStateFlow<List<MediaItem>>(emptyList())
    val media: StateFlow<List<MediaItem>> = _media

    private val _access = MutableStateFlow(MediaAccess.NONE)
    val access: StateFlow<MediaAccess> = _access

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading

    private val _nas = MutableStateFlow<NasStatus>(NasStatus.NotConfigured)
    val nas: StateFlow<NasStatus> = _nas

    private val _selected = MutableStateFlow<Set<Long>>(emptySet())
    val selected: StateFlow<Set<Long>> = _selected

    /** true: まだ NAS に無いものだけ表示する */
    val onlyNotBackedUp = MutableStateFlow(true)

    private var checkJob: Job? = null

    /** 画面が表示されるたびに呼ぶ (権限が変わった場合などに備えて読み直す) */
    fun onResume() {
        val newAccess = MediaRepository.access(getApplication())
        val changed = newAccess != _access.value
        _access.value = newAccess
        if (newAccess == MediaAccess.NONE) {
            _media.value = emptyList()
            return
        }
        if (changed || _media.value.isEmpty() || newAccess == MediaAccess.PARTIAL) {
            reloadMedia()
        }
    }

    fun reloadMedia() {
        viewModelScope.launch {
            _loading.value = true
            val items = withContext(Dispatchers.IO) { runCatching { repo.loadAll() }.getOrDefault(emptyList()) }
            _media.value = items
            _loading.value = false
            val ids = items.map { it.id }.toSet()
            _selected.update { it intersect ids }
            checkNas()
        }
    }

    /** NAS に接続して、どのファイルがバックアップ済みかを調べる */
    fun checkNas() {
        val s = settings.value
        if (!s.isComplete) {
            _nas.value = NasStatus.NotConfigured
            return
        }
        checkJob?.cancel()
        checkJob = viewModelScope.launch {
            _nas.value = NasStatus.Checking
            val items = _media.value
            _nas.value = withContext(Dispatchers.IO) {
                try {
                    SmbRemoteFs.connect(s.nasConfig(), timeoutSeconds = 15).use { fs ->
                        val engine = BackupEngine(fs, s.backupSettings())
                        val found = engine.findBackedUp(items.map { repo.toMediaFileLight(it) })
                        BackupController.backedUp.value = found
                        val space = fs.space()
                        NasStatus.Ok(space?.first, space?.second)
                    }
                } catch (e: Exception) {
                    NasStatus.Error(describeError(e))
                }
            }
            _selected.update { sel -> sel - BackupController.backedUp.value.keys }
        }
    }

    fun toggle(id: Long) = _selected.update { if (id in it) it - id else it + id }

    fun select(ids: Collection<Long>, on: Boolean) = _selected.update { if (on) it + ids else it - ids.toSet() }

    fun clearSelection() {
        _selected.value = emptySet()
    }

    fun startBackup() {
        val sel = _selected.value
        val items = _media.value.filter { it.id in sel }
        BackupController.start(getApplication(), items)
    }

    /** バックアップが終わったら、送れたものを選択から外す */
    fun onBackupFinished() {
        _selected.update { it - BackupController.backedUp.value.keys }
    }

    fun saveSettings(s: AppSettings) {
        val old = settings.value
        store.save(s)
        if (old.nasConfig() != s.nasConfig() || old.backupSettings() != s.backupSettings()) {
            BackupController.backedUp.value = emptyMap()
        }
        checkNas()
    }

    /** 設定画面の「接続テスト」 */
    suspend fun testConnection(s: AppSettings): Result<String> = withContext(Dispatchers.IO) {
        try {
            SmbRemoteFs.connect(s.nasConfig(), timeoutSeconds = 10).use { fs ->
                val base = s.backupSettings().baseDir
                // 保存先フォルダを作り、書き込めることを確認する
                val probe = listOf(base.trim('/'), ".nasbackup", "write-test").filter { it.isNotEmpty() }.joinToString("/")
                fs.mkdirs(probe.substringBeforeLast('/'))
                fs.openForWrite(probe).use { it.write(0, byteArrayOf(1), 1) }
                fs.delete(probe)
                val space = fs.space()
                val free = space?.let { "（空き ${formatBytes(it.first)} / ${formatBytes(it.second)}）" } ?: ""
                Result.success("接続できました$free")
            }
        } catch (e: Exception) {
            Result.failure(Exception(describeError(e)))
        }
    }
}

/** バックアップ済みかを調べるだけなので、ファイルは開かない */
private fun MediaRepository.toMediaFileLight(item: MediaItem) =
    io.github.masahiroc1203.nasbackup.core.MediaFile(item.id, item.name, item.size, item.takenAt) {
        throw IllegalStateException("not used")
    }

fun formatBytes(n: Long): String {
    if (n < 1024) return "$n B"
    val units = listOf("KB", "MB", "GB", "TB")
    var v = n / 1024.0
    var i = 0
    while (v >= 1024 && i < units.size - 1) {
        v /= 1024
        i++
    }
    return if (v < 10) "%.1f %s".format(v, units[i]) else "%.0f %s".format(v, units[i])
}
