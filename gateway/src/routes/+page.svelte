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
  }

  interface GatewaySettings {
    rejectCalls: boolean;
    replyMessage: string;
    dashboardUrl: string;
  }

  interface GatewayEvent {
    type: 'call' | 'alert';
    timestamp: string;
    number?: string;
    state?: string;
    sms?: string;
    sender?: string;
    text?: string;
  }

  interface GatewayPlugin {
    getStatus(): Promise<GatewayStatus>;
    requestScreeningRole(): Promise<GatewayStatus>;
    requestSmsPermissions(): Promise<GatewayStatus>;
    getSettings(): Promise<GatewaySettings>;
    saveSettings(options: GatewaySettings): Promise<void>;
    getEvents(): Promise<{ events: GatewayEvent[] }>;
    clearEvents(): Promise<void>;
  }

  const DirectSms = registerPlugin<DirectSmsPlugin>('DirectSms');
  const Gateway = registerPlugin<GatewayPlugin>('Gateway');
  const isNative = Capacitor.isNativePlatform();

  const SETTINGS_KEY = 'kaaka_gateway_settings';
  const defaultReply = 'received call. will get back to you shortly.';
  const numberPlaceholder = '+91XXXXXXXXXX';
  const dashboardPlaceholder = 'http://<mac-ip>:8080 (optional)';

  // Setup status (call screening role + SMS permissions)
  let status = $state<GatewayStatus | null>(null);

  // Settings used by the native call screening service
  let rejectCalls = $state(true);
  let replyMessage = $state(defaultReply);
  let dashboardUrl = $state('');
  let showSettings = $state(false);

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

  async function loadSettings() {
    let saved: Partial<GatewaySettings> = {};
    try {
      saved = isNative ? await Gateway.getSettings() : JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
    } catch {
      saved = {};
    }
    rejectCalls = saved.rejectCalls ?? true;
    replyMessage = saved.replyMessage || defaultReply;
    dashboardUrl = saved.dashboardUrl ?? '';
  }

  async function handleSaveSettings(e: Event) {
    e.preventDefault();
    const url = dashboardUrl.trim().replace(/\/+$/, '');
    if (url && !/^https?:\/\//.test(url)) {
      statusMessage = { text: 'dashboard server must start with http:// or https://', type: 'error' };
      return;
    }
    const settings: GatewaySettings = {
      rejectCalls,
      replyMessage: replyMessage.trim() || defaultReply,
      dashboardUrl: url,
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    try {
      if (isNative) await Gateway.saveSettings(settings);
      dashboardUrl = url;
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
        <label class="field-label" for="reply-input">auto-reply message</label>
        <textarea id="reply-input" rows={2} bind:value={replyMessage} class="tech-textarea"></textarea>
        <label class="field-label" for="dashboard-input">dashboard server</label>
        <div class="config-input-group">
          <input
            id="dashboard-input"
            type="url"
            bind:value={dashboardUrl}
            placeholder={dashboardPlaceholder}
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
              {#if ev.type === 'call'}
                <span>call {ev.number || 'hidden number'} · {ev.state} · sms {ev.sms}</span>
              {:else}
                <span>alert from {ev.sender || 'unknown'}</span>
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
