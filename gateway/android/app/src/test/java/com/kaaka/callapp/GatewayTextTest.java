package com.kaaka.callapp;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.List;
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

    @Test
    public void helpKeywordsAsWholeWords() {
        assertTrue(GatewayText.isHelpRequest("HELP"));
        assertTrue(GatewayText.isHelpRequest("please help me"));
        assertTrue(GatewayText.isHelpRequest("sos!"));
        assertTrue(GatewayText.isHelpRequest("Kaaka, need help at the bus stand"));
        assertTrue(GatewayText.isHelpRequest("എനിക്ക് സഹായം വേണം"));
        assertFalse(GatewayText.isHelpRequest("that was helpful, thanks"));
        assertFalse(GatewayText.isHelpRequest("kaakaa"));
        assertFalse(GatewayText.isHelpRequest("see you tomorrow"));
        assertFalse(GatewayText.isHelpRequest(null));
    }

    @Test
    public void ownMessagesAreNotHelpRequests() {
        assertFalse(GatewayText.isHelpRequest(GatewayText.REPLY_EN));
        assertFalse(GatewayText.isHelpRequest(GatewayText.REPLY_ML));
        assertFalse(GatewayText.isHelpRequest("Kaaka: help SMS from +910000000001 at 10:00: \"help\""));
        assertFalse(GatewayText.isHelpRequest("Kaaka UNACKNOWLEDGED: call from +910000000001 at 10:00."));
        assertFalse(GatewayText.isHelpRequest("A Kaaka responder has seen your call and will contact you soon."));
        assertTrue(GatewayText.isHelpRequest("Kaaka: please help"));
    }

    @Test
    public void parsesResponderCommands() {
        assertTrue(GatewayText.isStatus("STATUS"));
        assertTrue(GatewayText.isStatus(" status "));
        assertFalse(GatewayText.isStatus("status please"));
        assertArrayEquals(new String[] { "+919876543210", "handed to police" },
            GatewayText.parseResolve("RESOLVE +91 98765 43210 handed to police"));
        assertArrayEquals(new String[] { "", "" }, GatewayText.parseResolve("resolve"));
        assertArrayEquals(new String[] { "", "false alarm" }, GatewayText.parseResolve("Resolve false alarm"));
        assertNull(GatewayText.parseResolve("resolved it"));
        assertEquals("+919876543210", GatewayText.parseAck("ACK +919876543210"));
    }

    @Test
    public void replyLanguages() {
        assertEquals(GatewayText.REPLY_EN, GatewayText.defaultReply("en"));
        assertEquals(GatewayText.REPLY_EN, GatewayText.defaultReply(null));
        assertEquals(GatewayText.REPLY_ML, GatewayText.defaultReply("ml"));
        assertEquals(GatewayText.REPLY_EN + "\n" + GatewayText.REPLY_ML, GatewayText.defaultReply("both"));
    }

    private static GatewayText.Ev call(String number, long at, boolean limited) {
        return new GatewayText.Ev("call", number, "rejected", at, limited);
    }

    @Test
    public void rateLimitCountsRepliesInLastHour() {
        long now = 10 * GatewayText.HOUR_MS;
        List<GatewayText.Ev> events = Arrays.asList(
            call("+919800000001", now - 10_000, false),
            call("9800000001", now - 20_000, false),
            call("+919800000001", now - 30_000, true),               // rate-limited ones do not count
            call("+919800000001", now - 2 * GatewayText.HOUR_MS, false), // older than an hour
            call("+919800000002", now - 5_000, false));
        assertFalse(GatewayText.isRateLimited(events, "+919800000001", now, 3));
        assertTrue(GatewayText.isRateLimited(events, "+919800000001", now, 2));
        assertFalse(GatewayText.isRateLimited(events, "+919800000001", now, 0)); // 0 = no limit
        assertFalse(GatewayText.isRateLimited(events, "", now, 1));
    }

    @Test
    public void openIncidentsSkipAcknowledgedAndOld() {
        long now = 30 * GatewayText.HOUR_MS;
        List<GatewayText.Ev> events = Arrays.asList(
            new GatewayText.Ev("ack", "+919800000001", "", now - 50_000, false),
            call("+919800000001", now - 60_000, false),                 // acknowledged later: closed
            new GatewayText.Ev("call", "+919800000002", "sms", now - 40_000, false),
            call("+919800000003", now - 30_000, false),
            new GatewayText.Ev("resolve", "+919800000003", "", now - 20_000, false),
            call("+919800000004", now - 25 * GatewayText.HOUR_MS, false), // older than 24 h
            call("+919800000005", now - 90_000, false),
            new GatewayText.Ev("ack", "+919800000005", "", now - 100_000, false), // ack before the call: still open
            call("", now - 1_000, false));                               // hidden number
        List<GatewayText.Ev> open = GatewayText.openIncidents(events, now);
        assertEquals(2, open.size());
        assertEquals("+919800000002", open.get(0).number);
        assertEquals("help SMS", open.get(0).kind());
        assertEquals("+919800000005", open.get(1).number);
        assertTrue(GatewayText.statusMessage(open).startsWith("Kaaka: 2 open — +919800000002 (help SMS "));
        assertEquals("Kaaka: no open incidents", GatewayText.statusMessage(Arrays.asList()));
    }

    @Test
    public void handledSinceNeedsLaterAckOrResolve() {
        List<GatewayText.Ev> events = Arrays.asList(new GatewayText.Ev("ack", "9800000001", "", 1_000, false));
        assertTrue(GatewayText.handledSince(events, "+919800000001", 500));
        assertFalse(GatewayText.handledSince(events, "+919800000001", 2_000));
        assertFalse(GatewayText.handledSince(events, "+919800000002", 0));
    }

    @Test
    public void safeReportsAreRecognised() {
        for (String s : new String[] { "SAFE", "safe", " Safe. ", "I'm safe", "im safe!", "I am safe", "I AM SAFE", "ഞാൻ സുരക്ഷിതം" }) {
            assertTrue(s, GatewayText.isSafeReport(s));
        }
        for (String s : new String[] { "not safe", "safe house", "SAFE HELP", "Kaaka: glad you are safe. Your alert is closed.", "", null }) {
            assertFalse(String.valueOf(s), GatewayText.isSafeReport(s));
        }
        // A safe report is not a help request.
        assertFalse(GatewayText.isHelpRequest("I'm safe"));
    }

    @Test
    public void openIncidentClosesOnSafeOrResolveNotAck() {
        long now = 1_000_000_000L;
        GatewayText.Ev call = new GatewayText.Ev("call", "+919876543210", "rejected", now - 60_000, false);
        GatewayText.Ev alertOnly = new GatewayText.Ev("alert", "+919000000001", "", now - 60_000, false);
        assertTrue(GatewayText.hasOpenIncident(Arrays.asList(call), "9876543210", now));
        assertTrue(GatewayText.hasOpenIncident(Arrays.asList(alertOnly), "+919000000001", now));
        assertFalse(GatewayText.hasOpenIncident(Arrays.asList(call), "+911111111111", now));
        GatewayText.Ev ack = new GatewayText.Ev("ack", "+919876543210", "", now - 30_000, false);
        assertTrue(GatewayText.hasOpenIncident(Arrays.asList(call, ack), "+919876543210", now));
        GatewayText.Ev safe = new GatewayText.Ev("safe", "+919876543210", "", now - 10_000, false);
        assertFalse(GatewayText.hasOpenIncident(Arrays.asList(call, ack, safe), "+919876543210", now));
        // A "safe" counts as handled for the escalation reminder.
        assertTrue(GatewayText.handledSince(Arrays.asList(call, safe), "+919876543210", call.at));
        // ...and reopens when the caller contacts again.
        GatewayText.Ev again = new GatewayText.Ev("call", "+919876543210", "sms", now, false);
        assertTrue(GatewayText.hasOpenIncident(Arrays.asList(call, safe, again), "+919876543210", now));
        // Old contact (over 24 h) is not open.
        GatewayText.Ev old = new GatewayText.Ev("call", "+919000000002", "rejected", now - 25L * 3600_000, false);
        assertFalse(GatewayText.hasOpenIncident(Arrays.asList(old), "+919000000002", now));
    }
}
