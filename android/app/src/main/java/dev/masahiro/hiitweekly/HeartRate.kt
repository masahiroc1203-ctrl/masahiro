package dev.masahiro.hiitweekly

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.util.Log
import org.json.JSONObject
import java.util.UUID

// Bluetooth の心拍センサー（Heart Rate サービス 0x180D）から心拍数を受け取る。
// Xiaomi Smart Band の「心拍数を共有」や胸ベルト型の心拍計が、同じ形式で送ってくる。
// 結果は emit(種類, 内容) で Web 側（js/hr.js）に渡す。権限の確認は呼ぶ側（MainActivity）で済ませておくこと。
// 公開している関数はすべてメインスレッドから呼ぶ
@SuppressLint("MissingPermission")
class HeartRate(private val context: Context, private val emit: (type: String, data: JSONObject) -> Unit) {
    private val adapter: BluetoothAdapter? = context.getSystemService(BluetoothManager::class.java)?.adapter
    private val main = Handler(Looper.getMainLooper())
    private var gatt: BluetoothGatt? = null
    private var wanted: String? = null // つないでおきたい相手。切れたらつなぎ直す
    private var scanning = false
    private val seen = HashMap<String, Boolean>() // さがして見つけた機器 → 心拍計だと名乗っているか

    val ready get() = adapter?.isEnabled == true

    private fun status(value: String) = emit("status", JSONObject().put("status", value))

    private fun fail(message: String) {
        Log.w(TAG, message)
        disconnect()
        emit("error", JSONObject().put("message", message))
    }

    // ───── さがす ─────
    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            // 名前の無いものは選びようがないので出さない
            val name = result.scanRecord?.deviceName ?: result.device.name ?: return
            val hr = result.scanRecord?.serviceUuids?.contains(ParcelUuid(HR_SERVICE)) == true
            val address = result.device.address
            if (seen[address] == true || seen[address] == hr) return
            seen[address] = hr
            emit("device", JSONObject().put("id", address).put("name", name).put("hr", hr))
        }

        override fun onScanFailed(errorCode: Int) {
            scanning = false
            emit("scan", JSONObject().put("on", false))
            emit("error", JSONObject().put("message", "機器をさがせませんでした（$errorCode）"))
        }
    }
    private val stopScanLater = Runnable { stopScan() }

    fun scan() {
        if (scanning) return
        val scanner = adapter?.bluetoothLeScanner ?: return
        seen.clear()
        scanning = true
        // 心拍計だと名乗らずに電波を出す機器もあるので、種類では絞らず全部を受ける
        scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), scanCallback)
        emit("scan", JSONObject().put("on", true))
        main.postDelayed(stopScanLater, SCAN_MS)
    }

    fun stopScan() {
        main.removeCallbacks(stopScanLater)
        if (!scanning) return
        scanning = false
        runCatching { adapter?.bluetoothLeScanner?.stopScan(scanCallback) }
        emit("scan", JSONObject().put("on", false))
    }

    // ───── つなぐ ─────
    fun connect(address: String) {
        stopScan()
        release()
        val device = runCatching { adapter?.getRemoteDevice(address) }.getOrNull() ?: return
        wanted = address
        status("connecting")
        gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
    }

    fun disconnect() {
        release()
        status("off")
    }

    // 画面を閉じるとき用。Web 側には知らせない
    fun release() {
        wanted = null
        main.removeCallbacks(retry)
        gatt?.let {
            it.disconnect()
            it.close()
        }
        gatt = null
    }

    // 切れたとき：相手が電波の届くところへ戻ってきたら自動でつながるように待つ（autoConnect = true）
    private val retry: Runnable = Runnable {
        val address = wanted ?: return@Runnable
        if (!ready) return@Runnable fail("Bluetooth がオフになりました")
        gatt = adapter?.getRemoteDevice(address)?.connectGatt(context, true, callback, BluetoothDevice.TRANSPORT_LE)
    }

    // 通知は Bluetooth のスレッドに届くので、状態を触る処理はメインスレッドに回す
    private val callback: BluetoothGattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            main.post {
                if (g !== gatt) return@post // もう使っていない接続からの通知
                if (newState == BluetoothProfile.STATE_CONNECTED) {
                    g.discoverServices()
                } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                    Log.i(TAG, "disconnected (status $status)")
                    g.close()
                    gatt = null
                    if (wanted == null) return@post
                    status("connecting")
                    main.postDelayed(retry, RETRY_MS)
                }
            }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            main.post {
                if (g !== gatt) return@post
                val ch = g.getService(HR_SERVICE)?.getCharacteristic(HR_MEASUREMENT)
                val cccd = ch?.getDescriptor(CCCD)
                if (ch == null || cccd == null) {
                    return@post fail("この機器は心拍数を送っていません。バンドの「心拍数を共有」をオンにしてください")
                }
                g.setCharacteristicNotification(ch, true)
                if (Build.VERSION.SDK_INT >= 33) {
                    g.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                } else {
                    @Suppress("DEPRECATION")
                    cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                    @Suppress("DEPRECATION")
                    g.writeDescriptor(cccd)
                }
            }
        }

        override fun onDescriptorWrite(g: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            main.post {
                if (g !== gatt) return@post
                if (status == BluetoothGatt.GATT_SUCCESS) status("on")
                else fail("心拍数の受信を始められませんでした（$status）")
            }
        }

        // Android 13 以降
        override fun onCharacteristicChanged(g: BluetoothGatt, ch: BluetoothGattCharacteristic, value: ByteArray) = data(ch, value)

        @Deprecated("Android 12 以前だけで使う")
        override fun onCharacteristicChanged(g: BluetoothGatt, ch: BluetoothGattCharacteristic) {
            @Suppress("DEPRECATION")
            data(ch, ch.value ?: return)
        }
    }

    // 中身の読み取りは Web 側（js/hr.js の parseHeartRate）で行う
    private fun data(ch: BluetoothGattCharacteristic, value: ByteArray) {
        if (ch.uuid != HR_MEASUREMENT) return
        emit("data", JSONObject().put("hex", value.joinToString("") { "%02x".format(it) }))
    }

    private companion object {
        const val TAG = "HiitWeekly"
        const val SCAN_MS = 15_000L
        const val RETRY_MS = 1_000L
        val HR_SERVICE: UUID = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb")
        val HR_MEASUREMENT: UUID = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
        val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
    }
}
