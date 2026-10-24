<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Capacitor, registerPlugin } from '@capacitor/core';

  interface DirectSmsPlugin {
    sendSms(options: { number: string; message: string }): Promise<void>;
  }

  const DirectSms = registerPlugin<DirectSmsPlugin>('DirectSms');

  // No defaults on purpose: the user must enter the Mac server address and recipients.
  const numberPlaceholder = '+91XXXXXXXXXX';
  const serverUrlPlaceholder = 'ws://<mac-ip>:8765';
  const defaultMessage = 'received call. will get back to you shortly.';

  let phoneNumber = $state('');
  let message = $state(defaultMessage);
  let statusMessage = $state.raw<{ text: string; type: 'success' | 'error' } | null>(null);
  let isSending = $state(false);

  let serverUrl = $state('');
  let wsConnected = $state(false);
  let autoSend = $state(true);
  let showSettings = $state(false);

  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let lastAutoSent: { number: string; time: number } | null = null;

  async function sendSmsMessage(targetNumber: string, content: string, isAutomated = false) {
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

    if (Capacitor.isNativePlatform()) {
      try {
        await DirectSms.sendSms({
          number: sanitizedNumber,
          message: messageContent,
        });

        statusMessage = {
          text: `sent to ${rawNumber}`,
          type: 'success'
        };

        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'SMS_SENT',
            number: rawNumber,
            automated: isAutomated,
            timestamp: new Date().toISOString(),
          }));
        }
      } catch (err: unknown) {
        console.error('Direct SMS error:', err);
        const errorMsg = err instanceof Error ? err.message : String(err);
        statusMessage = { text: `failed: ${errorMsg.toLowerCase()}`, type: 'error' };
      } finally {
        isSending = false;
      }
    } else {
      try {
        window.location.href = `sms:${sanitizedNumber}?body=${encodeURIComponent(messageContent)}`;
        statusMessage = { text: `sms link opened`, type: 'success' };
      } catch (err) {
        console.error('Web SMS error:', err);
        window.open(`sms:${sanitizedNumber}?body=${encodeURIComponent(messageContent)}`, '_system');
      } finally {
        isSending = false;
      }
    }
  }

  function connectWebSocket() {
    if (typeof window === 'undefined') return;
    if (!serverUrl.trim()) {
      wsConnected = false;
      showSettings = true;
      statusMessage = { text: 'server address not set: enter ws://<mac-ip>:8765 in [config]', type: 'error' };
      return;
    }

    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      if (ws) {
        try { ws.close(); } catch {}
      }

      ws = new WebSocket(serverUrl);

      ws.onopen = () => {
        wsConnected = true;
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
        console.log('Connected to WebSocket server:', serverUrl);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WS Message received:', data);

          if (data.type === 'CALL_DETECTED' && data.number) {
            const incomingNumber = data.number;
            phoneNumber = incomingNumber;

            const now = Date.now();
            if (lastAutoSent && lastAutoSent.number === incomingNumber && now - lastAutoSent.time < 3000) {
              console.log('Debounced duplicate CALL_DETECTED within 3s');
              return;
            }

            lastAutoSent = { number: incomingNumber, time: now };

            if (autoSend) {
              sendSmsMessage(incomingNumber, message, true);
            } else {
              statusMessage = {
                text: `call: ${incomingNumber}`,
                type: 'success'
              };
            }
          } else if (data.type === 'SERVER_READY') {
            if (data.last_number && !phoneNumber) {
              phoneNumber = data.last_number;
            }
          }
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      };

      ws.onclose = () => {
        wsConnected = false;
        if (reconnectTimer) clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = (err) => {
        console.warn('WS Error:', err);
      };
    } catch (err) {
      console.error('WS Connection error:', err);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connectWebSocket, 3000);
    }
  }

  onMount(() => {
    const savedUrl = localStorage.getItem('kaaka_ws_url');
    if (savedUrl) {
      serverUrl = savedUrl;
    }
    connectWebSocket();
  });

  onDestroy(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  });

  function handleManualSend(e: Event) {
    e.preventDefault();
    sendSmsMessage(phoneNumber, message, false);
  }

  function handleSaveSettings(e: Event) {
    e.preventDefault();
    serverUrl = serverUrl.trim();
    localStorage.setItem('kaaka_ws_url', serverUrl);
    showSettings = false;
    statusMessage = null;
    // Drop any connection to the old address so the new one is used.
    if (ws) {
      ws.onclose = null;
      try { ws.close(); } catch {}
      ws = null;
    }
    connectWebSocket();
  }

  function resetNumber() {
    phoneNumber = '';
    statusMessage = null;
  }
</script>

<div class="app-container">
  <main class="system-panel">
    <!-- Header -->
    <header class="panel-header">
      <h1 class="brand-title">kaaka</h1>
      <div class="header-right">
        <span class="status-indicator {wsConnected ? 'online' : 'offline'}">
          {wsConnected ? 'online' : serverUrl.trim() ? 'connecting' : 'no server'}
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

    <!-- Configuration Drawer -->
    {#if showSettings}
      <form onsubmit={handleSaveSettings} class="config-drawer">
        <label class="field-label" for="ws-input">endpoint</label>
        <div class="config-input-group">
          <input
            id="ws-input"
            type="text"
            bind:value={serverUrl}
            placeholder={serverUrlPlaceholder}
            class="config-input"
          />
          <button type="submit" class="config-submit-btn">
            apply
          </button>
        </div>
      </form>
    {/if}

    <!-- Form Section -->
    <form onsubmit={handleManualSend} class="panel-form">
      <!-- Auto-dispatch Toggle -->
      <label class="control-row" for="auto-toggle">
        <input
          id="auto-toggle"
          type="checkbox"
          bind:checked={autoSend}
          class="raw-checkbox"
        />
        <span class="control-label">auto-dispatch</span>
      </label>

      <!-- Target Recipient Number -->
      <div class="field-group">
        <div class="field-meta-row">
          <label class="field-label" for="phone-input">to</label>
          <button type="button" class="field-text-btn" onclick={resetNumber}>
            [reset]
          </button>
        </div>
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

      <!-- Message Payload -->
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

      <!-- Action Button -->
      <button
        type="submit"
        id="send-button"
        class="submit-btn"
        disabled={isSending}
      >
        {isSending ? 'sending...' : 'send'}
      </button>
    </form>

    <!-- Status Banner -->
    {#if statusMessage}
      <div class="status-banner {statusMessage.type}" role="status">
        {statusMessage.text}
      </div>
    {/if}
  </main>
</div>
