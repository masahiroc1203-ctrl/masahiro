package com.example.btnotifyrelay

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.util.concurrent.atomic.AtomicInteger

object NotificationHelper {
    const val CHANNEL_SERVICE_ID = "bt_relay_service_channel"
    const val CHANNEL_RELAY_ID = "pc_relay_channel"
    private val notificationIdCounter = AtomicInteger(1000)

    fun createChannels(context: Context) {
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

    /** 通知を出せる状態か (権限・アプリの通知設定・転送用チャンネルの設定) */
    fun canPostRelayNotifications(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return false
        }
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        val channel = context.getSystemService(NotificationManager::class.java).getNotificationChannel(CHANNEL_RELAY_ID)
        return channel == null || channel.importance != NotificationManager.IMPORTANCE_NONE
    }

    fun buildServiceNotification(context: Context, statusText: String): Notification {
        val openApp = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(context, CHANNEL_SERVICE_ID)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setContentTitle("BT Notify Relay")
            .setContentText(statusText)
            .setContentIntent(openApp)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }

    /** PC から届いた通知を出す。出せなかったら false */
    fun showRelayedNotification(
        context: Context,
        appName: String,
        title: String,
        body: String,
        timestampSeconds: Long? = null,
    ): Boolean {
        if (!canPostRelayNotifications(context)) return false

        val id = notificationIdCounter.incrementAndGet()
        val displayTitle = if (appName.isNotBlank()) "[$appName] $title" else title

        val builder = NotificationCompat.Builder(context, CHANNEL_RELAY_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(displayTitle)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setGroup("pc_relay_group_$id") // 個別IDにしてバンド側で1件ずつ振動させる
            .setAutoCancel(true)
        if (timestampSeconds != null && timestampSeconds > 0) {
            builder.setWhen(timestampSeconds * 1000).setShowWhen(true)
        }

        return try {
            NotificationManagerCompat.from(context).notify(id, builder.build())
            true
        } catch (e: SecurityException) {
            false
        }
    }
}
