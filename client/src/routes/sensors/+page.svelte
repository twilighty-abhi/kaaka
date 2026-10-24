<script lang="ts">
	import { onMount, onDestroy } from "svelte";
	import * as Alert from "#lib/components/ui/alert/index.js";

	import PedometerCard from "#lib/components/PedometerCard.svelte";
	import AccelerometerCard from "#lib/components/AccelerometerCard.svelte";
	import GyroscopeCard from "#lib/components/GyroscopeCard.svelte";
	import MagnetometerCard from "#lib/components/MagnetometerCard.svelte";
	import AmbientLightCard from "#lib/components/AmbientLightCard.svelte";
	import SmsSenderCard from "#lib/components/SmsSenderCard.svelte";

	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import {
		Play,
		Square,
		ShieldCheck,
		Sliders,
		ArrowLeft,
		Cpu,
		Footprints,
		Gauge,
		MessageSquare
	} from "lucide-svelte";

	onMount(async () => {
		await sensorManager.initialize();
		if (!sensorManager.isListening) {
			await sensorManager.start();
		}
	});
</script>

<div class="min-h-screen bg-background text-foreground flex flex-col pb-8">
	<!-- Enlarged Top Menu Bar with Back Button -->
	<header class="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur-xl px-4 sm:px-6 pt-safe pb-4 sm:pb-5 shadow-md">
		<div class="mx-auto flex max-w-5xl items-center justify-between gap-3">
			<div class="flex items-center gap-3 sm:gap-4">
				<a
					href="/"
					class="flex h-11 w-11 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-2xl bg-secondary/80 text-foreground ring-1 ring-border/60 hover:bg-secondary transition-all active:scale-95"
					title="Back to Home"
				>
					<ArrowLeft class="h-6 w-6" />
				</a>

				<div class="min-w-0">
					<div class="flex items-center gap-2.5 flex-wrap">
						<h1 class="text-xl sm:text-2xl md:text-3xl font-black tracking-tight truncate">All Sensors</h1>
						<span class="text-xs font-semibold text-emerald-400">
							{sensorManager.isNative ? "Android" : "Web Preview"}
						</span>
					</div>
					<p class="text-xs sm:text-sm text-muted-foreground truncate mt-0.5">
						Hardware Telemetry Suite
					</p>
				</div>
			</div>

			<!-- Live Frequency Display in Menu Bar -->
			<div class="flex items-center gap-3 shrink-0">
				<a
					href="/receiver"
					class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-secondary/80 text-foreground ring-1 ring-border/60 hover:bg-secondary text-xs font-bold transition-all active:scale-95"
					title="SMS Receiver Monitor"
				>
					<MessageSquare class="h-4 w-4 text-emerald-400" />
					<span class="hidden sm:inline">SMS Receiver</span>
				</a>

				<div class="flex items-baseline gap-1 text-right">
					<span class="text-2xl sm:text-3xl font-black text-emerald-400">
						{sensorManager.isListening ? sensorManager.updateRateHz : 0}
					</span>
					<span class="text-xs font-bold text-emerald-400/70">Hz</span>
				</div>
			</div>
		</div>
	</header>

	<!-- Main Body Content: All Sensors Grid (Scrollable) -->
	<main class="mx-auto w-full max-w-5xl flex-1 px-3.5 sm:px-4 pt-4 sm:pt-6 space-y-5 pb-20 sm:pb-24">
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

		<!-- All Sensors Data Grid Directly Below Menu Bar -->
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
			<!-- Pedometer -->
			<div class="col-span-1 md:col-span-2 lg:col-span-1">
				<PedometerCard />
			</div>

			<!-- Accelerometer -->
			<div class="col-span-1">
				<AccelerometerCard />
			</div>

			<!-- Gyroscope -->
			<div class="col-span-1">
				<GyroscopeCard />
			</div>

			<!-- Magnetometer -->
			<div class="col-span-1">
				<MagnetometerCard />
			</div>

			<!-- Ambient Light -->
			<div class="col-span-1">
				<AmbientLightCard />
			</div>

			<!-- Hardware Diagnostic Card with Lucide Icons (No Nested Tiles) -->
			<div class="col-span-1 flex flex-col justify-between rounded-2xl border border-border/70 bg-card/90 p-4 sm:p-5 shadow-md backdrop-blur-xl">
				<div>
					<div class="flex items-center justify-between pb-2">
						<div class="flex items-center gap-2">
							<Sliders class="h-4 w-4 text-emerald-400" />
							<span class="text-xs font-bold uppercase tracking-wider text-foreground">Hardware Status</span>
						</div>
						<span class="text-xs font-semibold text-emerald-400">Capacitor 7</span>
					</div>
					<p class="text-xs text-muted-foreground mt-1">
						Package: <span class="text-foreground font-semibold">com.kaaka.sensors</span>
					</p>

					<div class="mt-4 space-y-2.5 text-xs">
						<div class="flex justify-between items-center py-1 border-b border-border/40">
							<span class="text-muted-foreground flex items-center gap-1.5">
								<Cpu class="h-3.5 w-3.5 text-emerald-400" />
								<span>Platform Engine:</span>
							</span>
							<span class="font-bold text-foreground">{sensorManager.isNative ? "Android Native" : "Web Preview"}</span>
						</div>
						<div class="flex justify-between items-center py-1 border-b border-border/40">
							<span class="text-muted-foreground flex items-center gap-1.5">
								<Footprints class="h-3.5 w-3.5 text-emerald-400" />
								<span>Step Detector:</span>
							</span>
							<span class="font-bold text-emerald-400">{sensorManager.status.pedometerHardwareAvailable ? "Hardware" : "Software"}</span>
						</div>
						<div class="flex justify-between items-center py-1">
							<span class="text-muted-foreground flex items-center gap-1.5">
								<Gauge class="h-3.5 w-3.5 text-emerald-400" />
								<span>Update Rate:</span>
							</span>
							<span class="font-bold text-emerald-400">{sensorManager.updateRateHz} updates/sec</span>
						</div>
					</div>
				</div>

				<div class="pt-3 border-t border-border/50 mt-3 text-center">
					<span class="text-[11px] text-muted-foreground font-medium">Continuous synchronization</span>
				</div>
			</div>
		</div>

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
