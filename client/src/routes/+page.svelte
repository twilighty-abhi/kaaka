<script lang="ts">
	import { onMount, onDestroy } from "svelte";
	import * as Alert from "#lib/components/ui/alert/index.js";
	import * as Card from "#lib/components/ui/card/index.js";

	import MagnetometerCard from "#lib/components/MagnetometerCard.svelte";
	import PedometerCard from "#lib/components/PedometerCard.svelte";
	import AmbientLightCard from "#lib/components/AmbientLightCard.svelte";
	import TelemetryBeaconCard from "#lib/components/TelemetryBeaconCard.svelte";
	import SmsSenderCard from "#lib/components/SmsSenderCard.svelte";
	import SettingsCard from "#lib/components/SettingsCard.svelte";
	import SosCard from "#lib/components/SosCard.svelte";
	import SafetyTimerCard from "#lib/components/SafetyTimerCard.svelte";
	import logo from "#lib/assets/logo.png";

	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import { defaultSmsManager } from "#lib/services/defaultSmsService.svelte.js";
	import { telemetryBeacon } from "#lib/services/telemetryBeaconService.svelte.js";
	import {
		Play,
		Square,
		ShieldCheck,
		Activity,
		ChevronRight,
		Compass,
		Zap,
		SunMedium,
		Sliders,
		MessageSquare,
		Radio
	} from "lucide-svelte";

	onMount(async () => {
		await defaultSmsManager.initialize();
		await sensorManager.initialize();
		await sensorManager.start();
	});

	onDestroy(() => {
		sensorManager.destroy();
	});
</script>

<div class="min-h-screen bg-background text-foreground flex flex-col pb-8">
	<!-- Enlarged Top Menu Bar with safe-area padding -->
	<header class="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur-xl px-4 sm:px-6 pt-safe pb-4 sm:pb-5 shadow-md">
		<div class="mx-auto flex max-w-5xl items-center justify-between gap-3">
			<div class="flex items-center gap-3.5 sm:gap-4">
				<div class="flex h-13 w-13 sm:h-15 sm:w-15 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/80 text-primary-foreground shadow-lg ring-1 ring-primary/30 overflow-hidden p-1.5">
					<img src={logo} alt="Kaaka Logo" class="h-full w-full object-contain rounded-xl" />
				</div>
				<div class="min-w-0">
					<div class="flex items-center gap-2.5 flex-wrap">
						<h1 class="text-xl sm:text-2xl md:text-3xl font-black tracking-tight truncate">Kaaka Sensors</h1>
						<span class="text-xs font-semibold text-emerald-400">
							{sensorManager.isNative ? "Android" : "Web Preview"}
						</span>
					</div>
					<p class="text-xs sm:text-sm text-muted-foreground truncate mt-0.5">
						Hardware Telemetry
					</p>
				</div>
			</div>

			<!-- Live Frequency Display in Menu Bar -->
			<div class="flex items-center shrink-0">
				<div class="flex items-baseline gap-1 text-right">
					<span class="text-2xl sm:text-3xl font-black text-emerald-400">
						{sensorManager.isListening ? sensorManager.updateRateHz : 0}
					</span>
					<span class="text-xs font-bold text-emerald-400/70">Hz</span>
				</div>
			</div>
		</div>
	</header>

	<!-- Main Body Content (Scrollable) -->
	<main class="mx-auto w-full max-w-5xl flex-1 px-3.5 sm:px-4 pt-4 sm:pt-6 space-y-5 pb-20 sm:pb-24">
		<!-- SOS first, then settings and the beacon -->
		<SosCard />

		<SafetyTimerCard />

		<SettingsCard />

		<TelemetryBeaconCard />

		<!-- Android Activity Permission Notice if needed -->
		{#if sensorManager.isNative && !sensorManager.status.hasActivityRecognitionPermission}
			<Alert.Root class="border-emerald-600/40 bg-emerald-950/40 text-emerald-200 rounded-2xl">
				<ShieldCheck class="h-5 w-5 text-emerald-400" />
				<Alert.Title class="text-sm font-bold">Permission Required for Pedometer</Alert.Title>
				<Alert.Description class="text-xs mt-1">
					Activity Recognition permission is needed for Android hardware step tracking.
				</Alert.Description>
			</Alert.Root>
		{/if}

		<!-- Sensor Data Directly Below Menu Bar: ONLY Compass, Pedometer, and Light Meter -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-5">
			<!-- 1. Compass (Magnetometer) -->
			<div class="col-span-1">
				<MagnetometerCard />
			</div>

			<!-- 2. Pedometer -->
			<div class="col-span-1">
				<PedometerCard />
			</div>

			<!-- 3. Light Meter -->
			<div class="col-span-1">
				<AmbientLightCard />
			</div>
		</div>

		<!-- See All Sensors in a 4x1 Matrix -->
		<a
			href="/sensors"
			class="group block transition-all duration-200 active:scale-[0.99] focus:outline-none"
			title="See All Sensors"
		>
			<Card.Root class="overflow-hidden border-2 border-primary/30 bg-gradient-to-r from-card via-card to-primary/5 rounded-2xl p-4 sm:p-5 shadow-lg transition-all group-hover:border-primary/60 group-hover:shadow-primary/10">
				<div class="flex items-center justify-between pb-3">
					<div class="flex items-center gap-2.5">
						<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
							<Sliders class="h-4 w-4" />
						</div>
						<div>
							<h3 class="text-sm sm:text-base font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
								See All Sensors
							</h3>
							<p class="text-xs text-muted-foreground">
								Full 5-axis telemetry, angular rotation, diagnostics & more
							</p>
						</div>
					</div>

					<div class="flex items-center gap-1.5 text-xs font-bold text-primary bg-primary/10 px-3 py-1.5 rounded-xl border border-primary/20 group-hover:bg-primary/20 transition-all">
						<span>View Full Suite</span>
						<ChevronRight class="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
					</div>
				</div>

				<!-- 4x1 Matrix (4 Columns x 1 Row) with Lucide Icons (No Nested Tiles) -->
				<div class="grid grid-cols-4 gap-2 pt-3 border-t border-border/50 text-center">
					<!-- Cell 1: Accelerometer -->
					<div class="flex flex-col items-center">
						<Activity class="h-4 w-4 text-emerald-400 mb-1" />
						<div class="text-[11px] font-bold text-foreground truncate w-full">Accel</div>
						<div class="text-[10px] sm:text-[11px] text-emerald-300 font-semibold truncate w-full">
							{sensorManager.accelerometer.magnitude.toFixed(1)} m/s²
						</div>
					</div>

					<!-- Cell 2: Gyroscope -->
					<div class="flex flex-col items-center">
						<Compass class="h-4 w-4 text-emerald-400 mb-1" />
						<div class="text-[11px] font-bold text-foreground truncate w-full">Gyro</div>
						<div class="text-[10px] sm:text-[11px] text-emerald-300 font-semibold truncate w-full">
							{sensorManager.gyroscope.rate.toFixed(1)} rad/s
						</div>
					</div>

					<!-- Cell 3: Compass -->
					<div class="flex flex-col items-center">
						<Zap class="h-4 w-4 text-emerald-400 mb-1" />
						<div class="text-[11px] font-bold text-foreground truncate w-full">Compass</div>
						<div class="text-[10px] sm:text-[11px] text-emerald-300 font-semibold truncate w-full">
							{Math.round(sensorManager.magnetometer.heading)}° {sensorManager.magnetometer.cardinal}
						</div>
					</div>

					<!-- Cell 4: Photometer & Steps -->
					<div class="flex flex-col items-center">
						<SunMedium class="h-4 w-4 text-emerald-400 mb-1" />
						<div class="text-[11px] font-bold text-foreground truncate w-full">Light</div>
						<div class="text-[10px] sm:text-[11px] text-emerald-300 font-semibold truncate w-full">
							{Math.round(sensorManager.ambientLight.lux)} lx
						</div>
					</div>
				</div>
			</Card.Root>
		</a>

		<!-- Default SMS Receiver & Trigger Monitor Route Link -->
		<a
			href="/receiver"
			class="group block transition-all duration-200 active:scale-[0.99] focus:outline-none"
			title="SMS Receiver & Emergency Alert Trigger Monitor"
		>
			<Card.Root class="overflow-hidden border border-border/80 bg-card/60 backdrop-blur-sm rounded-2xl p-4 sm:p-5 shadow-md transition-all group-hover:border-primary/60 group-hover:shadow-primary/10">
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-3">
						<div class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
							<MessageSquare class="h-5 w-5" />
						</div>
						<div>
							<h3 class="text-sm sm:text-base font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
								SMS Receiver & Emergency Trigger
							</h3>
							<p class="text-xs text-muted-foreground">
								Default SMS handler, alarm vibrations & emergency auto-open
							</p>
						</div>
					</div>

					<div class="flex items-center gap-1.5 text-xs font-bold text-primary bg-primary/10 px-3 py-1.5 rounded-xl border border-primary/20 group-hover:bg-primary/20 transition-all">
						<span>Open Monitor</span>
						<ChevronRight class="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
					</div>
				</div>
			</Card.Root>
		</a>

		<!-- Direct SMS Alert Box -->
		<SmsSenderCard />
	</main>

	<!-- Stagnant Fixed Bottom Bar -->
	<div class="fixed bottom-0 left-0 right-0 z-40 px-4 py-2.5 pb-safe bg-background/90 backdrop-blur-2xl border-t border-border/80 shadow-[0_-8px_30px_rgba(0,0,0,0.6)]">
		<div class="mx-auto max-w-md">
			{#if sensorManager.isListening}
				<button
					type="button"
					class="w-full h-11 sm:h-12 text-sm sm:text-base font-bold rounded-xl shadow-lg shadow-emerald-950/70 transition-all duration-200 active:scale-[0.98] bg-gradient-to-r from-emerald-800 via-emerald-700 to-emerald-800 hover:from-emerald-750 hover:via-emerald-650 hover:to-emerald-750 text-white border border-emerald-400/40 ring-1 ring-emerald-400/20 cursor-pointer flex items-center justify-center gap-2"
					onclick={() => sensorManager.stop()}
				>
					<Square class="h-4.5 w-4.5 fill-current" />
					<span class="tracking-wide">Stop Sensors</span>
				</button>
			{:else}
				<button
					type="button"
					class="w-full h-11 sm:h-12 text-sm sm:text-base font-bold rounded-xl shadow-lg shadow-emerald-950/60 transition-all duration-200 active:scale-[0.98] bg-gradient-to-r from-emerald-600 via-emerald-500 to-emerald-600 hover:from-emerald-500 hover:to-emerald-500 text-white border border-emerald-400/40 ring-1 ring-emerald-400/20 cursor-pointer flex items-center justify-center gap-2"
					onclick={() => sensorManager.start()}
				>
					<Play class="h-4.5 w-4.5 fill-current" />
					<span class="tracking-wide">Start Sensors</span>
				</button>
			{/if}
		</div>
	</div>
</div>
