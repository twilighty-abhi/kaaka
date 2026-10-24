<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { Input } from "#lib/components/ui/input/index.js";
	import { Button } from "#lib/components/ui/button/index.js";
	import { Settings, AlertCircle, CheckCircle2 } from "lucide-svelte";
	import { appSettings } from "#lib/services/appSettings.svelte.js";

	let gatewayNumber = $state(appSettings.gatewayNumber);
	let serverUrl = $state(appSettings.serverUrl);
	let backendUrl = $state(appSettings.backendUrl);
	let saved = $state(false);

	// Settings the user still has to fill in; shown as a warning so nothing silently falls back.
	let missing = $derived(
		[
			!appSettings.gatewayNumber && "gateway phone number",
			!appSettings.serverUrl && "Mac server address",
			!appSettings.backendUrl && "telemetry backend URL"
		].filter(Boolean) as string[]
	);

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
		{#if missing.length}
			<div class="mt-2 flex items-start gap-2 rounded-xl border border-red-500/50 bg-red-950/60 px-3 py-2 text-xs text-red-200">
				<AlertCircle class="h-4 w-4 shrink-0 text-red-400" />
				<span>Not set: {missing.join(", ")}. Alerts are not sent anywhere that is not configured.</span>
			</div>
		{/if}
	</Card.Header>
	<Card.Content>
		<form onsubmit={handleSave} class="space-y-3">
			<label class="block space-y-1 text-xs font-semibold">
				<span>Gateway phone number (alert recipient and authorized trigger sender)</span>
				<Input type="tel" bind:value={gatewayNumber} placeholder="+91XXXXXXXXXX" />
			</label>
			<label class="block space-y-1 text-xs font-semibold">
				<span>Mac server WebSocket</span>
				<Input type="url" bind:value={serverUrl} placeholder="ws://<mac-ip>:8765" />
			</label>
			<label class="block space-y-1 text-xs font-semibold">
				<span>Telemetry backend</span>
				<Input type="url" bind:value={backendUrl} placeholder="http://<mac-ip>:3001" />
			</label>
			<div class="flex items-center gap-3">
				<Button type="submit">Save</Button>
				{#if saved}
					<span class="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 class="h-4 w-4" /> Saved</span>
				{/if}
			</div>
		</form>
	</Card.Content>
</Card.Root>
