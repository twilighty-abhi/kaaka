<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { Button } from "#lib/components/ui/button/index.js";
	import { Timer, Info } from "lucide-svelte";
	import { emergencyService } from "#lib/services/emergencyService.svelte.js";
	import { appSettings } from "#lib/services/appSettings.svelte.js";

	const presets = [15, 30, 60, 120];
	let minutes = $state(emergencyService.safetyMinutes);

	// Re-render the time left once a second.
	let now = $state(Date.now());
	$effect(() => {
		const t = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(t);
	});

	let remaining = $derived(
		emergencyService.safetyDeadline === null ? null : Math.max(0, emergencyService.safetyDeadline - now)
	);

	function formatLeft(ms: number): string {
		const total = Math.ceil(ms / 1000);
		const h = Math.floor(total / 3600);
		const m = Math.floor((total % 3600) / 60);
		const s = total % 60;
		const mm = String(m).padStart(2, "0");
		const ss = String(s).padStart(2, "0");
		return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
	}
</script>

<Card.Root class="border-2 border-sky-600/40 bg-sky-950/20 rounded-2xl">
	<Card.Header class="pb-2">
		<div class="flex items-center gap-2">
			<Timer class="h-5 w-5 text-sky-400" />
			<Card.Title class="text-base font-bold">Safety timer</Card.Title>
		</div>
	</Card.Header>
	<Card.Content class="space-y-3">
		{#if remaining !== null}
			<div class="text-center space-y-1">
				<p class="text-xs text-muted-foreground">Check in before the timer ends</p>
				<p class="text-4xl font-black tabular-nums">{formatLeft(remaining)}</p>
				<p class="text-[11px] text-muted-foreground">
					ends at {new Date(emergencyService.safetyDeadline ?? 0).toLocaleTimeString()}
				</p>
			</div>
			<button
				type="button"
				onclick={() => emergencyService.checkIn()}
				class="w-full h-16 rounded-2xl bg-emerald-600 text-xl font-black text-white shadow active:scale-[0.98]"
			>
				I'm safe
			</button>
			<Button variant="secondary" class="w-full" onclick={() => emergencyService.extendSafetyTimer(15)}>
				Extend +15 min
			</Button>
		{:else if emergencyService.countdown?.reason === "safety timer"}
			<p class="text-xs text-amber-300">Timer ended. Cancel the countdown in the SOS card if you are safe.</p>
		{:else}
			<p class="text-xs text-muted-foreground">
				If you don't check in before the timer ends, Kaaka counts down 30 seconds and then sends SOS to the gateway number.
			</p>
			<div class="flex flex-wrap gap-2">
				{#each presets as p (p)}
					<Button size="sm" variant={minutes === p ? "default" : "secondary"} onclick={() => (minutes = p)}>
						{p < 60 ? `${p} min` : `${p / 60} h`}
					</Button>
				{/each}
				<label class="flex items-center gap-1 text-xs">
					<input
						type="number"
						min="1"
						max="720"
						class="w-16 rounded-md border border-border bg-background px-2 py-1"
						bind:value={minutes}
					/>
					min
				</label>
			</div>
			<Button
				class="w-full"
				disabled={!appSettings.gatewayNumber || !(Number(minutes) > 0)}
				onclick={() => emergencyService.startSafetyTimer(Number(minutes))}
			>
				Start safety timer
			</Button>
		{/if}
		<p class="flex items-start gap-2 text-[11px] text-muted-foreground">
			<Info class="h-3.5 w-3.5 shrink-0 mt-0.5" />
			The timer is checked while the app is open and as soon as you reopen it; Android may delay it in the background. If
			it ended while the app was closed, the countdown starts when you reopen the app.
		</p>
	</Card.Content>
</Card.Root>
