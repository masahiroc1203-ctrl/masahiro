@file:OptIn(ExperimentalMaterial3Api::class)

package io.github.masahiroc1203.nasbackup.ui

import android.Manifest
import android.os.Build
import android.util.LruCache
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.masahiroc1203.nasbackup.BackupController
import io.github.masahiroc1203.nasbackup.BackupProgress
import io.github.masahiroc1203.nasbackup.MainViewModel
import io.github.masahiroc1203.nasbackup.MediaAccess
import io.github.masahiroc1203.nasbackup.MediaItem
import io.github.masahiroc1203.nasbackup.MediaRepository
import io.github.masahiroc1203.nasbackup.NasStatus
import io.github.masahiroc1203.nasbackup.formatBytes
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.ZoneId

@Composable
fun MainScreen(vm: MainViewModel, openSettings: () -> Unit) {
    val media by vm.media.collectAsStateWithLifecycle()
    val access by vm.access.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val nas by vm.nas.collectAsStateWithLifecycle()
    val selected by vm.selected.collectAsStateWithLifecycle()
    val onlyNew by vm.onlyNotBackedUp.collectAsStateWithLifecycle()
    val backedUp by BackupController.backedUp.collectAsStateWithLifecycle()
    val failures by BackupController.failures.collectAsStateWithLifecycle()
    val progress by BackupController.progress.collectAsStateWithLifecycle()

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        vm.onResume()
    }
    val notificationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        vm.startBackup()
    }

    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.onResume() }
    LaunchedEffect(progress.finished) {
        if (progress.finished) vm.onBackupFinished()
    }

    val visible = remember(media, backedUp, onlyNew) {
        if (onlyNew) media.filter { it.id !in backedUp } else media
    }
    val sections = remember(visible) { groupByMonth(visible) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("NASバックアップ") },
                actions = {
                    IconButton(onClick = { vm.reloadMedia() }, enabled = !progress.running) {
                        Icon(Icons.Filled.Refresh, contentDescription = "再読み込み")
                    }
                    IconButton(onClick = openSettings, enabled = !progress.running) {
                        Icon(Icons.Filled.Settings, contentDescription = "設定")
                    }
                },
            )
        },
        bottomBar = {
            BottomPanel(
                progress = progress,
                selectedCount = selected.size,
                selectedBytes = remember(selected, media) { media.filter { it.id in selected }.sumOf { it.size } },
                canStart = nas is NasStatus.Ok,
                onStart = {
                    if (Build.VERSION.SDK_INT >= 33) {
                        notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    } else {
                        vm.startBackup()
                    }
                },
                onStop = { BackupController.stop() },
                onDismiss = { BackupController.dismissResult() },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            NasStatusCard(nas, onRetry = { vm.checkNas() }, openSettings = openSettings)

            when {
                access == MediaAccess.NONE -> PermissionCard { permissionLauncher.launch(MediaRepository.permissions()) }
                loading && media.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                else -> {
                    if (access == MediaAccess.PARTIAL) {
                        Text(
                            "選んだ写真だけ表示しています。ほかの写真も表示するには「すべて許可」してください。",
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier
                                .padding(horizontal = 16.dp)
                                .clickable { permissionLauncher.launch(MediaRepository.permissions()) },
                        )
                    }
                    FilterRow(
                        onlyNew = onlyNew,
                        onToggle = { vm.onlyNotBackedUp.value = !onlyNew },
                        visibleCount = visible.size,
                        allSelected = visible.isNotEmpty() && visible.all { it.id in selected || it.id in backedUp },
                        onSelectAll = { on -> vm.select(visible.filter { it.id !in backedUp }.map { it.id }, on) },
                        enabled = !progress.running,
                    )
                    if (visible.isEmpty()) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(
                                if (media.isEmpty()) "写真・動画がありません" else "すべてバックアップ済みです 🎉",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    } else {
                        MediaGrid(
                            sections = sections,
                            repo = vm.repo,
                            selected = selected,
                            backedUp = backedUp,
                            failures = failures,
                            enabled = !progress.running,
                            onToggle = vm::toggle,
                            onSelectMonth = { ids, on -> vm.select(ids, on) },
                        )
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- NAS の状態

@Composable
private fun NasStatusCard(nas: NasStatus, onRetry: () -> Unit, openSettings: () -> Unit) {
    val (text, isError) = when (nas) {
        NasStatus.NotConfigured -> "NASが設定されていません" to true
        NasStatus.Checking -> "NASに接続しています…" to false
        is NasStatus.Ok -> {
            val space = if (nas.freeBytes != null && nas.totalBytes != null) {
                "（空き ${formatBytes(nas.freeBytes)} / ${formatBytes(nas.totalBytes)}）"
            } else {
                ""
            }
            "NASに接続しました$space" to false
        }
        is NasStatus.Error -> nas.message to true
    }
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceVariant,
        ),
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            when (nas) {
                NasStatus.Checking -> CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                is NasStatus.Ok -> Icon(Icons.Filled.CheckCircle, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp))
                else -> Icon(Icons.Filled.Warning, null, tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(18.dp))
            }
            Text(text, Modifier.weight(1f).padding(start = 10.dp), style = MaterialTheme.typography.bodyMedium)
            when (nas) {
                NasStatus.NotConfigured -> TextButton(onClick = openSettings) { Text("設定") }
                is NasStatus.Error -> TextButton(onClick = onRetry) { Text("再試行") }
                else -> Unit
            }
        }
    }
}

@Composable
private fun PermissionCard(onRequest: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("写真と動画へのアクセスを許可してください", style = MaterialTheme.typography.titleMedium)
        Text(
            "バックアップするファイルを選ぶために使います。写真の位置情報もそのまま NAS に保存されます。",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Button(onClick = onRequest) { Text("許可する") }
    }
}

@Composable
private fun FilterRow(
    onlyNew: Boolean,
    onToggle: () -> Unit,
    visibleCount: Int,
    allSelected: Boolean,
    onSelectAll: (Boolean) -> Unit,
    enabled: Boolean,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        FilterChip(selected = onlyNew, onClick = onToggle, label = { Text("未バックアップのみ") })
        Text(
            "${visibleCount}件",
            Modifier
                .weight(1f)
                .padding(start = 12.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        TextButton(onClick = { onSelectAll(!allSelected) }, enabled = enabled && visibleCount > 0) {
            Text(if (allSelected) "選択解除" else "すべて選択")
        }
    }
}

// ---------------------------------------------------------------- 写真の一覧

private data class MonthSection(val title: String, val items: List<MediaItem>)

private fun groupByMonth(items: List<MediaItem>): List<MonthSection> {
    val zone = ZoneId.systemDefault()
    return items.groupBy {
        val d = Instant.ofEpochMilli(it.takenAt).atZone(zone)
        "${d.year}年${d.monthValue}月"
    }.map { (title, list) -> MonthSection(title, list) }
}

private val thumbCache = LruCache<Long, ImageBitmap>(400)

@Composable
private fun MediaGrid(
    sections: List<MonthSection>,
    repo: MediaRepository,
    selected: Set<Long>,
    backedUp: Map<Long, String>,
    failures: Map<Long, String>,
    enabled: Boolean,
    onToggle: (Long) -> Unit,
    onSelectMonth: (List<Long>, Boolean) -> Unit,
) {
    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = 96.dp),
        contentPadding = PaddingValues(start = 12.dp, end = 12.dp, bottom = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        for (section in sections) {
            item(key = "h-${section.title}", span = { GridItemSpan(maxLineSpan) }) {
                val ids = section.items.filter { it.id !in backedUp }.map { it.id }
                val all = ids.isNotEmpty() && ids.all { it in selected }
                Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(section.title, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                    if (ids.isNotEmpty()) {
                        TextButton(onClick = { onSelectMonth(ids, !all) }, enabled = enabled) {
                            Text(if (all) "解除" else "この月を選択")
                        }
                    }
                }
            }
            items(section.items, key = { it.id }) { item ->
                MediaCell(
                    item = item,
                    repo = repo,
                    selected = item.id in selected,
                    backedUp = item.id in backedUp,
                    failed = item.id in failures,
                    onClick = { if (enabled && item.id !in backedUp) onToggle(item.id) },
                )
            }
        }
    }
}

@Composable
private fun MediaCell(
    item: MediaItem,
    repo: MediaRepository,
    selected: Boolean,
    backedUp: Boolean,
    failed: Boolean,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(6.dp)
    val bitmap by produceState<ImageBitmap?>(initialValue = thumbCache.get(item.id), item.id) {
        if (value == null) {
            value = withContext(Dispatchers.IO) {
                repo.thumbnail(item, 256)?.asImageBitmap()?.also { thumbCache.put(item.id, it) }
            }
        }
    }
    Box(
        Modifier
            .aspectRatio(1f)
            .clip(shape)
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .then(if (selected) Modifier.border(3.dp, MaterialTheme.colorScheme.primary, shape) else Modifier)
            .clickable(onClick = onClick),
    ) {
        bitmap?.let {
            Image(it, contentDescription = item.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        }
        if (item.isVideo) {
            Row(
                Modifier
                    .align(Alignment.BottomStart)
                    .padding(4.dp)
                    .background(Color(0x99000000), RoundedCornerShape(4.dp))
                    .padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Filled.PlayArrow, null, tint = Color.White, modifier = Modifier.size(12.dp))
                Text(formatDuration(item.durationMs), color = Color.White, style = MaterialTheme.typography.labelSmall)
            }
        }
        when {
            backedUp -> Box(Modifier.fillMaxSize().background(Color(0x66000000))) {
                Text(
                    "保存済み",
                    color = Color.White,
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.align(Alignment.Center),
                )
            }
            selected -> Icon(
                Icons.Filled.CheckCircle,
                contentDescription = "選択中",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(4.dp)
                    .background(Color.White, CircleShape)
                    .size(22.dp),
            )
            failed -> Icon(
                Icons.Filled.Warning,
                contentDescription = "失敗",
                tint = MaterialTheme.colorScheme.error,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(4.dp)
                    .size(20.dp),
            )
        }
    }
}

private fun formatDuration(ms: Long): String {
    val s = ms / 1000
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s / 60 % 60, s % 60) else "%d:%02d".format(s / 60, s % 60)
}

// ---------------------------------------------------------------- 下部の操作パネル

@Composable
private fun BottomPanel(
    progress: BackupProgress,
    selectedCount: Int,
    selectedBytes: Long,
    canStart: Boolean,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onDismiss: () -> Unit,
) {
    Surface(tonalElevation = 3.dp, shadowElevation = 8.dp) {
        Column(
            Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            when {
                progress.running -> {
                    Text(
                        "送信中 ${minOf(progress.processed + 1, progress.total)}/${progress.total}件 · " +
                            "${formatBytes(progress.sentBytes)} / ${formatBytes(progress.totalBytes)}",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    LinearProgressIndicator(progress = { progress.fraction }, modifier = Modifier.fillMaxWidth())
                    Text(
                        progress.message ?: progress.currentName.orEmpty(),
                        style = MaterialTheme.typography.bodySmall,
                        color = if (progress.message != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        "画面を消したり他のアプリに切り替えても送信は続きます",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    OutlinedButton(onClick = onStop, modifier = Modifier.fillMaxWidth()) { Text("停止") }
                }
                progress.finished -> {
                    val title = when {
                        progress.fatalError != null -> "バックアップできませんでした"
                        progress.cancelled -> "停止しました"
                        progress.failed > 0 -> "終わりました（失敗 ${progress.failed}件）"
                        else -> "バックアップが完了しました"
                    }
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    Text(
                        progress.fatalError ?: "新規 ${progress.uploaded}件・保存済み ${progress.skipped}件",
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (progress.fatalError != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) { Text("閉じる") }
                        if (selectedCount > 0) {
                            Button(onClick = onStart, enabled = canStart, modifier = Modifier.weight(1f)) { Text("続きを送る") }
                        }
                    }
                }
                else -> {
                    Button(
                        onClick = onStart,
                        enabled = canStart && selectedCount > 0,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            if (selectedCount > 0) "バックアップ開始（${selectedCount}件・${formatBytes(selectedBytes)}）" else "写真・動画を選んでください",
                            modifier = Modifier.padding(vertical = 6.dp),
                        )
                    }
                }
            }
        }
    }
}
