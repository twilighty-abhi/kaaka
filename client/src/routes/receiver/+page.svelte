<script lang="ts">
	import { onMount, onDestroy } from "svelte";
	import { defaultSmsManager } from "#lib/services/defaultSmsService.svelte.js";
	import {
		ArrowLeft,
		ShieldCheck,
		AlertTriangle,
		Bell,
		MessageSquare,
		CheckCircle2,
		Clock,
		Radio,
		Send,
		Sliders
	} from "lucide-svelte";

	let testSender = $state("9495364448");
	let testMessage = $state("CRITICAL ALERT: Emergency fall detected at coordinates (9.9312, 76.2673)");

	onMount(async () => {
		await defaultSmsManager.initialize();
	});

	onDestroy(() => {
		defaultSmsManager.destroy();
	});

	function handleSetDefault() {
		defaultSmsManager.requestDefault();
	}

	function handleSimulate() {
		if (testSender && testMessage) {
			defaultSmsManager.simulateTestTrigger(testSender, testMessage);
		}
	}
</script>

<div class="min-h-screen bg-background text-foreground flex flex-col pb-12">
	<!-- Top App Header -->
	<header class="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur-xl px-4 sm:px-6 pt-safe pb-4 sm:pb-5 shadow-md">
		<div class="mx-auto flex max-w-5xl items-center justify-between gap-3">
			<div class="flex items-center gap-3 sm:gap-4">
				<a
					href="/"
					class="flex h-11 w-11 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-2xl bg-secondary/80 text-foreground ring-1 ring-border/60 hover:bg-secondary transition-all active:scale-95"
					title="Back to Dashboard"
				>
					<ArrowLeft class="h-6 w-6" />
				</a>

				<div class="min-w-0">
					<div class="flex items-center gap-2.5 flex-wrap">
						<h1 class="text-xl sm:text-2xl font-black tracking-tight truncate">SMS Receiver</h1>
						<span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-secondary border border-border/60 {defaultSmsManager.isNative ? 'text-emerald-400' : 'text-amber-400'}">
							{defaultSmsManager.isNative ? "Android Native" : "Web Preview"}
						</span>
					</div>
					<p class="text-xs sm:text-sm text-muted-foreground truncate mt-0.5">
						Default SMS Role & Emergency Trigger Monitor
					</p>
				</div>
			</div>

			<!-- Status Indicator -->
			<div class="flex items-center shrink-0">
				<div class="flex items-center gap-2 px-3 py-1.5 rounded-xl border {defaultSmsManager.isDefault ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' : 'border-amber-500/30 bg-amber-500/10 text-amber-400'}">
					<span class="h-2 w-2 rounded-full {defaultSmsManager.isDefault ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}"></span>
					<span class="text-xs font-bold font-mono uppercase tracking-wider">
						{defaultSmsManager.isDefault ? "Default SMS Active" : "Not Default"}
					</span>
				</div>
			</div>
		</div>
	</header>

	<main class="mx-auto w-full max-w-5xl flex-1 px-4 sm:px-6 pt-6 flex flex-col gap-6">

		<!-- Default Role Warning / Confirmation Banner -->
		{#if !defaultSmsManager.isDefault}
			<div class="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-lg backdrop-blur-sm">
				<div class="flex items-start gap-3.5">
					<div class="p-2.5 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
						<AlertTriangle class="h-6 w-6" />
					</div>
					<div class="space-y-1">
						<h3 class="font-bold text-amber-300 text-sm sm:text-base">Default Messaging Role Required</h3>
						<p class="text-xs sm:text-sm text-amber-200/80 leading-relaxed">
							Android requires this app to be set as the system's <strong>Default SMS App</strong> to intercept incoming messages, wake up the screen, and sound high-priority vibration alarms.
						</p>
					</div>
				</div>
				<button
					type="button"
					onclick={handleSetDefault}
					class="shrink-0 w-full sm:w-auto px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-black text-sm tracking-wide transition-all shadow-md active:scale-95 cursor-pointer"
				>
					Grant Default Role
				</button>
			</div>
		{:else}
			<div class="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex items-center justify-between gap-4">
				<div class="flex items-center gap-3">
					<div class="p-2 rounded-xl bg-emerald-500/20 text-emerald-400">
						<CheckCircle2 class="h-5 w-5" />
					</div>
					<div>
						<h4 class="font-bold text-emerald-300 text-sm">System Default Messenger Enabled</h4>
						<p class="text-xs text-emerald-200/70">
							Incoming SMS from authorized emergency numbers will trigger automatic foreground wake lock and alarms.
						</p>
					</div>
				</div>
				<span class="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/20 px-2.5 py-1 rounded-lg">
					ROLE_SMS: GRANTED
				</span>
			</div>
		{/if}

		<!-- Filter & Protocol Info Card -->
		<div class="rounded-2xl border border-border/70 bg-card/60 backdrop-blur-sm p-5 flex flex-col gap-3">
			<div class="flex items-center justify-between border-b border-border/50 pb-3">
				<span class="text-xs font-mono font-bold text-muted-foreground uppercase tracking-wider">
					Authorized Trigger Target
				</span>
				<span class="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
					FILTER ACTIVE
				</span>
			</div>
			<div class="flex items-center justify-between">
				<div>
					<span class="text-2xl font-black font-mono tracking-tight text-foreground">
						{defaultSmsManager.authorizedNumber}
					</span>
					<p class="text-xs text-muted-foreground mt-1">
						Incoming messages from this suffix auto-wake the screen, trigger full-screen alarm intents, and execute high-priority vibration bursts.
					</p>
				</div>
				<div class="h-10 w-10 rounded-xl bg-secondary flex items-center justify-center text-primary">
					<ShieldCheck class="h-5 w-5" />
				</div>
			</div>
		</div>

		<!-- Live Trigger Log Section -->
		<div class="rounded-2xl border border-border/70 bg-card/60 backdrop-blur-sm p-5 flex flex-col gap-4">
			<div class="flex items-center justify-between border-b border-border/50 pb-3">
				<div class="flex items-center gap-2">
					<Bell class="h-4 w-4 text-primary" />
					<h3 class="font-bold text-sm sm:text-base">Trigger Monitor</h3>
				</div>
				<span class="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-secondary text-foreground">
					[{defaultSmsManager.triggerCount} Triggers Recorded]
				</span>
			</div>

			<!-- Latest Trigger Card -->
			{#if defaultSmsManager.lastTrigger}
				<div class="rounded-xl border border-primary/40 bg-primary/10 p-4 flex flex-col gap-3">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2 text-primary font-bold text-sm">
							<Radio class="h-4 w-4 animate-pulse" />
							<span>Latest Emergency Trigger</span>
						</div>
						<div class="flex items-center gap-1.5 text-xs font-mono text-muted-foreground">
							<Clock class="h-3.5 w-3.5" />
							<span>{defaultSmsManager.lastTrigger.timeFormatted}</span>
						</div>
					</div>

					<div class="font-mono text-sm bg-background/80 rounded-lg p-3 border border-border/60 text-foreground break-words">
						"{defaultSmsManager.lastTrigger.message}"
					</div>

					<div class="flex items-center justify-between text-xs pt-1">
						<span class="font-mono text-muted-foreground">
							From: <strong class="text-foreground">{defaultSmsManager.lastTrigger.sender}</strong>
						</span>
						<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono font-bold text-[11px] border border-emerald-500/30">
							[AUTO-OPENED & VIBRATED]
						</span>
					</div>
				</div>
			{:else}
				<div class="rounded-xl border border-dashed border-border/80 p-8 text-center flex flex-col items-center justify-center gap-2 text-muted-foreground">
					<div class="h-10 w-10 rounded-full bg-secondary flex items-center justify-center text-muted-foreground/60 mb-1">
						<Radio class="h-5 w-5 animate-pulse" />
					</div>
					<p class="text-sm font-semibold text-foreground">Standing by for incoming SMS</p>
					<p class="text-xs max-w-sm">
						Listening for emergency broadcasts sent from authorized phone numbers or simulated test events.
					</p>
				</div>
			{/if}

			<!-- History of Previous Triggers -->
			{#if defaultSmsManager.triggerHistory.length > 1}
				<div class="mt-2 flex flex-col gap-2">
					<h4 class="text-xs font-mono font-bold text-muted-foreground uppercase tracking-wider">
						Trigger History ({defaultSmsManager.triggerHistory.length - 1} earlier)
					</h4>
					<div class="flex flex-col gap-2 max-h-60 overflow-y-auto pr-1">
						{#each defaultSmsManager.triggerHistory.slice(1) as item (item.timestamp)}
							<div class="rounded-lg border border-border/50 bg-secondary/40 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
								<div class="min-w-0">
									<div class="flex items-center gap-2">
										<strong class="font-mono text-foreground">{item.sender}</strong>
										<span class="text-muted-foreground text-[11px] font-mono">{item.timeFormatted}</span>
									</div>
									<p class="text-muted-foreground truncate mt-0.5">"{item.message}"</p>
								</div>
								<span class="shrink-0 font-mono text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded self-start sm:self-auto">
									DELIVERED
								</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		<!-- Testing / Simulation Panel -->
		<div class="rounded-2xl border border-border/70 bg-card/60 backdrop-blur-sm p-5 flex flex-col gap-4">
			<div class="flex items-center justify-between border-b border-border/50 pb-3">
				<div class="flex items-center gap-2">
					<Sliders class="h-4 w-4 text-primary" />
					<h3 class="font-bold text-sm sm:text-base">Trigger Simulator</h3>
				</div>
				<span class="text-xs font-mono text-muted-foreground">Local / Preview Test</span>
			</div>

			<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
				<div class="flex flex-col gap-1.5 sm:col-span-1">
					<label for="testSender" class="text-xs font-mono text-muted-foreground">Sender Number</label>
					<input
						id="testSender"
						type="text"
						bind:value={testSender}
						class="px-3 py-2 rounded-xl bg-background border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
						placeholder="9495364448"
					/>
				</div>
				<div class="flex flex-col gap-1.5 sm:col-span-2">
					<label for="testMsg" class="text-xs font-mono text-muted-foreground">Alert Message</label>
					<div class="flex gap-2">
						<input
							id="testMsg"
							type="text"
							bind:value={testMessage}
							class="flex-1 px-3 py-2 rounded-xl bg-background border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
							placeholder="Simulated fall alert..."
						/>
						<button
							type="button"
							onclick={handleSimulate}
							class="px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs tracking-wide transition-all active:scale-95 flex items-center gap-1.5 shrink-0 cursor-pointer"
						>
							<Send class="h-3.5 w-3.5" />
							<span>Simulate</span>
						</button>
					</div>
				</div>
			</div>
		</div>

	</main>
</div>
