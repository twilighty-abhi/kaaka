<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { Progress } from "#lib/components/ui/progress/index.js";
	import Sparkline from "./Sparkline.svelte";
	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import { Footprints, Flame, Navigation, Zap } from "lucide-svelte";

	const DAILY_GOAL = 10000;
	let stepProgress = $derived(
		Math.min(100, Math.round((sensorManager.pedometer.steps / DAILY_GOAL) * 100))
	);
	let isWalking = $derived(sensorManager.isListening && sensorManager.accelerometer.magnitude > 10.5);
</script>

<Card.Root class="relative overflow-hidden border-border/70 bg-card/90 shadow-md backdrop-blur-xl transition-all hover:border-emerald-500/40 rounded-2xl">
	<!-- Subtle ambient color background blur -->
	<div class="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-emerald-500/10 blur-2xl"></div>

	<Card.Header class="pb-2">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30 shadow-sm">
					<Footprints class="h-6 w-6" />
				</div>
				<div>
					<Card.Title class="text-lg sm:text-xl font-bold tracking-tight">Pedometer</Card.Title>
					<Card.Description class="text-xs text-muted-foreground">Step Counter</Card.Description>
				</div>
			</div>

			<div class="text-xs font-semibold {isWalking ? 'text-emerald-400' : 'text-muted-foreground'}">
				{isWalking ? "Active" : "Idle"}
			</div>
		</div>
	</Card.Header>

	<Card.Content class="space-y-5 pt-2">
		<!-- Giant Step Counter Display -->
		<div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
			<div>
				<div class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
					Cumulative Steps
				</div>
				<div class="text-5xl sm:text-6xl font-black tracking-tight text-foreground leading-none">
					{sensorManager.pedometer.steps.toLocaleString()}
				</div>
			</div>
			<div class="flex justify-end sm:justify-start">
				<Sparkline
					data={sensorManager.stepHistory}
					strokeColor="#10b981"
					fillColor="rgba(16, 185, 129, 0.15)"
					height={46}
					width={140}
				/>
			</div>
		</div>

		<!-- Daily Goal Progress -->
		<div class="space-y-2 pt-1">
			<div class="flex items-center justify-between text-xs">
				<span class="text-muted-foreground font-medium">Daily Target: {DAILY_GOAL.toLocaleString()} steps</span>
				<span class="font-bold text-emerald-400 text-sm">{stepProgress}%</span>
			</div>
			<Progress value={stepProgress} class="h-2.5 bg-secondary/80" />
		</div>

		<!-- 3 Stat Metrics with Lucide Icons (No Nested Tiles) -->
		<div class="grid grid-cols-3 gap-2 pt-3 border-t border-border/50 text-center">
			<!-- Distance -->
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Navigation class="h-3.5 w-3.5" />
					<span>Distance</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.pedometer.distanceKm.toFixed(2)}
				</div>
				<div class="text-[10px] text-muted-foreground uppercase font-medium">km</div>
			</div>

			<!-- Calories -->
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Flame class="h-3.5 w-3.5" />
					<span>Calories</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.pedometer.caloriesBurned.toFixed(0)}
				</div>
				<div class="text-[10px] text-muted-foreground uppercase font-medium">kcal</div>
			</div>

			<!-- Detector Cadence -->
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Zap class="h-3.5 w-3.5" />
					<span>Detected</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.pedometer.detectedSteps}
				</div>
				<div class="text-[10px] text-muted-foreground uppercase font-medium">Pulses</div>
			</div>
		</div>
	</Card.Content>
</Card.Root>
