<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Capacitor, registerPlugin } from '@capacitor/core';

  interface DirectSmsPlugin {
    sendSms(options: { number: string; message: string }): Promise<void>;
  }

  interface GatewayStatus {
    screeningSupported: boolean;
    screeningRole: boolean;
    sendSms: boolean;
    receiveSms: boolean;
    contactCalls: boolean;
    batteryExempt: boolean;
  }

  interface GatewaySettings {
    rejectCalls: boolean;
    replyMessage: string;
    dashboardUrl: string;
    responderNumbers: string;
    publicUrl: string;
    dashboardToken: string;
    escalateMinutes: number;
    maxRepliesPerHour: number;
    replyLanguage: ReplyLanguage;
  }

  type ReplyLanguage = 'en' | 'ml' | 'both';

  interface GatewayEvent {
    type: 'call' | 'alert' | 'ack' | 'escalation' | 'resolve' | 'safe';
    timestamp: string;
    number?: string;
    state?: string;
    sms?: string;
    via?: string;
    token?: string;
    locationLink?: boolean;
    responder?: string;
    smsToCaller?: string;
    responders?: number;
    respondersFailed?: number;
    sender?: string;
    text?: string;
    message?: string;
    rateLimited?: boolean;
    kind?: string;
    note?: string;
  }

  interface GatewayPlugin {
    getStatus(): Promise<GatewayStatus>;
    requestScreeningRole(): Promise<GatewayStatus>;
    requestSmsPermissions(): Promise<GatewayStatus>;
    requestCallPermissions(): Promise<GatewayStatus>;
    requestBatteryExemption(): Promise<GatewayStatus>;
    getSettings(): Promise<GatewaySettings>;
    saveSettings(options: GatewaySettings): Promise<void>;
    getEvents(): Promise<{ events: GatewayEvent[] }>;
    clearEvents(): Promise<void>;
  }

  const DirectSms = registerPlugin<DirectSmsPlugin>('DirectSms');
  const Gateway = registerPlugin<GatewayPlugin>('Gateway');
  const isNative = Capacitor.isNativePlatform();

  const SETTINGS_KEY = 'kaaka_gateway_settings';
  const defaultReply = 'Kaaka received your call. Help is being arranged. If in immediate danger, call 112.';
  // Same texts as native GatewayText; the Malayalam text should be checked by a native speaker.
  const defaultReplyMl =
    'കാക്ക നിങ്ങളുടെ സന്ദേശം സ്വീകരിച്ചു. സഹായം ഏർപ്പാടാക്കുന്നു. അടിയന്തര അപകടത്തിലാണെങ്കിൽ 112-ൽ വിളിക്കുക.';
  const languageDefaults: Record<ReplyLanguage, string> = {
    en: defaultReply,
    ml: defaultReplyMl,
    both: `${defaultReply}\n${defaultReplyMl}`,
  };
  const oldDefaultReply = 'received call. will get back to you shortly.';
  const numberPlaceholder = '+91XXXXXXXXXX';
  const dashboardPlaceholder = 'http://<mac-ip>:8080 (optional)';

  // Setup status (call screening role + SMS permissions)
  let status = $state<GatewayStatus | null>(null);

  // Settings used by the native call screening service
  let rejectCalls = $state(true);
  // Empty = use the default reply for the chosen language.
  let replyMessage = $state('');
  let replyLanguage = $state<ReplyLanguage>('en');
  let escalateMinutes = $state(5);
  let maxRepliesPerHour = $state(3);
  let dashboardUrl = $state('');
  let responderNumbers = $state('');
  let publicUrl = $state('');
  let dashboardToken = $state('');
  // Browsers only allow location sharing on https pages, so the link needs an https public URL.
  const publicUrlInsecure = $derived(publicUrl.trim() !== '' && !/^https:\/\//.test(publicUrl.trim()));
  let showSettings = $state(false);

  // Same rule as native GatewayStore.responderNumbers: comma or new line separated, digits and +.
  const responderCount = $derived(
    new Set(
      responderNumbers
        .split(/[,\n]/)
        .map((n) => n.trim().replace(/[^0-9+]/g, ''))
        .filter((n) => n.replace('+', ''))
    ).size
  );

  // Recent events written by native code
  let events = $state<GatewayEvent[]>([]);
  let refreshTimer: ReturnType<typeof setInterval> | null = null;

  // Manual SMS
  let phoneNumber = $state('');
  let message = $state(defaultReply);
  let isSending = $state(false);
  let statusMessage = $state.raw<{ text: string; type: 'success' | 'error' } | null>(null);

  const ready = $derived(!!status && status.screeningRole && status.sendSms);

  function errorText(err: unknown) {
    return (err instanceof Error ? err.message : String(err)).toLowerCase();
  }

  async function refresh() {
    if (!isNative) return;
    try {
      status = await Gateway.getStatus();
      events = (await Gateway.getEvents()).events ?? [];
    } catch (err) {
      statusMessage = { text: `status error: ${errorText(err)}`, type: 'error' };
    }
  }

  async function requestRole() {
    try {
      status = await Gateway.requestScreeningRole();
      if (!status.screeningRole) statusMessage = { text: 'call screening not granted', type: 'error' };
    } catch (err) {
      statusMessage = { text: errorText(err), type: 'error' };
    }
  }

  async function requestSms() {
    try {
      status = await Gateway.requestSmsPermissions();
      if (!status.sendSms || !status.receiveSms) statusMessage = { text: 'sms permission not granted', type: 'error' };
    } catch (err) {
      statusMessage = { text: errorText(err), type: 'error' };
    }
  }

  async function requestCallPerms() {
    try {
      status = await Gateway.requestCallPermissions();
      if (!status.contactCalls) statusMessage = { text: 'call permissions not granted: calls from contacts are not handled', type: 'error' };
    } catch (err) {
      statusMessage = { text: errorText(err), type: 'error' };
    }
  }

  async function requestBattery() {
    try {
      status = await Gateway.requestBatteryExemption();
      if (!status.batteryExempt) statusMessage = { text: 'not exempt: android may delay calls and alerts while the phone sleeps', type: 'error' };
    } catch (err) {
      statusMessage = { text: errorText(err), type: 'error' };
    }
  }

  async function loadSettings() {
    let saved: Partial<GatewaySettings> = {};
    try {
      saved = isNative ? await Gateway.getSettings() : JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
    } catch {
      saved = {};
    }
    rejectCalls = saved.rejectCalls ?? true;
    const savedReply = (saved.replyMessage ?? '').trim();
    replyMessage = savedReply === oldDefaultReply || Object.values(languageDefaults).includes(savedReply) ? '' : savedReply;
    replyLanguage = saved.replyLanguage === 'ml' || saved.replyLanguage === 'both' ? saved.replyLanguage : 'en';
    escalateMinutes = Number.isFinite(saved.escalateMinutes) ? Number(saved.escalateMinutes) : 5;
    maxRepliesPerHour = Number.isFinite(saved.maxRepliesPerHour) ? Number(saved.maxRepliesPerHour) : 3;
    dashboardUrl = saved.dashboardUrl ?? '';
    responderNumbers = saved.responderNumbers ?? '';
    publicUrl = saved.publicUrl ?? '';
    dashboardToken = saved.dashboardToken ?? '';
  }

  async function handleSaveSettings(e: Event) {
    e.preventDefault();
    const url = dashboardUrl.trim().replace(/\/+$/, '');
    if (url && !/^https?:\/\//.test(url)) {
      statusMessage = { text: 'dashboard server must start with http:// or https://', type: 'error' };
      return;
    }
    const link = publicUrl.trim().replace(/\/+$/, '');
    if (link && !/^https?:\/\//.test(link)) {
      statusMessage = { text: 'public link url must start with https://', type: 'error' };
      return;
    }
    const escalate = Math.floor(Number(escalateMinutes));
    const maxReplies = Math.floor(Number(maxRepliesPerHour));
    if (!Number.isFinite(escalate) || escalate < 0 || !Number.isFinite(maxReplies) || maxReplies < 0) {
      statusMessage = { text: 'escalation minutes and reply limit must be 0 or more', type: 'error' };
      return;
    }
    const settings: GatewaySettings = {
      rejectCalls,
      replyMessage: replyMessage.trim(),
      replyLanguage,
      escalateMinutes: escalate,
      maxRepliesPerHour: maxReplies,
      dashboardUrl: url,
      responderNumbers: responderNumbers.trim(),
      publicUrl: link,
      dashboardToken: dashboardToken.trim(),
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    try {
      if (isNative) await Gateway.saveSettings(settings);
      dashboardUrl = url;
      publicUrl = link;
      showSettings = false;
      statusMessage = { text: 'settings saved', type: 'success' };
    } catch (err) {
      statusMessage = { text: `save failed: ${errorText(err)}`, type: 'error' };
    }
  }

  async function clearEvents() {
    if (!isNative) return;
    await Gateway.clearEvents();
    events = [];
  }

  async function sendSmsMessage(targetNumber: string, content: string) {
    const rawNumber = targetNumber.trim();
    const sanitizedNumber = rawNumber.replace(/[^0-9+*#]/g, '');
    const messageContent = content.trim();

    if (!sanitizedNumber) {
      statusMessage = { text: rawNumber ? 'invalid number' : 'no recipient number', type: 'error' };
      return;
    }
    if (!messageContent) {
      statusMessage = { text: 'empty message', type: 'error' };
      return;
    }

    isSending = true;
    statusMessage = null;
    try {
      if (isNative) {
        await DirectSms.sendSms({ number: sanitizedNumber, message: messageContent });
        statusMessage = { text: `sent to ${rawNumber}`, type: 'success' };
      } else {
        window.location.href = `sms:${sanitizedNumber}?body=${encodeURIComponent(messageContent)}`;
        statusMessage = { text: 'sms link opened', type: 'success' };
      }
    } catch (err) {
      statusMessage = { text: `failed: ${errorText(err)}`, type: 'error' };
    } finally {
      isSending = false;
    }
  }

  function handleManualSend(e: Event) {
    e.preventDefault();
    sendSmsMessage(phoneNumber, message);
  }

  function respondersText(ev: GatewayEvent) {
    if (ev.responders === undefined) return '';
    const failed = ev.respondersFailed ? ` (${ev.respondersFailed} failed)` : '';
    return ` · ${ev.responders} responders texted${failed}`;
  }

  function formatTime(iso: string) {
    const d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleString();
  }

  function onVisibility() {
    if (document.visibilityState === 'visible') refresh();
  }

  onMount(async () => {
    await loadSettings();
    await refresh();
    refreshTimer = setInterval(refresh, 5000);
    document.addEventListener('visibilitychange', onVisibility);
  });

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer);
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVisibility);
  });
</script>

<div class="app-container">
  <main class="system-panel">
    <!-- Header -->
    <header class="panel-header">
      <h1 class="brand-title">kaaka</h1>
      <div class="header-right">
        <span class="status-indicator {ready ? 'online' : 'offline'}">
          {ready ? 'active' : 'setup needed'}
        </span>
        <button
          type="button"
          class="header-action-btn"
          onclick={() => (showSettings = !showSettings)}
          aria-label="config"
        >
          {showSettings ? '[close]' : '[config]'}
        </button>
      </div>
    </header>

    <!-- Setup status -->
    {#if isNative && status}
      <section class="setup-list">
        <div class="setup-row">
          <span class="field-label">call screening</span>
          {#if !status.screeningSupported}
            <span class="setup-state bad">needs android 10+</span>
          {:else if status.screeningRole}
            <span class="setup-state ok">on</span>
          {:else}
            <button type="button" class="field-text-btn" onclick={requestRole}>[enable]</button>
          {/if}
        </div>
        <div class="setup-row">
          <span class="field-label">sms send / receive</span>
          {#if status.sendSms && status.receiveSms}
            <span class="setup-state ok">granted</span>
          {:else}
            <button type="button" class="field-text-btn" onclick={requestSms}>[allow]</button>
          {/if}
        </div>
        <div class="setup-row">
          <span class="field-label">calls from contacts</span>
          {#if status.contactCalls}
            <span class="setup-state ok">granted</span>
          {:else}
            <button type="button" class="field-text-btn" onclick={requestCallPerms}>[allow]</button>
          {/if}
        </div>
        <div class="setup-row">
          <span class="field-label">battery optimisation</span>
          {#if status.batteryExempt}
            <span class="setup-state ok">exempt</span>
          {:else}
            <button type="button" class="field-text-btn" onclick={requestBattery}>[exempt]</button>
          {/if}
        </div>
      </section>
    {:else if !isNative}
      <div class="status-banner error" role="status">
        call screening only works in the android app
      </div>
    {/if}

    <!-- Settings Drawer -->
    {#if showSettings}
      <form onsubmit={handleSaveSettings} class="config-drawer">
        <label class="control-row" for="reject-toggle">
          <input id="reject-toggle" type="checkbox" bind:checked={rejectCalls} class="raw-checkbox" />
          <span class="control-label">reject incoming calls</span>
        </label>
        <label class="field-label" for="language-input">reply language</label>
        <select id="language-input" bind:value={replyLanguage} class="config-input">
          <option value="en">english</option>
          <option value="ml">malayalam</option>
          <option value="both">both</option>
        </select>
        <label class="field-label" for="reply-input">custom auto-reply (empty = default for the language)</label>
        <textarea
          id="reply-input"
          rows={2}
          bind:value={replyMessage}
          placeholder={languageDefaults[replyLanguage]}
          class="tech-textarea"
        ></textarea>
        <label class="field-label" for="escalate-input">remind responders if not acknowledged after (minutes, 0 = off)</label>
        <input id="escalate-input" type="number" min="0" step="1" bind:value={escalateMinutes} class="config-input" />
        <label class="field-label" for="limit-input">max replies per number per hour (0 = no limit)</label>
        <input id="limit-input" type="number" min="0" step="1" bind:value={maxRepliesPerHour} class="config-input" />
        <label class="field-label" for="responders-input">
          responder numbers ({responderCount} set) — texted on every call and alert
        </label>
        <textarea
          id="responders-input"
          rows={2}
          bind:value={responderNumbers}
          placeholder="+91XXXXXXXXXX, +91XXXXXXXXXX (comma or new line)"
          class="tech-textarea"
        ></textarea>
        <label class="field-label" for="dashboard-input">dashboard server</label>
        <div class="config-input-group">
          <input
            id="dashboard-input"
            type="url"
            bind:value={dashboardUrl}
            placeholder={dashboardPlaceholder}
            class="config-input"
          />
        </div>
        <label class="field-label" for="public-url-input">public link url (location sharing)</label>
        <input
          id="public-url-input"
          type="url"
          bind:value={publicUrl}
          placeholder="https://<your-tunnel> (optional)"
          class="config-input"
        />
        {#if publicUrlInsecure}
          <p class="setup-state bad">not https: callers' browsers will block location sharing</p>
        {/if}
        <label class="field-label" for="token-input">dashboard token</label>
        <div class="config-input-group">
          <input
            id="token-input"
            type="password"
            autocomplete="off"
            bind:value={dashboardToken}
            placeholder="only if the server sets KAAKA_ADMIN_TOKEN"
            class="config-input"
          />
          <button type="submit" class="config-submit-btn">save</button>
        </div>
      </form>
    {/if}

    <!-- Recent events -->
    <section class="events">
      <div class="field-meta-row">
        <span class="field-label">recent events</span>
        {#if events.length}
          <button type="button" class="field-text-btn" onclick={clearEvents}>[clear]</button>
        {/if}
      </div>
      {#if events.length === 0}
        <p class="event-empty">no calls or alerts yet</p>
      {:else}
        <ul class="event-list">
          {#each events as ev, i (i)}
            <li class="event-item">
              <span class="event-time">{formatTime(ev.timestamp)}</span>
              {#if ev.type === 'call' && ev.state === 'sms'}
                <span>help sms {ev.number} · sms {ev.sms}{ev.rateLimited ? ' · rate-limited' : ''}{ev.locationLink ? ' + location link' : ''}{respondersText(ev)}</span>
                <span class="event-text">{ev.message}</span>
              {:else if ev.type === 'call'}
                <span>call {ev.number || 'hidden number'}{ev.via === 'phone_state' ? ' (contact)' : ''} · {ev.state} · sms {ev.sms}{ev.rateLimited ? ' · rate-limited' : ''}{ev.locationLink ? ' + location link' : ''}{respondersText(ev)}</span>
              {:else if ev.type === 'ack'}
                <span>ack {ev.number} by {ev.responder} · caller sms {ev.smsToCaller}</span>
              {:else if ev.type === 'escalation'}
                <span>reminder: {ev.kind || 'call'} {ev.number} unacknowledged{respondersText(ev)}</span>
              {:else if ev.type === 'safe'}
                <span>safe {ev.number} · incident closed · caller sms {ev.smsToCaller ?? '?'}{respondersText(ev)}</span>
              {:else if ev.type === 'resolve'}
                <span>resolved {ev.number} by {ev.responder}{ev.note ? ` · ${ev.note}` : ''}</span>
              {:else}
                <span>alert from {ev.sender || 'unknown'}{respondersText(ev)}</span>
                <span class="event-text">{ev.text}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <!-- Manual SMS -->
    <form onsubmit={handleManualSend} class="panel-form">
      <div class="field-group">
        <label class="field-label" for="phone-input">to</label>
        <input
          id="phone-input"
          type="tel"
          inputmode="tel"
          autocomplete="tel"
          bind:value={phoneNumber}
          oninput={() => (statusMessage = null)}
          placeholder={numberPlaceholder}
          class="tech-input"
          aria-label="recipient"
        />
      </div>

      <div class="field-group">
        <label class="field-label" for="message-input">message</label>
        <textarea
          id="message-input"
          rows={3}
          bind:value={message}
          oninput={() => (statusMessage = null)}
          placeholder="message..."
          class="tech-textarea"
          aria-label="message"
        ></textarea>
      </div>

      <button type="submit" id="send-button" class="submit-btn" disabled={isSending}>
        {isSending ? 'sending...' : 'send'}
      </button>
    </form>

    {#if statusMessage}
      <div class="status-banner {statusMessage.type}" role="status">
        {statusMessage.text}
      </div>
    {/if}
  </main>
</div>

<style>
  .setup-list,
  .events {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .setup-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .setup-state {
    font-size: 0.75rem;
    text-transform: lowercase;
  }
  .setup-state.ok {
    color: var(--text-bright);
  }
  .setup-state.bad {
    color: var(--text-dim);
  }
  .event-empty {
    color: var(--text-dim);
    font-size: 0.75rem;
    margin: 0;
  }
  .event-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-height: 14rem;
    overflow-y: auto;
  }
  .event-item {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    border-left: 1px solid var(--border-mid);
    padding-left: 0.5rem;
    font-size: 0.75rem;
    color: var(--text-mid);
  }
  .event-time {
    color: var(--text-dim);
  }
  .event-text {
    white-space: pre-wrap;
    color: var(--text-dim);
  }
</style>
