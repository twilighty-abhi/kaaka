#!/usr/bin/env python3
"""Builds the Kaaka user docs (site/docs/*.html) from the page definitions below.

Run `python3 site/docs/build_docs.py` after editing a page; commit the generated HTML with it.
The pages are served by server/server.py at /docs and work as plain files too.
"""
import os
import re

OUT = os.path.dirname(os.path.abspath(__file__))

# (file, title, sidebar section, body html)
PAGES = []


def page(file, title, section, body):
    PAGES.append((file, title, section, body.strip()))


page("index.html", "Overview", "Start here", """
<p class="lead">Kaaka is a community help line run from one Android phone and one laptop. Callers need nothing but a phone that can make a call or send an SMS.</p>

<h2 id="parts">The three parts</h2>
<table>
<tr><th>Part</th><th>Runs on</th><th>What it does</th></tr>
<tr><td><strong>Kaaka Call</strong> (the Kaaka number)</td><td>One Android phone with a SIM</td><td>Screens every incoming call, rejects it and replies by SMS. Texts responders, handles their replies, and reports everything to the control room.</td></tr>
<tr><td><strong>Control room</strong> (dashboard)</td><td>A laptop or server</td><td>Groups calls, texts, alerts and locations into incidents on a live map. History, analytics, responder registry, notifications.</td></tr>
<tr><td><strong>Kaaka Sensors</strong> (optional)</td><td>The caller's own phone</td><td>SOS button, fall detection, a safety timer and an "I'm safe" button. Sends GPS reports by SMS to the Kaaka number.</td></tr>
</table>

<h2 id="flow">What happens on a call</h2>
<ol>
<li>Someone calls the Kaaka number. The call is rejected at once, so it costs the caller nothing.</li>
<li>The caller gets an SMS: <em>"Kaaka received your call. Help is being arranged. If in immediate danger, call 112."</em> If a public URL is set, it ends with a link to share their location.</li>
<li>Every configured responder gets an SMS with the caller's number and <em>"Reply ACK &lt;number&gt; to confirm."</em></li>
<li>The call appears in the control room as an open incident. When the caller's location arrives, the nearest available responder is dispatched by SMS with distance and ETA.</li>
<li>A responder replies <code>ACK</code>; the caller is told a responder has seen their call. If nobody replies within five minutes, responders get one reminder.</li>
<li>The incident closes when a responder texts <code>RESOLVE</code>, the caller texts <code>SAFE</code>, or someone presses [resolve] in the control room.</li>
</ol>

<h2 id="texts">Help without a call</h2>
<p>An SMS to the Kaaka number containing <code>HELP</code>, <code>SOS</code>, <code>KAAKA</code> or <code>സഹായം</code> is handled exactly like a call. See <a href="sms-commands.html">SMS commands</a>.</p>

<div class="callout warn"><strong>Kaaka works alongside 112, never instead of it.</strong> Every reply points to 112 for immediate danger. Kaaka adds location, tracking and a responder loop; it cannot answer calls with a voice.</div>

<h2 id="next">Where to go next</h2>
<ul>
<li><a href="getting-started.html">Getting started</a>: set up the Kaaka number and the control room in about twenty minutes.</li>
<li><a href="sms-commands.html">SMS commands</a>: every text Kaaka understands and sends.</li>
<li><a href="deployment.html">Running in production</a>: token, service files, backups, health check.</li>
</ul>
""")

page("getting-started.html", "Getting started", "Start here", """
<p class="lead">You need one Android phone (Android 10 or newer) with a SIM that can send SMS, and a laptop on the same Wi-Fi. The phone becomes the Kaaka number.</p>

<h2 id="dashboard">1. Start the control room</h2>
<pre><code>git clone https://github.com/twilighty-abhi/kaaka
cd kaaka
python3 -m venv .venv-mac &amp;&amp; .venv-mac/bin/pip install -r server/requirements.txt
.venv-mac/bin/python server/server.py</code></pre>
<p>The banner prints the laptop's Wi-Fi address. Open <code>http://&lt;ip&gt;:8080/admin</code> in a browser, or use the <strong>Open control room</strong> button on the landing page: that is the control room. With a token or demo PIN set, it asks for it first. <code>http://&lt;ip&gt;:8080/</code> is the public landing page and <code>/docs</code> is this wiki.</p>
<div class="callout"><strong>Before anyone else can reach it, set a token.</strong> <code>export KAAKA_ADMIN_TOKEN=&lt;long random string&gt;</code> before starting the server, then open the control room once as <code>/admin?token=&lt;the token&gt;</code>. Without a token anyone on the network can read callers' numbers and locations. See <a href="deployment.html">Running in production</a>.</div>

<h2 id="gateway">2. Install Kaaka Call on the Kaaka number</h2>
<ol>
<li>Copy <code>gateway/Kaaka.apk</code> to the phone and install it. On a phone that had an earlier debug build, uninstall that first.</li>
<li>Open <strong>Kaaka Call</strong>. The setup card lists four rows. Make each one green:
  <ul>
  <li><strong>call screening</strong>: tap [enable] and choose Kaaka Call as the caller ID &amp; spam app.</li>
  <li><strong>sms send / receive</strong>: tap [allow].</li>
  <li><strong>calls from contacts</strong>: tap [allow] (phone, call log and call management). Android does not pass calls from saved contacts to call screening, so Kaaka Call handles them another way.</li>
  <li><strong>battery optimisation</strong>: tap [exempt] so the phone never puts Kaaka to sleep.</li>
  </ul></li>
<li>Tap <strong>[config]</strong> and fill in:
  <ul>
  <li><strong>responder numbers</strong>: the phones that should be texted on every call, comma or newline separated.</li>
  <li><strong>dashboard server</strong>: <code>http://&lt;laptop ip&gt;:8080</code>.</li>
  <li><strong>dashboard token</strong>: the same value as <code>KAAKA_ADMIN_TOKEN</code>, if you set one.</li>
  </ul>
  Leave the rest at the defaults for now and tap <strong>save</strong>. Saving sends a heartbeat; within a minute the control room header shows the phone as seen.</li>
</ol>
<p>The header reads <strong>active</strong> when screening and SMS are both on. Settings are stored natively, so Kaaka keeps working with the app closed and the screen locked.</p>

<h2 id="test">3. Make a test call</h2>
<ol>
<li>From another phone, call the Kaaka number. It should be rejected within a second.</li>
<li>That phone receives the reply SMS. Each responder receives the call alert.</li>
<li>The control room's <strong>live</strong> page shows a new open incident.</li>
<li>From a responder phone, text <code>ACK</code> to the Kaaka number. The caller gets a confirmation and the incident shows "acknowledged".</li>
<li>Text <code>RESOLVE</code> from the responder phone. The incident moves to <strong>history</strong>.</li>
</ol>
<p>The full checklist with every feature is in <code>docs/TESTING.md</code> in the repository.</p>

<h2 id="responders">4. Register responders in the control room</h2>
<p>On the <strong>responders</strong> page add each responder with a name, phone number and home position (type <code>lat, lon</code> or use [pick on map]). This is what makes the nearest-responder dispatch work; the responder numbers in Kaaka Call are what get the SMS. Use the same numbers in both places. See <a href="responders.html">Responders</a>.</p>

<h2 id="sensors">5. Optional: Kaaka Sensors for callers</h2>
<p>People who want an SOS button and automatic location reports install <code>client/KaakaSensors.apk</code> on their own phone and enter the Kaaka number in its settings. See <a href="kaaka-sensors.html">Kaaka Sensors</a>. The Kaaka number itself does not need it.</p>
""")

page("kaaka-call.html", "Kaaka Call settings", "Using Kaaka", """
<p class="lead">Kaaka Call is the app on the Kaaka number. Everything it does is configured under <strong>[config]</strong>. This page explains every setting and what the app does with it.</p>

<h2 id="settings">Settings</h2>
<table>
<tr><th>Setting</th><th>Default</th><th>What it does</th></tr>
<tr><td>reject incoming calls</td><td>on</td><td>Rejects every incoming call after reading the number. Off: calls ring through, but the SMS reply, responder texts and dashboard report still happen.</td></tr>
<tr><td>reply language</td><td>English</td><td>English, Malayalam or both. The Malayalam text should be checked by a native speaker before real use. Malayalam SMS use Unicode and split into more parts.</td></tr>
<tr><td>custom auto-reply</td><td>empty</td><td>Replaces the default reply text. Leave empty to use the language setting.</td></tr>
<tr><td>escalate after (minutes)</td><td>5</td><td>If nobody ACKs or resolves an incident in this time, every responder gets one reminder. 0 turns it off.</td></tr>
<tr><td>max replies per number per hour</td><td>3</td><td>After this many contacts from the same number in an hour, further contacts are logged and reported but nobody is texted. 0 = no limit.</td></tr>
<tr><td>responder numbers</td><td>empty</td><td>Phones texted on every call, help SMS and alert. Only these numbers can use the responder commands.</td></tr>
<tr><td>dashboard server</td><td>empty</td><td><code>http://&lt;ip&gt;:8080</code>. Empty = phone-only mode, no control room.</td></tr>
<tr><td>public link URL</td><td>empty</td><td>An https address that reaches the control room. Normally left empty: the phone learns it from the dashboard's heartbeat reply. See <a href="location-links.html">Location links</a>.</td></tr>
<tr><td>dashboard token</td><td>empty</td><td>Must match <code>KAAKA_ADMIN_TOKEN</code> on the server. Sent as the <code>X-Kaaka-Token</code> header on every request.</td></tr>
</table>

<h2 id="calls">How a call is handled</h2>
<ul>
<li><strong>Unknown numbers</strong> go through Android's call screening: the app reads the number and rejects the call. The call still shows in the call log as missed.</li>
<li><strong>Saved contacts</strong> are not passed to call screening by Android. Kaaka Call sees them through the phone-state broadcast and ends the call. Those events show "(contact)". This uses an API Android has deprecated; if it ever stops working, the call keeps ringing but the SMS, responder texts and dashboard report still happen.</li>
<li><strong>Hidden numbers</strong> get no SMS, since there is nowhere to send it. The call is still logged and reported.</li>
<li>Repeat calls from the same number within 10 seconds are treated as one.</li>
</ul>

<h2 id="rate">Rate limiting and escalation</h2>
<p>Each contact from a number counts toward the hourly limit. Beyond it, the event is logged as "rate-limited" and posted to the dashboard with <code>sms: skipped</code>, but no texts go out and no reminder is scheduled. Escalation reminders run through Android's WorkManager, so a sleeping phone may deliver them a little late, more so without the battery exemption. A newer contact from the same number restarts its timer.</p>

<h2 id="heartbeat">Heartbeat</h2>
<p>While a dashboard server is set, the phone posts a heartbeat every 15 minutes and right after saving settings: battery level, charging state, and whether call screening, SMS and contact-call permissions are in place. The control room shows "last seen" and warns when no heartbeat has arrived for 20 minutes or a permission is missing.</p>

<h2 id="events">Recent events and manual SMS</h2>
<p>The app keeps its last 200 events (calls, help SMS, alerts, ACKs, resolves, reminders) and shows them on its main screen. STATUS replies, rate limiting and escalation use this log, not the dashboard. At the bottom you can type a number and a message to send an SMS by hand.</p>
""")

page("sms-commands.html", "SMS commands", "Using Kaaka", """
<p class="lead">Every text Kaaka understands, who may send it, and the exact replies. Commands are case-insensitive. Texts Kaaka sends itself are never treated as commands, so two Kaaka numbers cannot answer each other.</p>

<h2 id="callers">From callers (anyone)</h2>
<table>
<tr><th>Text</th><th>Effect</th><th>Reply</th></tr>
<tr><td><code>HELP</code>, <code>SOS</code>, <code>KAAKA</code> or <code>സഹായം</code> anywhere in the message</td><td>Handled like a call: responders are texted, an incident opens, escalation starts. The first 80 characters of the message are passed to responders and shown in the control room.</td><td>The auto-reply, with the location link if one is set.</td></tr>
<tr><td><code>SAFE</code>, <code>I'm safe</code>, <code>I am safe</code> or <code>സുരക്ഷിതം</code></td><td>Closes the caller's open incident (a call, help SMS or alert in the last 24 hours with no later RESOLVE or SAFE). Responders are told. No reminder follows.</td><td>"Kaaka: glad you are safe. Your alert is closed. If you need help again, call or text this number." A SAFE with no open incident gets no reply.</td></tr>
<tr><td>Any other text</td><td>Ignored.</td><td>None.</td></tr>
</table>

<h2 id="responders">From responders (configured numbers only)</h2>
<table>
<tr><th>Text</th><th>Effect</th><th>Reply</th></tr>
<tr><td><code>ACK</code> or <code>ACK &lt;number&gt;</code></td><td>Acknowledges the most recent incident, or the given caller. The caller is texted "A Kaaka responder has seen your call and will contact you soon." The control room shows "acknowledged by …".</td><td>"Kaaka: ACK recorded for &lt;number&gt;" or "Kaaka: no recent incident to acknowledge".</td></tr>
<tr><td><code>STATUS</code></td><td>Lists incidents from the last 24 hours that have no later ACK or RESOLVE.</td><td>"Kaaka: 2 open — +91… (call 10:42), +91… (help SMS 10:50)" or "Kaaka: no open incidents".</td></tr>
<tr><td><code>RESOLVE</code>, <code>RESOLVE &lt;number&gt;</code>, <code>RESOLVE &lt;number&gt; &lt;note&gt;</code></td><td>Closes the most recent incident, or the given caller's, with an optional note. The control room marks it resolved with the note.</td><td>"Kaaka: resolved &lt;number&gt;".</td></tr>
</table>
<p>Responder commands are checked before caller texts, so a responder's own "safe" message is never misread. Texts from responders that are not commands are ignored and never treated as help requests. An ACK is never forwarded to other responders.</p>

<h2 id="sent">Texts Kaaka sends</h2>
<table>
<tr><th>To</th><th>When</th><th>Text</th></tr>
<tr><td>Caller</td><td>Call or help SMS</td><td>"Kaaka received your call. Help is being arranged. If in immediate danger, call 112." (plus "Share your location: https://…/l/&lt;token&gt;" when a public URL is set)</td></tr>
<tr><td>Caller</td><td>A responder ACKs</td><td>"A Kaaka responder has seen your call and will contact you soon."</td></tr>
<tr><td>Caller</td><td>Caller texts SAFE</td><td>"Kaaka: glad you are safe. Your alert is closed. If you need help again, call or text this number."</td></tr>
<tr><td>Responders</td><td>Call</td><td>"Kaaka: call from &lt;number&gt; at &lt;HH:mm&gt; — rejected, reply sent. Reply ACK &lt;number&gt; to confirm."</td></tr>
<tr><td>Responders</td><td>Help SMS</td><td>"Kaaka: help SMS from &lt;number&gt; at &lt;HH:mm&gt;: "&lt;first 80 characters&gt;" Reply ACK &lt;number&gt; to confirm."</td></tr>
<tr><td>Responders</td><td>Kaaka Sensors alert</td><td>"Kaaka alert from &lt;sender&gt;: " plus the alert's first line and its Maps link, "Reply ACK &lt;number&gt; to confirm."</td></tr>
<tr><td>Nearest responder</td><td>First location for an open incident</td><td>"Kaaka dispatch: you are the nearest responder (1.2 km, ~3 min) to &lt;caller&gt;. Location: &lt;maps&gt; Reply ACK &lt;caller&gt; to confirm."</td></tr>
<tr><td>Responders</td><td>No ACK after the escalation time</td><td>"Kaaka UNACKNOWLEDGED: call from &lt;number&gt; at &lt;HH:mm&gt;. Reply ACK &lt;number&gt; to confirm." (once)</td></tr>
<tr><td>Responders</td><td>Caller texts SAFE</td><td>"Kaaka: &lt;number&gt; reported safe at &lt;HH:mm&gt;. Incident closed."</td></tr>
</table>
<p>All of these are ordinary SMS from the Kaaka number's SIM and cost the same as any SMS. The location link makes the reply longer, so it may take two parts.</p>
""")

page("kaaka-sensors.html", "Kaaka Sensors", "Using Kaaka", """
<p class="lead">Kaaka Sensors is the optional app for the caller's own phone. It gives them an SOS button, fall detection, a safety timer and an "I'm safe" button, and sends GPS reports to the Kaaka number by SMS.</p>

<h2 id="install">Install and set up</h2>
<ol>
<li>Install <code>client/KaakaSensors.apk</code> on the caller's phone, not on the Kaaka number.</li>
<li>Open it and allow what it asks for: SMS, phone, location including <strong>"Allow all the time"</strong> (reports go out while the app is in the background), notifications, and activity recognition for the pedometer.</li>
<li>In the <strong>Settings</strong> card enter the <strong>gateway phone number</strong>: the Kaaka number. This is the only number that can start the beacon and the only number reports are sent to.</li>
<li>The app offers to become the default SMS app. That is what lets it react to the Kaaka reply reliably and show the full-screen alert. It is optional for the SOS button.</li>
</ol>
<p>The two computer settings (dashboard WebSocket and live sensor stream URL) are extras for a dashboard on the same Wi-Fi. Kaaka Sensors works phone-to-phone with only the gateway number.</p>

<h2 id="trigger">What starts the beacon</h2>
<ul>
<li><strong>The Kaaka reply.</strong> When the caller phones the Kaaka number and the reply SMS arrives from the configured number, the app sends a "Kaaka Alert" report with a fresh GPS fix straight away, then keeps reporting. An SMS from any other sender does nothing, whatever it says.</li>
<li><strong>SOS button</strong> at the top of the main screen: one report now, then the beacon.</li>
<li><strong>Auto SOS on fall</strong> (off by default): an acceleration spike above about 2.5 g followed by two seconds of stillness starts a 15-second countdown with an "I'm OK, cancel" button. The thresholds are untuned; expect false alarms until tested on real phones.</li>
<li><strong>Safety timer</strong>: pick 15 min, 30 min, 1 h, 2 h or a custom length. Tap <strong>I'm safe</strong> to check in, or <strong>Extend +15 min</strong>. If it runs out, a 30-second countdown starts, then SOS. The deadline is stored, so a timer that ended while the app was closed counts down as soon as the app reopens.</li>
</ul>
<p>Only one countdown runs at a time, and pressing SOS during a beacon sends one extra report rather than starting a second beacon.</p>

<h2 id="beacon">The beacon</h2>
<p>Reports go to the Kaaka number every 60 seconds by default. The <strong>Update every</strong> control offers 15, 30 or 60 seconds; the control room draws the reports as a trail on the map. The beacon stops by itself after the configured duration (30 minutes by default) or when you tap <strong>Stop</strong>. The SOS card shows the trigger, how many reports were sent, the last send time and the minutes left.</p>

<h2 id="safe">I'm safe</h2>
<p>While the beacon runs or a countdown is active, the <strong>I'm safe — close my alert</strong> button stops the beacon, cancels any countdown and timer, and texts <code>SAFE</code> to the Kaaka number. The Kaaka number closes the incident, confirms to the caller and tells responders. The button shows whether the SMS actually went out.</p>

<h2 id="report">What a report contains</h2>
<pre><code>Kaaka Alert: Emergency assistance requested

Live Sensors (5/5):
• Pedometer: 120 steps (0.09 km)
• Light: 53 lx
• Accelerometer: 9.7 m/s²
• Gyroscope: 0.2 rad/s
• Magnetometer: 186° S
• Coords: 10.007040, 76.365610
• Maps: https://maps.google.com/?q=10.007040,76.365610
• Trigger: sos</code></pre>
<p>Without a GPS fix the report says <code>• Location: unavailable</code>; the first report goes out after at most five seconds either way, and later ones carry coordinates once GPS locks. Triggers are <code>sos</code>, <code>fall</code>, <code>safety timer</code>, <code>gateway reply</code> or <code>manual</code>.</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Fall detection, the safety timer and the beacon run inside the app. With the app closed or the screen off for a long time, Android may pause them. Keep the app open during an emergency.</li>
<li>Reports are SMS from the caller's own SIM and cost the same as any SMS.</li>
<li>On Xiaomi and other heavily customised phones, grant the permissions inside the app's setup card and turn off battery restrictions for Kaaka Sensors; see <a href="troubleshooting.html">Troubleshooting</a>.</li>
</ul>
""")

page("dashboard.html", "The control room", "Using Kaaka", """
<p class="lead">The control room is the browser dashboard at <code>/admin</code>. It turns calls and texts into incidents people can act on. The header on every page shows the WebSocket link, the gateway mode and when the Kaaka number was last seen.</p>

<h2 id="pages">Pages</h2>
<table>
<tr><th>Page</th><th>What it shows</th></tr>
<tr><td><strong>live</strong></td><td>Open and acknowledged incidents, newest activity first. Each card shows the caller, calls and alerts, the latest location, the nearest responders with distance and ETA, and [timeline →] and [resolve] buttons. Below it the incident map with trails, nearest-responder lines and a [hotspots] overlay, then the activity log.</td></tr>
<tr><td><strong>history</strong></td><td>Resolved incidents. Search by digits of the number, filter by outcome (resolved by responder / closed by caller) and by date, [load more] 20 at a time, [download csv] with the same filters.</td></tr>
<tr><td><strong>incident</strong></td><td>One caller's full timeline: calls with the reply result, help SMS text, alerts with coordinates, location shares, dispatches, ACKs and the resolution. A map of the caller's trail. [resolve] while still active. Open it from any number or [timeline →].</td></tr>
<tr><td><strong>analytics</strong></td><td>One range filter (24h / 7d / 30d / all). KPI tiles: incidents, open now, median and p90 time to ACK, median time to close, % located, % replies sent, closed by caller. Charts: contacts per day by channel, contacts by hour, outcomes, a responder leaderboard. Each chart has a [table] view.</td></tr>
<tr><td><strong>responders</strong></td><td>The responder registry (add, availability, remove, [pick on map]) with each responder's dispatches and ACKs.</td></tr>
<tr><td><strong>system</strong></td><td>The raw latest alert, live sensor tiles, telephony details and the test triggers.</td></tr>
</table>
<p>The address keeps the page (for example <code>/admin#history</code>), so reload and back work. Counts show next to live, history and responders.</p>

<h2 id="status">Incident status</h2>
<ul>
<li><strong>open</strong>: needs attention, highlighted.</li>
<li><strong>acknowledged</strong>: a responder replied ACK.</li>
<li><strong>resolved</strong>: closed by a responder's RESOLVE, the caller's SAFE (shown with a green "safe" badge and "closed by caller"), or the [resolve] button. A later call, help SMS or alert reopens it.</li>
</ul>
<p>Incidents group everything by the caller's number (its last 10 digits). History is kept in the data directory and reloaded when the server restarts.</p>

<h2 id="map">The map</h2>
<p>OpenStreetMap tiles through Leaflet, so it needs internet. Offline, the panel says the map is unavailable and everything else works. Each incident's latest location is a pin; a caller who keeps sharing leaves a trail. A dashed line runs from the nearest available responder to each open incident, labelled with distance and ETA.</p>

<h2 id="notify">Notifications</h2>
<p>On a Mac the server posts a system notification for a new or reopened incident, an acknowledgement, a resolution, and when the Kaaka number goes silent or comes back. Turn them off with <code>--no-notify</code> or <code>KAAKA_NOTIFY=0</code>.</p>

<h2 id="csv">Export</h2>
<p>[download csv] on the history page, or <code>GET /api/incidents.csv</code> with the same filters. Columns: number, status, first and last seen, counts of calls, help SMS and alerts, latest coordinates, who acknowledged and resolved and when, and the note.</p>
""")

page("responders.html", "Responders", "Using Kaaka", """
<p class="lead">Responders are the people who go to the caller. They need nothing but a phone that can receive and send SMS. Kaaka texts them, reads their replies, and works out who is nearest.</p>

<h2 id="two-lists">Two lists, same numbers</h2>
<ul>
<li><strong>Responder numbers in Kaaka Call</strong> ([config] on the Kaaka number) decide who is texted on every call and who may use the responder commands.</li>
<li><strong>The responder registry in the control room</strong> (responders page) adds a name, a home position and availability. This is what the nearest-responder dispatch uses.</li>
</ul>
<p>Enter the same phone numbers in both. The control room matches ACKs to registry entries by number.</p>

<h2 id="dispatch">Nearest responder and dispatch</h2>
<ol>
<li>When an open incident gets its first location (from a Kaaka Sensors report or a shared link), the server finds the nearest available responders by straight-line distance and estimates the time at 25 km/h city speed. This is a planning number, not a promise.</li>
<li>It dispatches the one or two nearest: they are recorded on the incident, and the Kaaka number texts each one <em>"Kaaka dispatch: you are the nearest responder (1.2 km, ~3 min) to &lt;caller&gt;. Location: &lt;maps&gt; Reply ACK &lt;caller&gt; to confirm."</em></li>
<li>Later locations for the same open incident do not dispatch again. A resolved incident that reopens does.</li>
</ol>
<p>Toggle a responder's availability on the responders page when they are off duty; unavailable responders are never dispatched but still get the ordinary call texts from Kaaka Call.</p>

<h2 id="ack">Acknowledging and resolving</h2>
<p>A responder replies <code>ACK</code> (or <code>ACK &lt;number&gt;</code>) to take an incident. The caller is told, the control room shows who acknowledged, and the escalation reminder is cancelled. When the caller is reached, the responder texts <code>RESOLVE &lt;number&gt; &lt;note&gt;</code>; the note shows in the control room. <code>STATUS</code> lists what is still open. All three are in <a href="sms-commands.html">SMS commands</a>.</p>

<h2 id="escalation">If nobody answers</h2>
<p>After the escalation time (5 minutes by default) with no ACK or RESOLVE, every responder gets one reminder: <em>"Kaaka UNACKNOWLEDGED: call from &lt;number&gt; at &lt;HH:mm&gt;. Reply ACK &lt;number&gt; to confirm."</em> The control room's analytics page tracks the median and p90 time to acknowledge, so you can see whether the team keeps up.</p>
""")

page("location-links.html", "Location links", "Using Kaaka", """
<p class="lead">Most callers will not have Kaaka Sensors. The reply SMS can carry a link that shares their location from any phone browser, with no app.</p>

<h2 id="how">How it works</h2>
<ol>
<li>Kaaka Call gives every call a random token and reports it with the call. When it knows a public URL, the reply ends with <code>Share your location: https://&lt;public-url&gt;/l/&lt;token&gt;</code>.</li>
<li>The caller opens the link and taps <strong>Share my location</strong>. The browser's GPS position is posted to the control room.</li>
<li>While the page stays open it sends an update every 15 seconds ("Sharing live location · N updates") until the caller taps <strong>Stop sharing</strong>, so a moving caller leaves a trail on the map.</li>
<li>The location shows on the caller's incident with a Google Maps link, and triggers the nearest-responder dispatch.</li>
</ol>
<p>Links expire after 24 hours. The server accepts at most one update per link every 10 seconds. The link page and the location endpoint are the only public parts of the control room; everything else stays behind the admin token.</p>

<h2 id="setup">Setup</h2>
<p>Browsers only share location on <strong>https</strong> pages, so the control room must be reachable at a public https address.</p>
<ol>
<li>Set an admin token on the server. The server refuses to start with a public URL and no token (only <code>--allow-unprotected-public</code> overrides this, for throwaway tests).</li>
<li>Get an https address. For a quick test: <code>scripts/public-url.sh</code> opens a Cloudflare quick tunnel (<code>brew install cloudflared</code>) and prints the URL and the next commands. The address changes on every run. For something permanent use a named tunnel, a reverse proxy with a certificate, or a hosted server. See <a href="deployment.html">Running in production</a>.</li>
<li>Restart the server with <code>KAAKA_PUBLIC_URL=&lt;url&gt; KAAKA_ADMIN_TOKEN=&lt;token&gt;</code>.</li>
<li>In Kaaka Call set the same <strong>dashboard token</strong>. The phone learns the public URL from the next heartbeat reply within a minute and shows it as "auto: …" under the public link URL field. Set that field yourself only to pin a different address.</li>
</ol>
<p>Kaaka Call warns if the URL is not https, because the link would not work.</p>
""")

page("deployment.html", "Running in production", "Operating", """
<p class="lead">The basics for a help line that stays up: a token, a supervised service, backups, a health check, and release builds on the phones.</p>

<h2 id="token">1. Set an admin token</h2>
<p>Export <code>KAAKA_ADMIN_TOKEN</code> as a long random string before starting the server, and enter the same value as the dashboard token in Kaaka Call. With the token set, the dashboard, the API and the WebSocket all require it. The landing page, this wiki, <code>/api/health</code> and the location link pages stay public.</p>
<pre><code>export KAAKA_ADMIN_TOKEN="$(openssl rand -hex 24)"</code></pre>
<p>Open <code>/admin</code> and enter the token on the login page; a cookie remembers it in that browser until you visit <code>/admin/logout</code>. Opening <code>/admin?token=&lt;the token&gt;</code> works too. Ten wrong attempts from one address in ten minutes lock that address out for ten minutes.</p>

<h3 id="demo-pin">Demo PIN</h3>
<p>For a demo, set <code>KAAKA_DEMO_PIN=1234</code> (any short code). The landing page then shows "Try the live control room with demo PIN 1234" under an <strong>Open the control room</strong> button, and the login page offers a <strong>Use demo PIN</strong> button. The PIN unlocks everything the admin token does. Without <code>KAAKA_ADMIN_TOKEN</code> it is the only credential, so Kaaka Call's dashboard token must be the PIN too; with both set, the phone keeps the secret token and visitors use the PIN.</p>
<div class="callout warn"><strong>Anyone who reads the landing page can see every incident</strong>, including callers' numbers and locations. Use a demo PIN only with demo data or for a short window, then unset it and restart the server.</div>

<h2 id="service">2. Run it as a service</h2>
<p><strong>Linux (systemd):</strong> copy the repository to <code>/opt/kaaka</code>, create the venv there (<code>python3 -m venv .venv &amp;&amp; .venv/bin/pip install -r server/requirements.txt</code>), put the environment in <code>/etc/kaaka/kaaka.env</code> (start from <code>deploy/kaaka.env.example</code>), create the <code>kaaka</code> user, then:</p>
<pre><code>sudo cp deploy/kaaka.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kaaka
journalctl -u kaaka -f</code></pre>
<p>Data lives in <code>/var/lib/kaaka</code>. The unit restarts the server after a crash or reboot.</p>
<p><strong>macOS (launchd):</strong> edit the paths and the token in <code>deploy/com.kaaka.server.plist</code>, then:</p>
<pre><code>cp deploy/com.kaaka.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kaaka.server.plist</code></pre>
<p>Logs go to <code>~/Library/Logs/kaaka/</code>. Keep the Mac awake and on power (<code>caffeinate -i</code> or the Energy settings); a sleeping laptop is a silent control room.</p>
<p>The server needs no terminal: without one it skips the test console automatically, and <code>SIGTERM</code> stops it cleanly.</p>

<h2 id="data">3. Back up the data directory</h2>
<p><code>KAAKA_DATA_DIR</code> (or <code>--data-dir</code>) holds the incident history (<code>events.jsonl</code>), the responder registry and the last call. It contains phone numbers and locations: restrict access to it and back it up.</p>

<h2 id="health">4. Monitor it</h2>
<p><code>GET /api/health</code> needs no token and answers:</p>
<pre><code>{"ok": true, "version": "1.0.0", "uptime_seconds": 1234, "gateway_online": true}</code></pre>
<p><code>gateway_online</code> is false when the Kaaka number has not sent a heartbeat for 20 minutes (<code>KAAKA_STALE_SECONDS</code>). Point an uptime monitor at it and alert on anything but 200 with <code>ok: true</code>, and separately on <code>gateway_online: false</code>, which usually means the phone lost Wi-Fi, power or the app.</p>

<h2 id="public">5. Public access</h2>
<p>Put the server behind https, either a reverse proxy with a certificate or a tunnel, and set <code>KAAKA_PUBLIC_URL</code> so location links work from any phone. The Kaaka number only needs HTTP to port 8080, so a tunnel to that one port is enough; through a tunnel the dashboard's WebSocket is not reachable and the pages fall back to polling.</p>

<h2 id="apks">6. Install the release builds</h2>
<p><code>gateway/Kaaka.apk</code> and <code>client/KaakaSensors.apk</code> are release-signed, version 1.0.0. A phone that still has an earlier debug-signed build must uninstall it first: Android refuses to update an app whose signing key changed, and the uninstall clears the app's settings, so note the dashboard address and token before you do it. Later builds signed with the same key update in place.</p>

<h2 id="keystore">7. Guard the signing key</h2>
<p>Release builds read <code>android/keystore.properties</code> in each app (gitignored; copy <code>keystore.properties.example</code>). Back up the keystore it points to. If it is lost, installed apps can never be updated under the same signature and every phone would have to uninstall and reinstall.</p>

<h2 id="reference">Server settings reference</h2>
<table>
<tr><th>Setting</th><th>Purpose</th></tr>
<tr><td><code>KAAKA_ADMIN_TOKEN</code></td><td>Token for the dashboard, API and WebSocket. Strongly recommended.</td></tr>
<tr><td><code>--public-url</code> / <code>KAAKA_PUBLIC_URL</code></td><td>Public https address; requires the token.</td></tr>
<tr><td><code>KAAKA_DEMO_PIN</code></td><td>Public demo PIN shown on the landing and login pages. Demos only.</td></tr>
<tr><td><code>--data-dir</code> / <code>KAAKA_DATA_DIR</code></td><td>Runtime data directory. Default: <code>server/</code>.</td></tr>
<tr><td><code>--http-port</code> (8080), <code>--port</code> (8765), <code>--host</code> (0.0.0.0)</td><td>Dashboard port, WebSocket port, bind address.</td></tr>
<tr><td><code>--no-console</code> / <code>KAAKA_CONSOLE=0</code></td><td>Turn off the terminal test console (off automatically without a terminal).</td></tr>
<tr><td><code>--no-notify</code> / <code>KAAKA_NOTIFY=0</code></td><td>Turn off macOS notifications.</td></tr>
<tr><td><code>KAAKA_STALE_SECONDS</code></td><td>Seconds without a heartbeat before the Kaaka number counts as silent. Default 1200.</td></tr>
</table>
<p>Tests: <code>cd server &amp;&amp; python -m unittest -q</code>. The repository's CI runs them and both web builds on every push.</p>
""")

page("api.html", "API reference", "Operating", """
<p class="lead">The control room's HTTP API. All bodies are JSON. Errors return <code>{"success": false, "error": "…"}</code>. With <code>KAAKA_ADMIN_TOKEN</code> set, every endpoint except the public ones needs the token as the <code>X-Kaaka-Token</code> header, <code>?token=</code>, or the dashboard cookie.</p>

<h2 id="public">Public</h2>
<table>
<tr><th>Endpoint</th><th>Purpose</th></tr>
<tr><td><code>GET /</code>, <code>/docs</code></td><td>Landing page and this wiki.</td></tr>
<tr><td><code>GET /api/health</code></td><td><code>{ok, version, uptime_seconds, gateway_online}</code>.</td></tr>
<tr><td><code>GET /l/&lt;token&gt;</code></td><td>The location-sharing page for a caller. 404 when unknown or expired.</td></tr>
<tr><td><code>POST /api/location</code></td><td><code>{token, lat, lon, accuracy?}</code>. 400 malformed, 404 unknown or expired token, 429 more than one update per 10 s.</td></tr>
</table>

<h2 id="gateway">From the Kaaka number</h2>
<table>
<tr><th>Endpoint</th><th>Body</th></tr>
<tr><td><code>POST /api/call-event</code></td><td><code>number</code> ("" if hidden), <code>state</code> (<code>rejected</code>, <code>allowed</code>, or <code>sms</code> for a help text), <code>sms</code> (<code>sent</code>, <code>failed</code>, <code>skipped</code>), <code>timestamp</code>, optional <code>token</code> and <code>message</code> (max 500).</td></tr>
<tr><td><code>POST /api/telemetry</code></td><td><code>{report, sender}</code> for a forwarded "Kaaka Alert" SMS. Returns <code>dispatch: [{name, number, distance_km, eta_min, maps_url}]</code>, non-empty only the first time an open incident gets a location.</td></tr>
<tr><td><code>POST /api/heartbeat</code></td><td><code>{timestamp, battery, charging, screeningRole, smsGranted, contactCalls}</code>. Returns <code>public_url</code>.</td></tr>
<tr><td><code>POST /api/ack</code></td><td><code>{number, responder, timestamp}</code>.</td></tr>
<tr><td><code>POST /api/resolve</code></td><td><code>{number, by, note, timestamp}</code>. 404 when there is no incident for the number.</td></tr>
</table>

<h2 id="dashboard">Dashboard</h2>
<table>
<tr><th>Endpoint</th><th>Purpose</th></tr>
<tr><td><code>GET /api/status</code></td><td>Server status: last heartbeat, gateway stale flag, public URL, whether the token is on.</td></tr>
<tr><td><code>GET /api/incidents</code></td><td>Newest first, max 50. With <code>status</code>, <code>q</code>, <code>from</code>, <code>to</code>, <code>outcome</code>, <code>limit</code> (0–500), <code>offset</code>: a filtered page with <code>total</code> and <code>counts</code>.</td></tr>
<tr><td><code>GET /api/incidents/&lt;key&gt;</code></td><td>One incident (key = last 10 digits) with its full <code>timeline</code>.</td></tr>
<tr><td><code>GET /api/incidents.csv</code></td><td>CSV export with the same filters.</td></tr>
<tr><td><code>GET /api/analytics?range=24h|7d|30d|all</code></td><td>KPIs, per-bucket contacts by channel, hours, outcomes, responders, hotspots.</td></tr>
<tr><td><code>GET /api/responders</code>, <code>POST</code>, <code>PATCH /api/responders/&lt;id&gt;</code>, <code>DELETE</code></td><td>The responder registry: <code>{name, number, lat, lon, available}</code>.</td></tr>
<tr><td><code>GET /api/responders/activity</code></td><td>Dispatches and ACKs per responder, newest first.</td></tr>
</table>
<p>The WebSocket on port 8765 pushes the same events live (new calls, alerts, acknowledgements, resolutions, dispatches, gateway stale/back). It takes the token the same way during the handshake. The full table with every field is in the repository README.</p>
""")

page("troubleshooting.html", "Troubleshooting", "Operating", """
<p class="lead">Problems seen in real testing, and what fixed them.</p>

<h2 id="calls">Calls are not detected</h2>
<ul>
<li>Check the four setup rows in Kaaka Call are green. Call screening needs Android 10 or newer and the caller ID &amp; spam role; without it nothing happens on a call.</li>
<li>Calls from <strong>saved contacts</strong> need the "calls from contacts" permissions. Without them, Android keeps those calls away from Kaaka.</li>
<li>Two calls from the same number within 10 seconds count as one.</li>
</ul>

<h2 id="sms">The reply SMS is not sent</h2>
<ul>
<li>Hidden numbers get no SMS by design.</li>
<li>Check the hourly limit: after three contacts from one number in an hour, the event shows "rate-limited" and no text goes out.</li>
<li>On Xiaomi/MIUI and similar phones, grant SMS inside the app's setup card (not only in system settings), allow the app to run in the background, and turn off battery restrictions. MIUI silently blocks apps otherwise.</li>
</ul>

<h2 id="silent">The control room shows nothing or says the phone is silent</h2>
<ul>
<li>The Kaaka number and the laptop must be on the same Wi-Fi, and the dashboard server address in Kaaka Call must be the laptop's current IP. <strong>The IP changes when the laptop joins another network</strong>; the server banner prints the current one. Save settings in Kaaka Call to send a heartbeat right away.</li>
<li>If the phone's Wi-Fi is off or sleeping, events queue on the phone until it is back. Exempt Kaaka Call from battery optimisation.</li>
<li>With an admin token, the token in Kaaka Call must match exactly, or every report is refused with 401.</li>
<li><code>GET /api/health</code> shows whether the server is up and whether the phone has reported recently.</li>
</ul>

<h2 id="sensors">Kaaka Sensors does not react to the reply</h2>
<ul>
<li>The gateway phone number in its settings must match the Kaaka number as it appears on the incoming SMS (with the country code).</li>
<li>Location must be allowed <strong>all the time</strong>, and phone permission is needed on some Android versions. Without them the report goes out with "Location: unavailable" or not at all.</li>
<li>Android 14 and newer stop apps opening from the background. Kaaka Sensors sends the first report natively from the SMS receiver for that reason, so the report arrives even if the screen does not change.</li>
</ul>

<h2 id="install">"App not installed" or "package conflicts"</h2>
<p>The phone has an earlier build signed with a different key. Uninstall the old Kaaka app, then install the new APK. Note the dashboard address and token first; uninstalling clears them.</p>

<h2 id="link">The location link does nothing</h2>
<ul>
<li>It must be https. Browsers refuse to share location on plain http. Kaaka Call warns if the public URL is not https.</li>
<li>Links expire after 24 hours and need the control room to be reachable at that address.</li>
</ul>

<h2 id="map">The map is blank</h2>
<p>Map tiles come from the internet. Offline, the panel says the map is unavailable; incidents and the rest of the dashboard still work.</p>

<h2 id="server">The server does not start</h2>
<ul>
<li>"a public URL needs KAAKA_ADMIN_TOKEN": set a token, or drop the public URL.</li>
<li>On Linux, <code>--bt-mac</code> (Bluetooth mode) needs <code>python3-dbus</code> and <code>python3-gi</code>. Without <code>--bt-mac</code> only <code>websockets</code> is needed.</li>
<li>Port already in use: another server is running; stop it or pass <code>--http-port</code> and <code>--port</code>.</li>
</ul>
""")

page("safety.html", "Safety and privacy", "Operating", """
<p class="lead">What Kaaka does to keep callers' data safe, and what it cannot do.</p>

<h2 id="design">By design</h2>
<ul>
<li><strong>Works without data.</strong> Calls and SMS only. A rejected call costs the caller nothing.</li>
<li><strong>Only the Kaaka number can start the beacon.</strong> Kaaka Sensors reacts to an SMS from the configured number and nothing else; a stranger cannot make a phone report its location.</li>
<li><strong>Reports go only to the Kaaka number.</strong> Never to another number.</li>
<li><strong>The control room is locked before it goes public.</strong> The server refuses a public URL without an admin token. Only the location link page and its endpoint are public, and each link expires after 24 hours and accepts one update per 10 seconds.</li>
<li><strong>Rate limiting</strong> per caller stops one number from flooding responders.</li>
<li><strong>Nothing sensitive in backups.</strong> Both apps opt out of Android cloud backup, since they hold phone numbers, tokens and SMS.</li>
<li><strong>Every reply names 112.</strong> Kaaka is an addition to the emergency number, never a replacement.</li>
</ul>

<h2 id="data">What is stored, and where</h2>
<table>
<tr><th>Where</th><th>What</th></tr>
<tr><td>Kaaka number (app)</td><td>Settings, the last 200 events with caller numbers, and the ordinary SMS inbox.</td></tr>
<tr><td>Control room data directory</td><td>Every event: numbers, message texts, alert reports, coordinates, who acknowledged and resolved. The responder registry with names, numbers and home positions.</td></tr>
<tr><td>Caller's phone (Kaaka Sensors)</td><td>Its own settings and the SMS it sent.</td></tr>
</table>
<p>Treat the data directory as sensitive: restrict who can read it, back it up somewhere equally restricted, and delete history you no longer need.</p>

<h2 id="cannot">What Kaaka cannot do</h2>
<ul>
<li>It cannot talk to the caller. Android gives apps no call audio; Kaaka only screens, rejects and texts.</li>
<li>It cannot locate a caller who does not share their location, either with Kaaka Sensors or the link.</li>
<li>Fall detection is a simple, untuned heuristic.</li>
<li>Distance and ETA are straight-line estimates at an assumed city speed.</li>
<li>SMS can be delayed or lost by the network. Responders should still call the caller back.</li>
</ul>
""")

SECTIONS = []
for f, t, s, _ in PAGES:
    if s not in SECTIONS:
        SECTIONS.append(s)

CSS = open(os.path.join(OUT, "docs.css"), encoding="utf-8").read() if os.path.exists(os.path.join(OUT, "docs.css")) else ""

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Kaaka docs: {title}">
<title>{title} · Kaaka docs</title>
<link rel="icon" href="/icons/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<link rel="manifest" href="/icons/site.webmanifest">
<meta name="theme-color" content="#012624">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap">
<link rel="stylesheet" href="docs.css">
</head>
<body>
<header class="top">
  <a class="brand" href="../">kaaka</a>
  <span class="crumb">docs</span>
  <button class="menu" type="button" aria-expanded="false" aria-controls="side">Menu</button>
  <nav class="toplinks"><a href="../">Home</a><a href="../admin">Control room</a><a href="https://github.com/twilighty-abhi/kaaka" rel="noopener">GitHub</a></nav>
</header>
<div class="wrap">
  <aside class="side" id="side">
    <input class="filter" type="search" placeholder="Filter pages" aria-label="Filter pages">
    {sidebar}
  </aside>
  <main class="doc">
    <h1>{title}</h1>
    {body}
    <nav class="pager">{pager}</nav>
    <p class="foot">Kaaka 1.0.0 · <a href="https://github.com/twilighty-abhi/kaaka/tree/main/site/docs" rel="noopener">Edit this page</a> · In immediate danger, call 112.</p>
  </main>
</div>
<script>
(() => {{
  const btn = document.querySelector('.menu'), side = document.getElementById('side');
  btn.addEventListener('click', () => {{ const open = side.classList.toggle('open'); btn.setAttribute('aria-expanded', open); }});
  const filter = document.querySelector('.filter');
  filter.addEventListener('input', () => {{
    const q = filter.value.trim().toLowerCase();
    side.querySelectorAll('li').forEach(li => li.hidden = q && !li.textContent.toLowerCase().includes(q));
    side.querySelectorAll('h3').forEach(h => h.hidden = q && ![...h.nextElementSibling.children].some(li => !li.hidden));
  }});
  const toc = document.querySelector('.toc');
  if (toc) document.querySelectorAll('.doc h2[id]').forEach(h => {{ const a = document.createElement('a'); a.href = '#' + h.id; a.textContent = h.textContent; toc.appendChild(a); }});
}})();
</script>
</body>
</html>
"""


def sidebar(current):
    out = []
    for s in SECTIONS:
        out.append(f"<h3>{s}</h3><ul>")
        for f, t, sec, _ in PAGES:
            if sec == s:
                cls = ' class="current"' if f == current else ""
                out.append(f'<li{cls}><a href="{f}">{t}</a></li>')
        out.append("</ul>")
    return "\n    ".join(out)


def build():
    for i, (f, t, s, body) in enumerate(PAGES):
        prev = PAGES[i - 1] if i > 0 else None
        nxt = PAGES[i + 1] if i + 1 < len(PAGES) else None
        pager = ""
        if prev:
            pager += f'<a class="prev" href="{prev[0]}">← {prev[1]}</a>'
        if nxt:
            pager += f'<a class="next" href="{nxt[0]}">{nxt[1]} →</a>'
        toc = '<nav class="toc" aria-label="On this page"></nav>' if body.count("<h2 ") > 2 else ""
        html = TEMPLATE.format(title=t, sidebar=sidebar(f), body=toc + "\n" + body, pager=pager)
        with open(os.path.join(OUT, f), "w", encoding="utf-8") as fh:
            fh.write(html)
        print("wrote", f)


if __name__ == "__main__":
    build()
