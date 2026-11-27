package com.example.btnotifyrelay

import org.json.JSONException
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStream
import java.io.InputStreamReader
import java.io.OutputStream
import java.io.OutputStreamWriter

/** PC から届くメッセージ (docs/spec.md の 3 章) */
sealed interface RelayMessage {
    data class Notification(
        val id: String,
        val appName: String,
        val title: String,
        val body: String,
        val timestamp: Long?,
    ) : RelayMessage

    data class Ping(val timestamp: Long?) : RelayMessage
    data class Pong(val timestamp: Long?) : RelayMessage
    data class Unknown(val type: String) : RelayMessage
}

/**
 * UTF-8 の改行区切り JSON の読み書き。Bluetooth に依存しないので、単体テストできる。
 */
object RelayProtocol {
    const val SERVICE_UUID = "8ce255c0-200a-11e0-ac64-0800200c9a66"
    private const val MAX_LINE_CHARS = 64 * 1024

    /** 1 行を読む。JSON でなければ null */
    fun parse(line: String): RelayMessage? {
        val json = try {
            JSONObject(line)
        } catch (e: JSONException) {
            return null
        }
        val timestamp = if (json.has("timestamp")) json.optLong("timestamp") else null
        return when (val type = json.optString("type")) {
            "notification" -> RelayMessage.Notification(
                id = json.optString("id"),
                appName = json.optString("app_name", "PC"),
                title = json.optString("title", "通知"),
                body = json.optString("body", ""),
                timestamp = timestamp,
            )
            "ping" -> RelayMessage.Ping(timestamp)
            "pong" -> RelayMessage.Pong(timestamp)
            else -> RelayMessage.Unknown(type)
        }
    }

    fun pongLine(nowSeconds: Long): String =
        JSONObject().put("type", "pong").put("timestamp", nowSeconds).toString() + "\n"

    /**
     * 1 本の接続を、相手が切るまで処理する。ping には pong を返し、それ以外は onMessage に渡す。
     * 壊れた行は読み飛ばす。接続が切れると IOException か、正常終了で戻る。
     */
    fun serve(
        input: InputStream,
        output: OutputStream,
        nowSeconds: () -> Long = { System.currentTimeMillis() / 1000 },
        onMessage: (RelayMessage) -> Unit,
    ) {
        val reader = BufferedReader(InputStreamReader(input, Charsets.UTF_8))
        val writer = OutputStreamWriter(output, Charsets.UTF_8)
        while (true) {
            val line = reader.readLine() ?: return
            if (line.isBlank() || line.length > MAX_LINE_CHARS) continue
            val message = parse(line) ?: continue
            if (message is RelayMessage.Ping) {
                writer.write(pongLine(nowSeconds()))
                writer.flush()
            }
            onMessage(message)
        }
    }
}
