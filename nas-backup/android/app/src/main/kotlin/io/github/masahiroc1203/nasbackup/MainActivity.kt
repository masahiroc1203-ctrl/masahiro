package io.github.masahiroc1203.nasbackup

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.masahiroc1203.nasbackup.ui.MainScreen
import io.github.masahiroc1203.nasbackup.ui.NasBackupTheme
import io.github.masahiroc1203.nasbackup.ui.SettingsScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            NasBackupTheme {
                App()
            }
        }
    }
}

@Composable
private fun App() {
    val vm: MainViewModel = viewModel()
    // 初回 (NAS が未設定) は設定画面から始める
    var showSettings by rememberSaveable { mutableStateOf(!vm.settings.value.isComplete) }

    if (showSettings) {
        BackHandler { showSettings = false }
        SettingsScreen(vm, onClose = { showSettings = false })
    } else {
        MainScreen(vm, openSettings = { showSettings = true })
    }
}
