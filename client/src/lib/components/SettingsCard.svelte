<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { Input } from "#lib/components/ui/input/index.js";
	import { Button } from "#lib/components/ui/button/index.js";
	import { Settings, AlertCircle, CheckCircle2 } from "lucide-svelte";
	import { appSettings } from "#lib/services/appSettings.svelte.js";
	import { Capacitor, registerPlugin } from "@capacitor/core";
	import { onMount } from "svelte";

	interface ReceiveSmsPlugin {
		checkReceiveSms(): Promise<{ granted: boolean }>;
		requestReceiveSms(): Promise<{ granted: boolean }>;
	}
	const DefaultSms = registerPlugin<ReceiveSmsPlugin>("DefaultSms");
	const isNative = Capacitor.isNativePlatform();

	// Lets the app see the Kaaka number's reply SMS (and start the beacon) without being the default SMS app.
	let receiveSms = $state<boolean | null>(null);
	onMount(async () => {
		if (isNative) receiveSms = (await DefaultSms.checkReceiveSms()).granted;
	});
	async function allowReceiveSms() {
		receiveSms = (await DefaultSms.requestReceiveSms()).granted;
	}

	let gatewayNumber = $state(appSettings.gatewayNumber);
	let serverUrl = $state(appSettings.serverUrl);
	let backendUrl = $state(appSettings.backendUrl);
	let saved = $state(false);

	// Only the gateway number is required; the computer settings are optional extras.
	let missing = $derived(!appSettings.gatewayNumber);

	function handleSave(e: Event) {
		e.preventDefault();
		appSettings.save({ gatewayNumber, serverUrl, backendUrl });
		saved = true;
		setTimeout(() => (saved = false), 3000);
	}
</script>

<Card.Root class="border-border/70 bg-card/90 rounded-2xl">
	<Card.Header class="pb-2">
		<div class="flex items-center gap-2">
			<Settings class="h-5 w-5 text-primary" />
			<Card.Title class="text-base font-bold">Settings</Card.Title>
		</div>
		{#if missing}
			<div class="mt-2 flex items-start gap-2 rounded-xl border border-red-500/50 bg-red-950/60 px-3 py-2 text-xs text-red-200">
				<AlertCircle class="h-4 w-4 shrink-0 text-red-400" />
				<span>Not set: gateway phone number. The emergency beacon stays off until it is set.</span>
			</div>
		{/if}
	</Card.Header>
	<Card.Content>
		{#if isNative && receiveSms !== null}
			<div class="mb-3 rounded-xl border border-border/70 px-3 py-2 text-xs">
				<div class="flex items-center justify-between gap-2">
					<span class="font-semibold">Start beacon when the Kaaka number replies</span>
					{#if receiveSms}
						<span class="text-emerald-400 font-semibold">on</span>
					{:else}
						<Button type="button" size="sm" onclick={allowReceiveSms}>Allow</Button>
					{/if}
				</div>
				{#if !receiveSms}
					<p class="mt-1 text-muted-foreground">Needs the "receive SMS" permission. Without it, the reply from the Kaaka number cannot start the beacon (SOS still works).</p>
				{/if}
				<p class="mt-1 text-muted-foreground">On Xiaomi/MIUI also enable: Autostart, "Show on lock screen" and "Display pop-up windows while running in the background" for Kaaka Sensors.</p>
			</div>
		{/if}
		<form onsubmit={handleSave} class="space-y-3">
			<label class="block space-y-1 text-xs font-semibold">
				<span>Gateway phone number (alert recipient and authorized trigger sender)</span>
				<Input type="tel" bind:value={gatewayNumber} placeholder="+91XXXXXXXXXX" />
			</label>
			<label class="block space-y-1 text-xs font-semibold">
				<span>Computer dashboard WebSocket (optional)</span>
				<Input type="url" bind:value={serverUrl} placeholder="ws://<mac-ip>:8765" />
			</label>
			<label class="block space-y-1 text-xs font-semibold">
				<span>Live sensor stream URL (optional)</span>
				<Input type="url" bind:value={backendUrl} placeholder="http://<mac-ip>:8080" />
			</label>
			<p class="text-[11px] text-muted-foreground">
				Kaaka works phone-to-phone with only the gateway number. The two optional URLs just copy alerts and live
				readings to a computer dashboard if one is running.
			</p>
			<div class="flex items-center gap-3">
				<Button type="submit">Save</Button>
				{#if saved}
					<span class="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 class="h-4 w-4" /> Saved</span>
				{/if}
			</div>
		</form>
	</Card.Content>
</Card.Root>
