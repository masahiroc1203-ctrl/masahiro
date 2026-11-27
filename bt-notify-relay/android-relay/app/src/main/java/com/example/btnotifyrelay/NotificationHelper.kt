package com.example.btnotifyrelay

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import java.util.concurrent.atomic.AtomicInteger

object NotificationHelper {
    const val CHANNEL_SERVICE_ID = "bt_relay_service_channel"
    const val CHANNEL_RELAY_ID = "pc_relay_channel"
    private val notificationIdCounter = AtomicInteger(1000)

    fun createChannels(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(NotificationManager::class.java)

            val serviceChannel = NotificationChannel(
                CHANNEL_SERVICE_ID,
                "PC連携バックグラウンド待機",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "PCからのBluetooth通知受信サービスの状態表示"
            }

            val relayChannel = NotificationChannel(
                CHANNEL_RELAY_ID,
                "PC転送通知",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "PCから転送された通知（スマートバンド転送対象）"
                enableVibration(true)
            }

            manager.createNotificationChannel(serviceChannel)
            manager.createNotificationChannel(relayChannel)
        }
    }

    fun buildServiceNotification(context: Context, statusText: String): Notification {
        return NotificationCompat.Builder(context, CHANNEL_SERVICE_ID)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentTitle("BT Notify Relay")
            .setContentText(statusText)
            .setOngoing(true)
            .build()
    }

    fun showRelayedNotification(context: Context, appName: String, title: String, body: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ActivityCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        val id = notificationIdCounter.incrementAndGet()
        val displayTitle = if (appName.isNotBlank()) "[$appName] $title" else title

        val notification = NotificationCompat.Builder(context, CHANNEL_RELAY_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(displayTitle)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setGroup("pc_relay_group_$id") // 個別IDにしてバンド側で1件ずつ振動させる
            .setAutoCancel(true)
            .build()

        NotificationManagerCompat.from(context).notify(id, notification)
    }
}
