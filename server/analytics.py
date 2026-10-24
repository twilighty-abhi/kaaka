"""
Kaaka analytics
===============
Pure functions that summarise the incident event log (server/events.jsonl) for GET /api/analytics.
Nothing here reads files or the clock: callers pass the events, the responder list and "now", so every
number can be checked by hand from a small list of events.

Incidents here are *episodes*: an episode for a caller starts with their first contact (call, help SMS
or alert report) and ends when it is resolved; a later contact starts a new episode. This is the same
grouping the dashboard uses (a resolved incident reopens on new activity), but each reopening is counted
as its own incident so that response times are measured from the contact that started it.
"""

import math
from datetime import datetime, timedelta

try:
    from server.incidents import number_key
except ImportError:
    from incidents import number_key

RANGES = ("24h", "7d", "30d", "all")
DEFAULT_RANGE = "7d"
CHANNELS = ("call", "help_sms", "app_alert")
HOTSPOT_CELL_DEG = 0.005  # about 550 m north-south, about 550 m east-west near Kochi


def channel_of(event):
    """'call', 'help_sms' or 'app_alert' for a contact event; None for anything else."""
    kind = event.get("kind")
    if kind == "call":
        return "help_sms" if event.get("state") == "sms" else "call"
    if kind == "alert":
        return "app_alert"
    return None


def range_window(range_key, now_epoch, first_epoch=None):
    """
    (start_epoch, bucket, bucket_starts) for a range. Buckets are whole local hours (24h) or local days,
    the last one containing "now", so the chart axis is continuous. "all" starts on the day of the first
    event (today when there are none).
    """
    if range_key not in RANGES:
        raise ValueError(f'range must be one of {", ".join(RANGES)}')
    now = datetime.fromtimestamp(now_epoch)
    if range_key == "24h":
        last = now.replace(minute=0, second=0, microsecond=0)
        starts = [last - timedelta(hours=i) for i in range(23, -1, -1)]
        return starts[0].timestamp(), "hour", starts
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == "all":
        first_day = datetime.fromtimestamp(first_epoch).replace(hour=0, minute=0, second=0, microsecond=0) \
            if first_epoch is not None else today
        days = max(1, (today.date() - first_day.date()).days + 1)
    else:
        days = 7 if range_key == "7d" else 30
    starts = []
    for i in range(days - 1, -1, -1):
        # Step by calendar date (not 24 h) so a DST change cannot skip or repeat a day.
        d = today.date() - timedelta(days=i)
        starts.append(datetime(d.year, d.month, d.day))
    return starts[0].timestamp(), "day", starts


def bucket_label(start, bucket):
    return start.strftime("%Y-%m-%d %H:00" if bucket == "hour" else "%Y-%m-%d")


def build_episodes(events):
    """
    Episodes in time order. Each: key, number, start (epoch of the first contact), contacts [(epoch,
    channel)], ack_epoch (first ACK), last_ack_epoch, resolve (event or None), latest_location (lat, lon)
    or None, located (bool). ACK or resolve events with no active episode for that caller are ignored.
    """
    active = {}
    episodes = []
    for e in sorted(events, key=lambda ev: ev.get("received_epoch", 0)):
        key = number_key(e.get("number"))
        t = e.get("received_epoch", 0)
        channel = channel_of(e)
        ep = active.get(key)
        if channel:
            if ep is None:
                ep = {"key": key, "number": e.get("number") or "hidden", "start": t, "contacts": [],
                      "ack_epoch": None, "last_ack_epoch": None, "resolve": None,
                      "latest_location": None, "located": False}
                active[key] = ep
                episodes.append(ep)
            ep["contacts"].append((t, channel))
            if e.get("lat") is not None and e.get("lon") is not None:
                ep["latest_location"] = (e["lat"], e["lon"])
                ep["located"] = True
        elif ep is None:
            continue
        elif e.get("kind") == "location" and e.get("lat") is not None:
            ep["latest_location"] = (e["lat"], e["lon"])
            ep["located"] = True
        elif e.get("kind") == "ack":
            if ep["ack_epoch"] is None:
                ep["ack_epoch"] = t
            ep["last_ack_epoch"] = t
        elif e.get("kind") == "resolve":
            ep["resolve"] = {"by": e.get("by", ""), "epoch": t}
            del active[key]
    return episodes


def episode_outcome(ep):
    """'closed_by_caller', 'resolved_by_responder', 'acknowledged_open' or 'open' (as the dashboard shows it)."""
    if ep["resolve"]:
        return "closed_by_caller" if ep["resolve"]["by"] == "caller" else "resolved_by_responder"
    # A contact after the last ACK needs a fresh acknowledgement (same rule as IncidentStore).
    if ep["last_ack_epoch"] is not None and ep["last_ack_epoch"] >= ep["contacts"][-1][0]:
        return "acknowledged_open"
    return "open"


def percentile(values, q):
    """Linear-interpolated percentile (q in 0..100) of a non-empty list; None for an empty one."""
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * q / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def minutes(values, q):
    p = percentile(values, q)
    return None if p is None else round(p / 60.0, 1)


def pct(part, whole):
    return None if not whole else round(100.0 * part / whole, 1)


def hotspots(episodes, cell=HOTSPOT_CELL_DEG):
    """Grid cells (cell° square) with the number of episodes whose latest location falls in them."""
    cells = {}
    for ep in episodes:
        if not ep["latest_location"]:
            continue
        lat, lon = ep["latest_location"]
        ij = (math.floor(lat / cell), math.floor(lon / cell))
        cells[ij] = cells.get(ij, 0) + 1
    out = [{"lat": round((i + 0.5) * cell, 5), "lon": round((j + 0.5) * cell, 5), "count": n}
           for (i, j), n in cells.items()]
    out.sort(key=lambda c: (-c["count"], c["lat"], c["lon"]))
    return out


def responder_stats(events, responders, start_epoch):
    """Dispatches and ACKs per responder in range, matched by phone number (last 10 digits)."""
    rows = {}

    def row(number, name=""):
        key = number_key(number)
        if key not in rows:
            rows[key] = {"name": name, "number": number, "dispatches": 0, "acks": 0, "_dist": []}
        if name and not rows[key]["name"]:
            rows[key]["name"] = name
        return rows[key]

    for r in responders:
        row(r.get("number", ""), r.get("name", ""))
    for e in events:
        if e.get("received_epoch", 0) < start_epoch:
            continue
        if e.get("kind") == "dispatch":
            for d in e.get("responders", []):
                r = row(d.get("number", ""), d.get("name", ""))
                r["dispatches"] += 1
                if isinstance(d.get("distance_km"), (int, float)):
                    r["_dist"].append(d["distance_km"])
        elif e.get("kind") == "ack" and e.get("responder"):
            key = number_key(e["responder"])
            if key in rows:  # an ACK from a number that is neither registered nor dispatched is not a responder row
                rows[key]["acks"] += 1
    out = []
    for r in rows.values():
        dist = r.pop("_dist")
        r["avg_distance_km"] = round(sum(dist) / len(dist), 2) if dist else None
        r["name"] = r["name"] or r["number"]
        out.append(r)
    out.sort(key=lambda r: (-r["acks"], -r["dispatches"], r["name"].lower()))
    return out


def compute(events, responders, range_key, now_epoch):
    """The GET /api/analytics body for this range (see README)."""
    first = min((e.get("received_epoch", now_epoch) for e in events), default=None)
    start, bucket, starts = range_window(range_key, now_epoch, first)

    episodes = build_episodes(events)
    in_range = [ep for ep in episodes if any(t >= start for t, _ in ep["contacts"])]

    ack_secs = [ep["ack_epoch"] - ep["start"] for ep in in_range if ep["ack_epoch"] is not None]
    close_secs = [ep["resolve"]["epoch"] - ep["start"] for ep in in_range if ep["resolve"]]
    outcomes = {"resolved_by_responder": 0, "closed_by_caller": 0, "acknowledged_open": 0, "open": 0}
    for ep in in_range:
        outcomes[episode_outcome(ep)] += 1

    contacts = [e for e in events if channel_of(e) and e.get("received_epoch", 0) >= start]
    replies = [e for e in contacts if e["kind"] == "call" and e.get("sms") in ("sent", "failed")]

    series = [{"date": bucket_label(s, bucket), **{c: 0 for c in CHANNELS}} for s in starts]
    hours = [0] * 24
    for e in contacts:
        dt = datetime.fromtimestamp(e["received_epoch"])
        if bucket == "hour":
            idx = int((dt.replace(minute=0, second=0, microsecond=0) - starts[0]).total_seconds() // 3600)
        else:
            idx = (dt.date() - starts[0].date()).days
        if 0 <= idx < len(series):
            series[idx][channel_of(e)] += 1
        hours[dt.hour] += 1

    return {
        "range": range_key,
        "bucket": bucket,
        "from": datetime.fromtimestamp(start).strftime("%Y-%m-%d %H:%M:%S"),
        "to": datetime.fromtimestamp(now_epoch).strftime("%Y-%m-%d %H:%M:%S"),
        "kpis": {
            "incidents": len(in_range),
            "open_now": sum(1 for ep in episodes if not ep["resolve"]),
            "median_ack_minutes": minutes(ack_secs, 50),
            "p90_ack_minutes": minutes(ack_secs, 90),
            "acks": len(ack_secs),
            "median_close_minutes": minutes(close_secs, 50),
            "resolved": len(close_secs),
            "located_pct": pct(sum(1 for ep in in_range if ep["located"]), len(in_range)),
            "reply_sent_pct": pct(sum(1 for e in replies if e["sms"] == "sent"), len(replies)),
            "replies_attempted": len(replies),
            "closed_by_caller": outcomes["closed_by_caller"],
        },
        "daily": series,
        "hours": hours,
        "outcomes": outcomes,
        "responders": responder_stats(events, responders, start),
        "hotspot_cell_deg": HOTSPOT_CELL_DEG,
        "hotspots": hotspots(in_range),
    }
