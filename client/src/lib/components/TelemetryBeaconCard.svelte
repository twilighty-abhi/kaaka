<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { telemetryBeacon } from "#lib/services/telemetryBeaconService.svelte.js";
	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import {
		Radio,
		Square,
		Play,
		RotateCw,
		Send,
		CheckCircle2,
		AlertCircle,
		ShieldAlert,
		Clock,
		Flame
	} from "lucide-svelte";

	let targetInput = $state("9495364448");

	$effect(() => {
		if (telemetryBeacon.targetNumber) {
			targetInput = telemetryBeacon.targetNumber;
		}
	});

	function handleStart() {
		telemetryBeacon.startBeacon(targetInput.trim() || "9495364448");
	}

	function handleStop() {
		telemetryBeacon.stopBeacon();
	}

	async function handleSendNow() {
		await telemetryBeacon.sendImmediateUpdate();
	}
</script>

{#if telemetryBeacon.isActive}
	<!-- ACTIVE TELEMETRY BEACON (Pulsing Red Emergency Mode) -->
	<div class="relative overflow-hidden rounded-2xl border-2 border-red-500/80 bg-gradient-to-b from-red-950/60 via-card to-card p-4 sm:p-5 shadow-2xl shadow-red-950/60 ring-2 ring-red-500/30 transition-all">
		<!-- Pulsing background glow -->
		<div class="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-red-600/20 blur-3xl animate-pulse"></div>

		<!-- Header -->
		<div class="flex items-center justify-between pb-3 border-b border-red-900/50">
			<div class="flex items-center gap-2.5">
				<div class="relative flex h-3.5 w-3.5">
					<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
					<span class="relative inline-flex rounded-full h-3.5 w-3.5 bg-red-500"></span>
				</div>
				<div>
					<div class="flex items-center gap-2">
						<h2 class="text-base sm:text-lg font-black tracking-tight text-red-100 flex items-center gap-1.5">
							<ShieldAlert class="h-5 w-5 text-red-400" />
							LIVE TELEMETRY ACTIVE
						</h2>
						<span class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-red-500 text-white tracking-wider animate-pulse">
							60s Loop
						</span>
					</div>
					<p class="text-xs text-red-200/80 mt-0.5">
						Streaming 5 sensors + GPS coordinates to Gateway <span class="font-bold text-white font-mono">{telemetryBeacon.targetNumber}</span>
					</p>
				</div>
			</div>

			<div class="text-right">
				<div class="text-xs font-semibold text-red-300/80">Dispatched</div>
				<div class="text-xl sm:text-2xl font-black text-white font-mono">
					#{telemetryBeacon.updatesSentCount}
				</div>
			</div>
		</div>

		<!-- Countdown & Status Section -->
		<div class="py-4 space-y-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2 text-xs sm:text-sm font-semibold text-muted-foreground">
					<Clock class="h-4 w-4 text-red-400" />
					<span>Next Server Update In:</span>
				</div>
				<div class="flex items-baseline gap-1">
					<span class="text-2xl sm:text-3xl font-black text-red-400 font-mono">
						{telemetryBeacon.secondsRemaining}
					</span>
					<span class="text-xs font-bold text-red-400/80">sec</span>
				</div>
			</div>

			<!-- Visual Progress Bar (60s tick) -->
			<div class="w-full bg-red-950/80 rounded-full h-2.5 overflow-hidden border border-red-900/60">
				<div
					class="bg-gradient-to-r from-red-600 to-amber-500 h-2.5 rounded-full transition-all duration-1000 ease-linear"
					style="width: {((60 - telemetryBeacon.secondsRemaining) / 60) * 100}%"
				></div>
			</div>

			<!-- Live Sensor Values Snippet -->
			<div class="grid grid-cols-3 sm:grid-cols-5 gap-2 pt-1 text-center text-[11px] font-mono">
				<div class="bg-card/70 border border-border/60 rounded-lg p-1.5">
					<div class="text-[10px] text-muted-foreground uppercase">Steps</div>
					<div class="font-bold text-foreground truncate">{sensorManager.pedometer.steps}</div>
				</div>
				<div class="bg-card/70 border border-border/60 rounded-lg p-1.5">
					<div class="text-[10px] text-muted-foreground uppercase">Light</div>
					<div class="font-bold text-foreground truncate">{Math.round(sensorManager.ambientLight.lux)} lx</div>
				</div>
				<div class="bg-card/70 border border-border/60 rounded-lg p-1.5">
					<div class="text-[10px] text-muted-foreground uppercase">Accel</div>
					<div class="font-bold text-foreground truncate">{sensorManager.accelerometer.magnitude.toFixed(1)}</div>
				</div>
				<div class="bg-card/70 border border-border/60 rounded-lg p-1.5">
					<div class="text-[10px] text-muted-foreground uppercase">Gyro</div>
					<div class="font-bold text-foreground truncate">{sensorManager.gyroscope.rate.toFixed(1)}</div>
				</div>
				<div class="bg-card/70 border border-border/60 rounded-lg p-1.5 col-span-2 sm:col-span-1">
					<div class="text-[10px] text-muted-foreground uppercase">Heading</div>
					<div class="font-bold text-foreground truncate">{Math.round(sensorManager.magnetometer.heading)}° {sensorManager.magnetometer.cardinal}</div>
				</div>
			</div>

			<!-- Status Feedback Message -->
			{#if telemetryBeacon.status}
				<div class="flex items-center gap-2 text-xs py-1.5 px-2.5 rounded-lg border {telemetryBeacon.status.type === 'error' ? 'bg-red-950/80 border-red-500/50 text-red-200' : 'bg-emerald-950/60 border-emerald-500/40 text-emerald-200'}">
					{#if telemetryBeacon.status.type === 'error'}
						<AlertCircle class="h-4 w-4 shrink-0 text-red-400" />
					{:else}
						<CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
					{/if}
					<span class="truncate">{telemetryBeacon.status.text}</span>
				</div>
			{/if}
		</div>

		<!-- Action Buttons: Large Red Stop Button & Immediate Send -->
		<div class="flex flex-col sm:flex-row gap-2.5 pt-1">
			<!-- Prominent Red Stop Button -->
			<button
				type="button"
				class="flex-1 h-13 sm:h-14 bg-red-600 hover:bg-red-700 active:bg-red-800 active:scale-[0.98] text-white font-black text-sm sm:text-base uppercase tracking-wider rounded-xl shadow-xl shadow-red-950/80 border-2 border-red-400/80 flex items-center justify-center gap-2.5 transition-all cursor-pointer"
				onclick={handleStop}
			>
				<Square class="h-5 w-5 fill-current" />
				<span>Stop Telemetry Updates</span>
			</button>

			<!-- Send Now Button -->
			<button
				type="button"
				class="h-13 sm:h-14 px-5 bg-card hover:bg-muted active:scale-[0.98] text-foreground font-bold text-xs sm:text-sm rounded-xl border border-border/80 flex items-center justify-center gap-2 transition-all cursor-pointer shrink-0 disabled:opacity-50"
				disabled={telemetryBeacon.isSending}
				onclick={handleSendNow}
			>
				{#if telemetryBeacon.isSending}
					<RotateCw class="h-4 w-4 animate-spin text-primary" />
					<span>Sending...</span>
				{:else}
					<Send class="h-4 w-4 text-primary" />
					<span>Send Now</span>
				{/if}
			</button>
		</div>
	</div>
{:else}
	<!-- INACTIVE / STANDBY TELEMETRY BEACON -->
	<div class="relative overflow-hidden rounded-2xl border border-border/80 bg-card/80 backdrop-blur-xl p-4 sm:p-5 shadow-lg transition-all hover:border-primary/40">
		<div class="flex items-center justify-between pb-3 border-b border-border/60">
			<div class="flex items-center gap-3">
				<div class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
					<Radio class="h-5 w-5" />
				</div>
				<div>
					<div class="flex items-center gap-2">
						<h2 class="text-base sm:text-lg font-bold tracking-tight text-foreground">
							Telemetry Beacon
						</h2>
						<span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-muted text-muted-foreground tracking-wider">
							Standby
						</span>
					</div>
					<p class="text-xs text-muted-foreground mt-0.5">
						Recurring 60s live 5-sensor telemetry + GPS coords to Server via SMS
					</p>
				</div>
			</div>

			{#if telemetryBeacon.updatesSentCount > 0}
				<div class="text-right text-xs text-muted-foreground">
					Total sent: <span class="font-bold text-foreground font-mono">#{telemetryBeacon.updatesSentCount}</span>
				</div>
			{/if}
		</div>

		<!-- Status Message if any -->
		{#if telemetryBeacon.status}
			<div class="my-3 flex items-center gap-2 text-xs py-2 px-3 rounded-xl bg-muted/60 border border-border/70 text-foreground">
				<CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
				<span class="truncate">{telemetryBeacon.status.text}</span>
			</div>
		{/if}

		<!-- Standby Controls -->
		<div class="pt-3 space-y-3">
			<div class="flex flex-col sm:flex-row gap-2.5">
				<!-- Target Number Input -->
				<div class="flex-1 flex items-center rounded-xl border border-border bg-background/80 px-3 py-1.5 focus-within:ring-2 focus-within:ring-primary/40">
					<span class="text-xs font-semibold text-muted-foreground mr-2 shrink-0">To:</span>
					<input
						type="tel"
						bind:value={targetInput}
						placeholder="Gateway phone number (e.g. 9495364448)"
						class="w-full bg-transparent text-xs sm:text-sm font-mono text-foreground focus:outline-none"
					/>
				</div>

				<!-- Start Beacon Button -->
				<button
					type="button"
					class="h-11 sm:h-12 px-6 bg-gradient-to-r from-emerald-600 via-emerald-500 to-emerald-600 hover:from-emerald-500 hover:to-emerald-500 active:scale-[0.98] text-white font-bold text-xs sm:text-sm uppercase tracking-wider rounded-xl shadow-lg shadow-emerald-950/60 border border-emerald-400/40 flex items-center justify-center gap-2 transition-all cursor-pointer"
					onclick={handleStart}
				>
					<Play class="h-4 w-4 fill-current" />
					<span>Start 60s Telemetry</span>
				</button>
			</div>
		</div>
	</div>
{/if}
