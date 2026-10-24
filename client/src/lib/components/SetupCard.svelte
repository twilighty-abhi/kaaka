<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { Button } from "#lib/components/ui/button/index.js";
	import { ShieldCheck, AlertCircle } from "lucide-svelte";
	import { Capacitor, registerPlugin } from "@capacitor/core";
	import { onMount } from "svelte";

	interface SetupStatus {
		sms: boolean;
		location: boolean;
		notifications: boolean;
		activity: boolean;
		batteryExempt: boolean;
		vendor: string;
	}
	interface KaakaSetupPlugin {
		getStatus(): Promise<SetupStatus>;
		requestAll(): Promise<SetupStatus>;
		requestBatteryExemption(): Promise<void>;
		openPhoneSettings(): Promise<void>;
	}
	const KaakaSetup = registerPlugin<KaakaSetupPlugin>("KaakaSetup");
	const isNative = Capacitor.isNativePlatform();
	const ASKED_KEY = "kaaka_setup_asked";

	let status = $state<SetupStatus | null>(null);

	const rows = $derived(
		status
			? [
					{ label: "SMS (send SOS, start beacon on Kaaka reply)", ok: status.sms },
					{ label: "Location (GPS in reports)", ok: status.location },
					{ label: "Notifications (emergency alarm)", ok: status.notifications },
					{ label: "Physical activity (step counter)", ok: status.activity }
				]
			: []
	);
	const permissionsOk = $derived(rows.every((r) => r.ok));
	const isXiaomi = $derived(!!status && /xiaomi|redmi|poco/.test(status.vendor));

	async function refresh() {
		if (isNative) status = await KaakaSetup.getStatus();
	}

	async function allowAll() {
		status = await KaakaSetup.requestAll();
	}

	onMount(() => {
		if (!isNative) return;
		(async () => {
			await refresh();
			// Ask once per app start, never in a loop (a declined request must not re-open itself).
			if (status && !permissionsOk && !sessionStorage.getItem(ASKED_KEY)) {
				sessionStorage.setItem(ASKED_KEY, "1");
				await allowAll();
			}
		})();
		const onVisible = () => {
			if (document.visibilityState === "visible") refresh();
		};
		document.addEventListener("visibilitychange", onVisible);
		return () => document.removeEventListener("visibilitychange", onVisible);
	});
</script>

{#if isNative && status && !(permissionsOk && status.batteryExempt)}
	<Card.Root class="border-amber-500/50 bg-card/90 rounded-2xl">
		<Card.Header class="pb-2">
			<div class="flex items-center gap-2">
				<AlertCircle class="h-5 w-5 text-amber-400" />
				<Card.Title class="text-base font-bold">Finish setup</Card.Title>
			</div>
		</Card.Header>
		<Card.Content class="space-y-2 text-xs">
			{#each rows as row}
				<div class="flex items-center justify-between gap-2">
					<span>{row.label}</span>
					<span class={row.ok ? "text-emerald-400 font-semibold" : "text-red-400 font-semibold"}>{row.ok ? "allowed" : "missing"}</span>
				</div>
			{/each}
			{#if !permissionsOk}
				<Button class="w-full" onclick={allowAll}>Allow all</Button>
				<p class="text-muted-foreground">If a permission stays missing after "Allow all", Android will not ask again: use "Open phone settings" and allow it there.</p>
			{/if}
			<div class="flex items-center justify-between gap-2 pt-1">
				<span>Battery optimisation (keep running in background)</span>
				{#if status.batteryExempt}
					<span class="text-emerald-400 font-semibold">exempt</span>
				{:else}
					<Button size="sm" variant="outline" onclick={() => KaakaSetup.requestBatteryExemption()}>Exempt</Button>
				{/if}
			</div>
			<div class="flex items-center justify-between gap-2">
				<span>{isXiaomi ? "MIUI: Autostart, Show on lock screen, Pop-up windows in background" : "Phone settings for this app"}</span>
				<Button size="sm" variant="outline" onclick={() => KaakaSetup.openPhoneSettings()}>Open phone settings</Button>
			</div>
		</Card.Content>
	</Card.Root>
{:else if isNative && status}
	<div class="flex items-center gap-2 text-xs text-emerald-400">
		<ShieldCheck class="h-4 w-4" />
		<span>Setup complete</span>
	</div>
{/if}
