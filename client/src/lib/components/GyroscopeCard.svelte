<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import Sparkline from "./Sparkline.svelte";
	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import { Compass, RotateCw, RotateCcw } from "lucide-svelte";

	let isSpinning = $derived(sensorManager.gyroscope.rate > 0.8);
	let degPerSec = $derived(Math.round(sensorManager.gyroscope.rate * (180 / Math.PI)));
</script>

<Card.Root class="relative overflow-hidden border-border/70 bg-card/90 shadow-md backdrop-blur-xl transition-all hover:border-emerald-500/40 rounded-2xl">
	<!-- Ambient glow -->
	<div class="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-emerald-500/10 blur-2xl"></div>

	<Card.Header class="pb-2">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30 shadow-sm">
					<Compass class="h-6 w-6" />
				</div>
				<div>
					<Card.Title class="text-lg sm:text-xl font-bold tracking-tight">Gyroscope</Card.Title>
					<Card.Description class="text-xs text-muted-foreground">Angular Rate</Card.Description>
				</div>
			</div>

			<div class="text-xs font-semibold {isSpinning ? 'text-emerald-400' : 'text-muted-foreground'}">
				{isSpinning ? "Active Spin" : "Stationary"}
			</div>
		</div>
	</Card.Header>

	<Card.Content class="space-y-5 pt-2">
		<!-- Giant Angular Speed Readout -->
		<div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
			<div>
				<div class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
					Angular Velocity Speed
				</div>
				<div class="flex items-baseline gap-2">
					<span class="text-5xl sm:text-6xl font-black tracking-tight text-foreground leading-none">
						{sensorManager.gyroscope.rate.toFixed(2)}
					</span>
					<span class="text-base font-semibold text-muted-foreground">rad/s</span>
					<span class="text-xs font-bold text-emerald-400 ml-1">({degPerSec}°/s)</span>
				</div>
			</div>
			<div class="flex justify-end sm:justify-start">
				<Sparkline
					data={sensorManager.gyroHistory}
					strokeColor="#10b981"
					fillColor="rgba(16, 185, 129, 0.15)"
					height={46}
					width={140}
				/>
			</div>
		</div>

		<!-- 3-Axis Rotation with Lucide Icons (No Nested Tiles) -->
		<div class="grid grid-cols-3 gap-2 pt-3 border-t border-border/50 text-center">
			<!-- Pitch X -->
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<RotateCw class="h-3.5 w-3.5" />
					<span>Pitch (X)</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.gyroscope.x > 0 ? "+" : ""}{sensorManager.gyroscope.x.toFixed(2)}
				</div>
				<div class="text-[10px] text-muted-foreground uppercase font-medium">rad/s</div>
			</div>

			<!-- Roll Y -->
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<RotateCcw class="h-3.5 w-3.5" />
					<span>Roll (Y)</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.gyroscope.y > 0 ? "+" : ""}{sensorManager.gyroscope.y.toFixed(2)}
				</div>
				<div class="text-[10px] text-muted-foreground uppercase font-medium">rad/s</div>
			</div>

			<!-- Yaw Z -->
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Compass class="h-3.5 w-3.5" />
					<span>Yaw (Z)</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.gyroscope.z > 0 ? "+" : ""}{sensorManager.gyroscope.z.toFixed(2)}
				</div>
				<div class="text-[10px] text-muted-foreground uppercase font-medium">rad/s</div>
			</div>
		</div>
	</Card.Content>
</Card.Root>
