<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import Sparkline from "./Sparkline.svelte";
	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import { Activity, Sliders, Zap } from "lucide-svelte";

	let isHighG = $derived(sensorManager.accelerometer.magnitude > 15);
	let gForce = $derived((sensorManager.accelerometer.magnitude / 9.80665).toFixed(2));
</script>

<Card.Root class="relative overflow-hidden border-border/70 bg-card/90 shadow-md transition-all hover:border-emerald-500/40 rounded-2xl">
	<!-- Ambient glow -->
	<div class="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-emerald-500/10 blur-2xl"></div>

	<Card.Header class="pb-2">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30 shadow-sm">
					<Activity class="h-6 w-6" />
				</div>
				<div>
					<Card.Title class="text-lg sm:text-xl font-bold tracking-tight">Accelerometer</Card.Title>
					<Card.Description class="text-xs text-muted-foreground">Linear Motion</Card.Description>
				</div>
			</div>

			<div class="text-xs font-semibold text-emerald-400">
				{isHighG ? "High Impact" : `${gForce} G`}
			</div>
		</div>
	</Card.Header>

	<Card.Content class="space-y-5 pt-2">
		<!-- Giant Vector Magnitude Readout -->
		<div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
			<div>
				<div class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
					Net Acceleration Force
				</div>
				<div class="flex items-baseline gap-2">
					<span class="text-5xl sm:text-6xl font-black tracking-tight text-foreground leading-none">
						{sensorManager.accelerometer.magnitude.toFixed(2)}
					</span>
					<span class="text-base font-semibold text-muted-foreground">m/s²</span>
				</div>
			</div>
			<div class="flex justify-end sm:justify-start">
				<Sparkline
					data={sensorManager.accelHistory}
					strokeColor="#10b981"
					fillColor="rgba(16, 185, 129, 0.15)"
					height={46}
					width={140}
				/>
			</div>
		</div>

		<!-- 3-Axis Balance Meters with Lucide Icons (No Nested Tiles) -->
		<div class="space-y-3 pt-3 border-t border-border/50">
			<!-- X Axis -->
			<div class="space-y-1.5">
				<div class="flex justify-between items-center text-xs">
					<div class="flex items-center gap-1.5 font-semibold text-emerald-400">
						<Activity class="h-3.5 w-3.5 text-emerald-400" />
						<span>X Axis</span>
					</div>
					<span class="font-bold text-foreground text-sm">
						{sensorManager.accelerometer.x > 0 ? "+" : ""}{sensorManager.accelerometer.x.toFixed(2)}
						<span class="text-[10px] text-muted-foreground font-normal">m/s²</span>
					</span>
				</div>
				<div class="relative h-2 w-full bg-secondary/80 rounded-full overflow-hidden flex items-center">
					<div class="absolute left-1/2 h-full w-0.5 bg-border z-10"></div>
					<div
						class="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full"
						style:width={`${Math.min(100, Math.abs(sensorManager.accelerometer.x) * 8)}%`}
					></div>
				</div>
			</div>

			<!-- Y Axis -->
			<div class="space-y-1.5">
				<div class="flex justify-between items-center text-xs">
					<div class="flex items-center gap-1.5 font-semibold text-emerald-400">
						<Sliders class="h-3.5 w-3.5 text-emerald-400" />
						<span>Y Axis</span>
					</div>
					<span class="font-bold text-foreground text-sm">
						{sensorManager.accelerometer.y > 0 ? "+" : ""}{sensorManager.accelerometer.y.toFixed(2)}
						<span class="text-[10px] text-muted-foreground font-normal">m/s²</span>
					</span>
				</div>
				<div class="relative h-2 w-full bg-secondary/80 rounded-full overflow-hidden flex items-center">
					<div class="absolute left-1/2 h-full w-0.5 bg-border z-10"></div>
					<div
						class="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full"
						style:width={`${Math.min(100, Math.abs(sensorManager.accelerometer.y) * 8)}%`}
					></div>
				</div>
			</div>

			<!-- Z Axis -->
			<div class="space-y-1.5">
				<div class="flex justify-between items-center text-xs">
					<div class="flex items-center gap-1.5 font-semibold text-emerald-400">
						<Zap class="h-3.5 w-3.5 text-emerald-400" />
						<span>Z Axis</span>
					</div>
					<span class="font-bold text-foreground text-sm">
						{sensorManager.accelerometer.z > 0 ? "+" : ""}{sensorManager.accelerometer.z.toFixed(2)}
						<span class="text-[10px] text-muted-foreground font-normal">m/s²</span>
					</span>
				</div>
				<div class="relative h-2 w-full bg-secondary/80 rounded-full overflow-hidden flex items-center">
					<div class="absolute left-1/2 h-full w-0.5 bg-border z-10"></div>
					<div
						class="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full"
						style:width={`${Math.min(100, Math.abs(sensorManager.accelerometer.z) * 8)}%`}
					></div>
				</div>
			</div>
		</div>
	</Card.Content>
</Card.Root>
