@file:OptIn(ExperimentalMaterial3Api::class)

package io.github.masahiroc1203.nasbackup.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import io.github.masahiroc1203.nasbackup.AppSettings
import io.github.masahiroc1203.nasbackup.MainViewModel
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(vm: MainViewModel, onClose: () -> Unit) {
    val initial = remember { vm.settings.value }
    var host by rememberSaveable { mutableStateOf(initial.host) }
    var share by rememberSaveable { mutableStateOf(initial.share) }
    var baseDir by rememberSaveable { mutableStateOf(initial.baseDir) }
    var user by rememberSaveable { mutableStateOf(initial.user) }
    var password by rememberSaveable { mutableStateOf(initial.password) }
    var owner by rememberSaveable { mutableStateOf(initial.owner) }
    var sortByDate by rememberSaveable { mutableStateOf(initial.sortByDate) }
    var testing by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<Result<String>?>(null) }
    val scope = rememberCoroutineScope()

    val current = AppSettings(host, share, baseDir, user, password, owner, sortByDate)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("NASの設定") },
                navigationIcon = {
                    IconButton(onClick = onClose) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "戻る")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "LS720D などの NAS の共有フォルダに直接保存します。スマホと NAS を同じ Wi-Fi につないで使ってください。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Field("NASのIPアドレス", host, { host = it }, "例: 192.168.1.50", KeyboardType.Uri,
                help = "NAS Navigator2 などで確認できます")
            Field("共有フォルダ名", share, { share = it }, "例: share")
            Field("保存先フォルダ", baseDir, { baseDir = it }, "例: SmartphoneBackup",
                help = "共有フォルダの中に作られます")
            Field("ユーザー名", user, { user = it }, "アクセス制限をしていなければ空のまま")
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("パスワード") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth(),
            )
            Field("保存先フォルダ名（家族で使うとき）", owner, { owner = it }, "例: papa",
                help = "名前を入れると人ごとにフォルダを分けて保存します")
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("撮影年月ごとにフォルダ分け", Modifier.weight(1f))
                Switch(checked = sortByDate, onCheckedChange = { sortByDate = it })
            }
            Text(
                "保存先: ${current.destinationExample()}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(
                    enabled = current.isComplete && !testing,
                    onClick = {
                        testing = true
                        testResult = null
                        scope.launch {
                            testResult = vm.testConnection(current)
                            testing = false
                        }
                    },
                ) { Text("接続テスト") }
                if (testing) CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
            }
            testResult?.let { r ->
                Text(
                    r.fold({ "✓ $it" }, { "✕ ${it.message}" }),
                    color = if (r.isSuccess) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                )
            }

            Spacer(Modifier.height(4.dp))
            Button(
                enabled = current.isComplete,
                onClick = {
                    vm.saveSettings(current)
                    onClose()
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("保存") }
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    placeholder: String,
    keyboardType: KeyboardType = KeyboardType.Text,
    help: String? = null,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        placeholder = { Text(placeholder) },
        supportingText = if (help != null) {
            { Text(help) }
        } else {
            null
        },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = ImeAction.Next),
        modifier = Modifier.fillMaxWidth(),
    )
}
