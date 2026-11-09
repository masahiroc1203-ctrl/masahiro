package io.github.masahiroc1203.nasbackup

import android.content.Context
import androidx.core.content.edit
import io.github.masahiroc1203.nasbackup.core.BackupSettings
import io.github.masahiroc1203.nasbackup.core.Layout
import io.github.masahiroc1203.nasbackup.core.NasConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** NAS への接続と保存先の設定 */
data class AppSettings(
    val host: String = "",
    val share: String = "share",
    val baseDir: String = "SmartphoneBackup",
    val user: String = "",
    val password: String = "",
    val owner: String = "",
    val sortByDate: Boolean = true,
) {
    val isComplete: Boolean get() = cleanHost.isNotEmpty() && share.isNotBlank()

    /** "smb://192.168.1.50/" や "\\192.168.1.50" と入力されても使えるようにする */
    val cleanHost: String
        get() = host.trim().removePrefix("smb://").trim('/', '\\', ' ')

    fun nasConfig() = NasConfig(host = cleanHost, share = share.trim(), user = user.trim(), password = password)

    fun backupSettings() = BackupSettings(
        baseDir = baseDir,
        owner = owner,
        layout = if (sortByDate) Layout.DATE else Layout.FLAT,
    )

    /** 画面に表示する保存先の例 */
    fun destinationExample(): String {
        val parts = mutableListOf("\\\\${cleanHost.ifEmpty { "NAS" }}", share.trim().ifEmpty { "共有フォルダ" })
        baseDir.trim('/', '\\', ' ').takeIf { it.isNotEmpty() }?.let { parts += it.replace('/', '\\') }
        owner.trim().takeIf { it.isNotEmpty() }?.let { parts += it }
        if (sortByDate) parts += "2026\\2026-11"
        return parts.joinToString("\\") + "\\"
    }
}

/** 設定の保存 (アプリ専用の領域に保存され、ほかのアプリからは読めない) */
class SettingsStore private constructor(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    private val state = MutableStateFlow(load())
    val settings: StateFlow<AppSettings> = state

    private fun load() = AppSettings(
        host = prefs.getString("host", "") ?: "",
        share = prefs.getString("share", "share") ?: "share",
        baseDir = prefs.getString("baseDir", "SmartphoneBackup") ?: "SmartphoneBackup",
        user = prefs.getString("user", "") ?: "",
        password = prefs.getString("password", "") ?: "",
        owner = prefs.getString("owner", "") ?: "",
        sortByDate = prefs.getBoolean("sortByDate", true),
    )

    fun save(s: AppSettings) {
        prefs.edit {
            putString("host", s.host.trim())
            putString("share", s.share.trim())
            putString("baseDir", s.baseDir.trim())
            putString("user", s.user.trim())
            putString("password", s.password)
            putString("owner", s.owner.trim())
            putBoolean("sortByDate", s.sortByDate)
        }
        state.value = load()
    }

    companion object {
        @Volatile
        private var instance: SettingsStore? = null

        fun get(context: Context): SettingsStore =
            instance ?: synchronized(this) {
                instance ?: SettingsStore(context.applicationContext).also { instance = it }
            }
    }
}
