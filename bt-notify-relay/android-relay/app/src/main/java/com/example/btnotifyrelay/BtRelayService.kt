package com.example.btnotifyrelay

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationManager
import android.app.Service
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothServerSocket
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import java.io.IOException
import java.util.UUID
import kotlin.concurrent.thread

/**
 * PC からの RFCOMM 接続を待ち受ける常駐サービス。
 *
 * サーバーソケットは開いたままにして、新しい接続が来たら古い接続を閉じて乗り換える。
 * PC がスリープから戻ったときなど、スマホ側が古い接続の切断に気づく前でも、すぐつなぎ直せる。
 */
class BtRelayService : Service() {

    companion object {
        val SERVICE_UUID: UUID = UUID.fromString(RelayProtocol.SERVICE_UUID)
        const val SERVICE_NAME = "BtNotifyRelay"
        const val FOREGROUND_ID = 1

        @Volatile
        var currentStatus: String = "停止中"
            private set

        @Volatile
        var isRunning: Boolean = false
            private set

        @Volatile
        var onStatusChanged: ((String) -> Unit)? = null

        fun hasBluetoothPermission(context: Context): Boolean =
            Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
    }

    @Volatile
    private var running = false

    @Volatile
    private var serverSocket: BluetoothServerSocket? = null

    @Volatile
    private var clientSocket: BluetoothSocket? = null
    private var acceptThread: Thread? = null

    override fun onCreate() {
        super.onCreate()
        NotificationHelper.createChannels(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (running) return START_STICKY

        // Android 14 以降、connectedDevice の常駐には「付近のデバイス」の権限が要る
        if (!hasBluetoothPermission(this)) {
            setStatus("エラー: 「付近のデバイス」の権限がありません")
            stopSelf()
            return START_NOT_STICKY
        }

        try {
            val notification = NotificationHelper.buildServiceNotification(this, "PCからの接続を待機中...")
            ServiceCompat.startForeground(
                this, FOREGROUND_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            )
        } catch (e: RuntimeException) {
            // 権限が無い・バックグラウンドからの起動が許されない、など
            setStatus("エラー: 常駐を開始できません (${e.javaClass.simpleName})")
            stopSelf()
            return START_NOT_STICKY
        }

        running = true
        isRunning = true
        setStatus("PCからの接続を待機中...")
        acceptThread = thread(name = "bt-relay-accept") { acceptLoop() }
        return START_STICKY
    }

    private fun setStatus(status: String) {
        currentStatus = status
        if (running) {
            getSystemService(NotificationManager::class.java)
                .notify(FOREGROUND_ID, NotificationHelper.buildServiceNotification(this, status))
        }
        onStatusChanged?.invoke(status)
    }

    // 権限は onStartCommand で確認済み (途中で取り消されたら SecurityException で止まる)
    @SuppressLint("MissingPermission")
    private fun acceptLoop() {
        val adapter: BluetoothAdapter = getSystemService(BluetoothManager::class.java)?.adapter ?: run {
            setStatus("エラー: Bluetooth非対応端末")
            stopSelf()
            return
        }

        while (running) {
            try {
                if (!adapter.isEnabled) {
                    setStatus("Bluetooth がオフです。オンにすると待ち受けを再開します")
                    sleepQuietly(3000)
                    continue
                }

                val server = adapter.listenUsingRfcommWithServiceRecord(SERVICE_NAME, SERVICE_UUID)
                serverSocket = server
                if (clientSocket == null) setStatus("PCからの接続を待機中...")
                try {
                    while (running) {
                        val socket = server.accept() // 次の接続まで止まる。Bluetooth オフやサービス停止で IOException
                        val previous = clientSocket
                        clientSocket = socket
                        closeQuietly(previous) // PC がつなぎ直してきたら古い接続は捨てる
                        thread(name = "bt-relay-client") { handleClient(socket) }
                    }
                } finally {
                    closeQuietly(server)
                    serverSocket = null
                }
            } catch (e: SecurityException) {
                setStatus("エラー: Bluetooth接続権限がありません")
                stopSelf()
                return
            } catch (e: IOException) {
                if (running) {
                    setStatus("待ち受けを再開します (${e.message ?: "IOException"})")
                    sleepQuietly(2000)
                }
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun handleClient(socket: BluetoothSocket) {
        val deviceName = try {
            socket.remoteDevice?.name ?: "PC"
        } catch (_: SecurityException) {
            "PC"
        }
        setStatus("接続中: $deviceName")

        try {
            RelayProtocol.serve(socket.inputStream, socket.outputStream) { message ->
                if (message is RelayMessage.Notification) {
                    val shown = NotificationHelper.showRelayedNotification(
                        this, message.appName, message.title, message.body, message.timestamp
                    )
                    if (!shown) setStatus("接続中: $deviceName（通知が許可されていないため表示できません）")
                }
            }
        } catch (_: IOException) {
            // 切断
        } finally {
            closeQuietly(socket)
            if (clientSocket === socket) {
                clientSocket = null
                if (running) setStatus("PCからの接続を待機中...（$deviceName と切断）")
            }
        }
    }

    override fun onDestroy() {
        running = false
        isRunning = false
        closeQuietly(clientSocket)
        closeQuietly(serverSocket)
        acceptThread?.interrupt()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        // ここで notify すると、消せない「停止中」の通知が残るので、状態だけ更新する
        setStatus("停止中")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun closeQuietly(closeable: java.io.Closeable?) {
        try {
            closeable?.close()
        } catch (_: IOException) {
        }
    }

    private fun sleepQuietly(millis: Long) {
        try {
            Thread.sleep(millis)
        } catch (_: InterruptedException) {
        }
    }
}
