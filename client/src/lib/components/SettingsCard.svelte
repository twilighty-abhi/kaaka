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
