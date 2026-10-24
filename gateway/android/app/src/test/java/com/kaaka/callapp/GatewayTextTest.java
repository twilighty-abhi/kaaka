package com.kaaka.callapp;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class GatewayTextTest {
    @Test
    public void tokenMatchesServerFormat() {
        for (int i = 0; i < 200; i++) {
            assertTrue(GatewayText.newToken().matches("^[A-Za-z0-9_-]{6,32}$"));
        }
        assertNotEquals(GatewayText.newToken(), GatewayText.newToken());
    }

    @Test
    public void parsesAckWithAndWithoutNumber() {
        assertEquals("", GatewayText.parseAck("ACK"));
        assertEquals("", GatewayText.parseAck("  ack  "));
        assertEquals("", GatewayText.parseAck("Ack, on my way"));
        assertEquals("+919876543210", GatewayText.parseAck("ACK +91 98765 43210"));
        assertEquals("9876543210", GatewayText.parseAck("ack: 98765-43210 coming"));
    }

    @Test
    public void ignoresNonAck() {
        assertNull(GatewayText.parseAck("Kaaka Alert: Emergency assistance requested"));
        assertNull(GatewayText.parseAck("acknowledged"));
        assertNull(GatewayText.parseAck("please ACK"));
        assertNull(GatewayText.parseAck(null));
    }

    @Test
    public void locationLineOnlyWithPublicUrl() {
        assertEquals("", GatewayText.locationLine("", "abc123def456"));
        assertEquals("\nShare your location: https://x.example/l/abc123def456",
            GatewayText.locationLine("https://x.example/", "abc123def456"));
    }
}
