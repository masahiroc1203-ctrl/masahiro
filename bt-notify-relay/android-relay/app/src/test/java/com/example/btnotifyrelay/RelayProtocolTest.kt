package com.example.btnotifyrelay

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

class RelayProtocolTest {

    /** PC 側 (pc-sender の Protocol.NotificationLine) が実際に出力する行。日本語や記号は \uXXXX になる */
    private val lineFromPc =
        "{\"type\":\"notification\",\"id\":\"Outlook_ABC_202611271530_5\",\"app_name\":\"Outlook\"," +
            "\"title\":\"\\u5B9A\\u4F8B\\u30DF\\u30FC\\u30C6\\u30A3\\u30F3\\u30B0 (5\\u5206\\u524D)\"," +
            "\"body\":\"15:30 \\u958B\\u59CB / \\u5834\\u6240: \\u4F1A\\u8B70\\u5BA4A\\n\\u0022\\u5F15\\u7528\\u0022 " +
            "\\u003Ctag\\u003E \\u0026 \\u0027x\\u0027\",\"timestamp\":1795760000}"

    @Test
    fun parsesNotificationSentByPc() {
        val message = RelayProtocol.parse(lineFromPc)
        assertEquals(
            RelayMessage.Notification(
                id = "Outlook_ABC_202611271530_5",
                appName = "Outlook",
                title = "定例ミーティング (5分前)",
                body = "15:30 開始 / 場所: 会議室A\n\"引用\" <tag> & 'x'",
                timestamp = 1795760000L,
            ),
            message
        )
    }

    @Test
    fun parsesSpecExampleWithDefaults() {
        val message = RelayProtocol.parse("{\"type\":\"notification\",\"title\":\"定例\"}") as RelayMessage.Notification
        assertEquals("PC", message.appName)
        assertEquals("定例", message.title)
        assertEquals("", message.body)
        assertNull(message.timestamp)
    }

    @Test
    fun parsesPingPongAndUnknown() {
        assertEquals(RelayMessage.Ping(1795760030L), RelayProtocol.parse("{ \"type\": \"ping\", \"timestamp\": 1795760030 }"))
        assertEquals(RelayMessage.Pong(null), RelayProtocol.parse("{\"type\":\"pong\"}"))
        assertEquals(RelayMessage.Unknown("hello"), RelayProtocol.parse("{\"type\":\"hello\"}"))
    }

    @Test
    fun rejectsNonJson() {
        assertNull(RelayProtocol.parse("not json"))
        assertNull(RelayProtocol.parse("[1,2]"))
    }

    @Test
    fun pongLineMatchesSpec() {
        val pong = RelayProtocol.pongLine(1795760030L)
        assertTrue(pong.endsWith("\n"))
        val json = JSONObject(pong.trim())
        assertEquals("pong", json.getString("type"))
        assertEquals(1795760030L, json.getLong("timestamp"))
    }

    @Test
    fun serveHandlesAStreamOfLines() {
        // 壊れた行・空行・CRLF が混ざっても、通知と ping を順に処理し、ping には pong を返す
        val input = listOf(
            lineFromPc,
            "",
            "garbage",
            "{\"type\":\"ping\",\"timestamp\":1795760030}",
            "{\"type\":\"notification\",\"id\":\"t\",\"app_name\":\"PCテスト\",\"title\":\"テスト\",\"body\":\"本文\",\"timestamp\":1}\r",
        ).joinToString("\n", postfix = "\n")
        val output = ByteArrayOutputStream()
        val received = mutableListOf<RelayMessage>()

        RelayProtocol.serve(ByteArrayInputStream(input.toByteArray(Charsets.UTF_8)), output, nowSeconds = { 42L }) {
            received += it
        }

        assertEquals(3, received.size)
        assertEquals("定例ミーティング (5分前)", (received[0] as RelayMessage.Notification).title)
        assertEquals(RelayMessage.Ping(1795760030L), received[1])
        assertEquals("テスト", (received[2] as RelayMessage.Notification).title)

        val replies = output.toString(Charsets.UTF_8.name()).lines().filter { it.isNotBlank() }
        assertEquals(1, replies.size)
        assertEquals("pong", JSONObject(replies[0]).getString("type"))
        assertEquals(42L, JSONObject(replies[0]).getLong("timestamp"))
    }

    @Test
    fun uuidMatchesPcSide() {
        assertEquals("8ce255c0-200a-11e0-ac64-0800200c9a66", BtRelayService.SERVICE_UUID.toString())
    }
}
