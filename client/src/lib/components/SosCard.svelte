<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { Button } from "#lib/components/ui/button/index.js";
	import { Siren, AlertCircle, CheckCircle2, Info } from "lucide-svelte";
	import { emergencyService } from "#lib/services/emergencyService.svelte.js";
	import { telemetryBeacon, BEACON_INTERVALS } from "#lib/services/telemetryBeaconService.svelte.js";
	import { appSettings } from "#lib/services/appSettings.svelte.js";

	let sending = $state(false);
	let duration = $state(telemetryBeacon.durationMinutes);

	// Re-render "ends at" once a second while the beacon runs.
	let now = $state(Date.now());
	$effect(() => {
		const t = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(t);
	});

	let minutesLeft = $derived(
		telemetryBeacon.endsAt ? Math.max(0, Math.ceil((telemetryBeacon.endsAt - now) / 60000)) : null
	);

	async function sos() {
		sending = true;
		await emergencyService.triggerSos("sos");
		sending = false;
	}
</script>

<Card.Root class="border-2 border-red-600/50 bg-red-950/30 rounded-2xl">
	<Card.Header class="pb-2">
		<div class="flex items-center gap-2">
			<Siren class="h-5 w-5 text-red-400" />
			<Card.Title class="text-base font-bold">Emergency SOS</Card.Title>
		</div>
	</Card.Header>
	<Card.Content class="space-y-3">
		{#if emergencyService.countdown}
			<div class="rounded-xl border-2 border-amber-500 bg-amber-950/70 p-4 text-center space-y-3" role="alert">
				<p class="text-sm font-bold text-amber-200">
					{emergencyService.countdown.reason === "fall" ? "Fall detected." : "Safety timer ended."} Sending SOS in
				</p>
				<p class="text-5xl font-black text-amber-300">{emergencyService.countdown.seconds}s</p>
				<Button variant="secondary" class="w-full h-12 text-base font-bold" onclick={() => emergencyService.cancelCountdown()}>
					I'm OK, cancel
				</Button>
			</div>
		{/if}

		<button
			type="button"
			onclick={sos}
			disabled={sending || !appSettings.gatewayNumber}
			class="w-full h-24 rounded-2xl bg-red-600 text-3xl font-black tracking-widest text-white shadow-lg active:scale-[0.98] disabled:opacity-50"
		>
			{sending ? "SENDING…" : "SOS"}
		</button>

		{#if !appSettings.gatewayNumber}
			<p class="flex items-center gap-2 text-xs text-red-300">
				<AlertCircle class="h-4 w-4" /> Set the gateway phone number in Settings to enable SOS.
			</p>
		{/if}

		{#if emergencyService.status}
			<p
				class="flex items-center gap-2 text-xs {emergencyService.status.type === 'error'
					? 'text-red-300'
					: emergencyService.status.type === 'success'
						? 'text-emerald-300'
						: 'text-muted-foreground'}"
			>
				{#if emergencyService.status.type === "error"}<AlertCircle class="h-4 w-4 shrink-0" />{:else}<CheckCircle2 class="h-4 w-4 shrink-0" />{/if}
				{emergencyService.status.text}
			</p>
		{/if}

		{#if telemetryBeacon.isActive}
			<div class="flex items-center justify-between rounded-xl bg-background/60 px-3 py-2 text-xs">
				<span>
					Beacon on ({telemetryBeacon.trigger}) · sent <b>#{telemetryBeacon.updatesSentCount}</b>
					{#if telemetryBeacon.lastSentTime}· last {telemetryBeacon.lastSentTime}{/if}
					{#if minutesLeft !== null}· stops in {minutesLeft} min{/if}
				</span>
				<Button size="sm" variant="secondary" onclick={() => telemetryBeacon.stopBeacon()}>Stop</Button>
			</div>
		{/if}

		<label class="flex items-center gap-2 text-xs font-semibold">
			<input
				type="checkbox"
				checked={emergencyService.autoSosOnFall}
				onchange={(e) => emergencyService.setAutoSosOnFall((e.currentTarget as HTMLInputElement).checked)}
			/>
			Auto SOS on fall (15 s countdown to cancel)
		</label>
		<label class="flex items-center gap-2 text-xs font-semibold">
			Beacon duration
			<input
				type="number"
				min="1"
				max="240"
				class="w-16 rounded-md border border-border bg-background px-2 py-1"
				bind:value={duration}
				onchange={() => telemetryBeacon.setDuration(Number(duration))}
			/>
			min
		</label>
		<label class="flex items-center gap-2 text-xs font-semibold">
			Update every
			<select
				class="rounded-md border border-border bg-background px-2 py-1"
				value={telemetryBeacon.intervalSeconds}
				onchange={(e) => telemetryBeacon.setIntervalSeconds(Number((e.currentTarget as HTMLSelectElement).value))}
			>
				{#each BEACON_INTERVALS as s}
					<option value={s}>{s} s</option>
				{/each}
			</select>
			<span class="font-normal text-muted-foreground">(shorter when travelling)</span>
		</label>
		<p class="flex items-start gap-2 text-[11px] text-muted-foreground">
			<Info class="h-3.5 w-3.5 shrink-0 mt-0.5" />
			Fall detection and the beacon run while this app is open. Android may pause them when the app is in the background or
			the screen is off for long; keep the app open during an emergency.
		</p>
	</Card.Content>
</Card.Root>
