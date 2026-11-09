package io.github.masahiroc1203.nasbackup

import android.Manifest
import android.content.ContentUris
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.util.Size
import androidx.core.content.ContextCompat
import io.github.masahiroc1203.nasbackup.core.MediaFile
import java.io.IOException
import java.io.InputStream

/** スマホの写真・動画 1 件 */
data class MediaItem(
    val id: Long,
    val uri: Uri,
    val name: String,
    val size: Long,
    /** 撮影日時 (UNIX ミリ秒) */
    val takenAt: Long,
    val isVideo: Boolean,
    val durationMs: Long,
)

enum class MediaAccess { FULL, PARTIAL, NONE }

/** 端末の写真・動画を MediaStore から読む */
class MediaRepository(context: Context) {
    private val context = context.applicationContext
    private val resolver = context.contentResolver

    fun loadAll(): List<MediaItem> {
        val items = ArrayList<MediaItem>()
        query(MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL), isVideo = false, items)
        query(MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL), isVideo = true, items)
        items.sortByDescending { it.takenAt }
        return items
    }

    private fun query(collection: Uri, isVideo: Boolean, out: MutableList<MediaItem>) {
        val projection = arrayOf(
            MediaStore.MediaColumns._ID,
            MediaStore.MediaColumns.DISPLAY_NAME,
            MediaStore.MediaColumns.SIZE,
            MediaStore.MediaColumns.DATE_TAKEN,
            MediaStore.MediaColumns.DATE_MODIFIED,
            MediaStore.MediaColumns.DURATION,
        )
        resolver.query(collection, projection, null, null, null)?.use { c ->
            val idCol = c.getColumnIndexOrThrow(MediaStore.MediaColumns._ID)
            val nameCol = c.getColumnIndexOrThrow(MediaStore.MediaColumns.DISPLAY_NAME)
            val sizeCol = c.getColumnIndexOrThrow(MediaStore.MediaColumns.SIZE)
            val takenCol = c.getColumnIndexOrThrow(MediaStore.MediaColumns.DATE_TAKEN)
            val modCol = c.getColumnIndexOrThrow(MediaStore.MediaColumns.DATE_MODIFIED)
            val durCol = c.getColumnIndexOrThrow(MediaStore.MediaColumns.DURATION)
            while (c.moveToNext()) {
                val id = c.getLong(idCol)
                val taken = c.getLong(takenCol).takeIf { it > 0 } ?: (c.getLong(modCol) * 1000)
                out += MediaItem(
                    id = id,
                    uri = ContentUris.withAppendedId(collection, id),
                    name = c.getString(nameCol) ?: "file_$id",
                    size = c.getLong(sizeCol),
                    takenAt = taken,
                    isVideo = isVideo,
                    durationMs = if (isVideo) c.getLong(durCol) else 0,
                )
            }
        }
    }

    fun thumbnail(item: MediaItem, px: Int): Bitmap? =
        runCatching { resolver.loadThumbnail(item.uri, Size(px, px), null) }.getOrNull()

    /** NAS へ送るためのファイル。位置情報も含めた元のファイルを読む。 */
    fun toMediaFile(item: MediaItem): MediaFile {
        var size = item.size
        if (size <= 0) {
            size = resolver.openFileDescriptor(item.uri, "r")?.use { it.statSize } ?: 0
        }
        return MediaFile(item.id, item.name, size, item.takenAt) { open(item) }
    }

    private fun open(item: MediaItem): InputStream {
        if (hasPermission(Manifest.permission.ACCESS_MEDIA_LOCATION)) {
            // 位置情報 (GPS) を消さずに読む
            try {
                resolver.openInputStream(MediaStore.setRequireOriginal(item.uri))?.let { return it }
            } catch (e: SecurityException) {
                // 許可されていなければ通常の読み方にする
            } catch (e: UnsupportedOperationException) {
                // 同上
            }
        }
        return resolver.openInputStream(item.uri) ?: throw IOException("ファイルを開けません: ${item.name}")
    }

    private fun hasPermission(p: String) =
        ContextCompat.checkSelfPermission(context, p) == PackageManager.PERMISSION_GRANTED

    companion object {
        /** 写真・動画の読み取りに必要な権限 */
        fun permissions(): Array<String> = when {
            Build.VERSION.SDK_INT >= 34 -> arrayOf(
                Manifest.permission.READ_MEDIA_IMAGES,
                Manifest.permission.READ_MEDIA_VIDEO,
                Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED,
                Manifest.permission.ACCESS_MEDIA_LOCATION,
            )
            Build.VERSION.SDK_INT >= 33 -> arrayOf(
                Manifest.permission.READ_MEDIA_IMAGES,
                Manifest.permission.READ_MEDIA_VIDEO,
                Manifest.permission.ACCESS_MEDIA_LOCATION,
            )
            else -> arrayOf(
                Manifest.permission.READ_EXTERNAL_STORAGE,
                Manifest.permission.ACCESS_MEDIA_LOCATION,
            )
        }

        fun access(context: Context): MediaAccess {
            fun granted(p: String) = ContextCompat.checkSelfPermission(context, p) == PackageManager.PERMISSION_GRANTED
            return when {
                Build.VERSION.SDK_INT >= 33 &&
                    granted(Manifest.permission.READ_MEDIA_IMAGES) && granted(Manifest.permission.READ_MEDIA_VIDEO) -> MediaAccess.FULL
                Build.VERSION.SDK_INT >= 34 &&
                    granted(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED) -> MediaAccess.PARTIAL
                Build.VERSION.SDK_INT < 33 && granted(Manifest.permission.READ_EXTERNAL_STORAGE) -> MediaAccess.FULL
                else -> MediaAccess.NONE
            }
        }
    }
}
