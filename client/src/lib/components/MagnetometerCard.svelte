<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import Sparkline from "./Sparkline.svelte";
	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import { Magnet, Compass, Navigation, Activity } from "lucide-svelte";

	let isAnomaly = $derived(
		sensorManager.magnetometer.fieldStrength > 90 || sensorManager.magnetometer.fieldStrength < 15
	);
</script>

<Card.Root class="relative overflow-hidden border-border/70 bg-card/90 shadow-md backdrop-blur-xl transition-all hover:border-emerald-500/40 rounded-2xl">
	<!-- Ambient glow -->
	<div class="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-emerald-500/10 blur-2xl"></div>

	<Card.Header class="pb-2">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30 shadow-sm">
					<Magnet class="h-6 w-6" />
				</div>
				<div>
					<Card.Title class="text-lg sm:text-xl font-bold tracking-tight">Magnetometer</Card.Title>
					<Card.Description class="text-xs text-muted-foreground">Geomagnetic Heading</Card.Description>
				</div>
			</div>

			<div class="text-xs font-semibold text-emerald-400">
				{isAnomaly ? "Anomaly" : `${sensorManager.magnetometer.fieldStrength.toFixed(0)} µT`}
			</div>
		</div>
	</Card.Header>

	<Card.Content class="space-y-5 pt-2">
		<!-- Giant Heading & Rotating Compass Dial -->
		<div class="flex items-center justify-between gap-3">
			<div>
				<div class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
					Compass Heading
				</div>
				<div class="flex items-baseline gap-2">
					<span class="text-5xl sm:text-6xl font-black tracking-tight text-foreground leading-none">
						{Math.round(sensorManager.magnetometer.heading)}°
					</span>
					<span class="text-lg font-black text-emerald-300">
						{sensorManager.magnetometer.cardinal}
					</span>
				</div>
				<div class="text-xs text-muted-foreground mt-2">
					Field Flux: <span class="font-semibold text-foreground">{sensorManager.magnetometer.fieldStrength.toFixed(1)} µT</span>
				</div>
			</div>

			<!-- Dynamic Compass Rose Dial in Emerald Greens -->
			<div class="relative flex h-20 w-20 sm:h-22 sm:w-22 shrink-0 items-center justify-center rounded-full border-2 border-border/80 bg-secondary/70 shadow-inner">
				<!-- Cardinal tick labels -->
				<span class="absolute top-1 text-[9px] font-black text-emerald-400">N</span>
				<span class="absolute right-1 text-[9px] font-bold text-muted-foreground">E</span>
				<span class="absolute bottom-1 text-[9px] font-bold text-muted-foreground">S</span>
				<span class="absolute left-1 text-[9px] font-bold text-muted-foreground">W</span>

				<!-- Rotating Needle -->
				<div
					class="transition-transform duration-100 ease-out flex items-center justify-center h-full w-full"
					style:transform={`rotate(${sensorManager.magnetometer.heading}deg)`}
				>
					<div class="h-12 w-1.5 flex flex-col items-center">
						<div class="h-6 w-1.5 bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-full shadow-sm"></div>
						<div class="h-6 w-1.5 bg-muted-foreground/30 rounded-b-full"></div>
					</div>
					<!-- Center Pivot -->
					<div class="absolute h-3 w-3 rounded-full bg-emerald-400 border-2 border-background shadow"></div>
				</div>
			</div>
		</div>

		<!-- Trend Sparkline -->
		<div class="flex items-center justify-between pt-1">
			<span class="text-xs text-muted-foreground font-medium">Flux Stability</span>
			<Sparkline
				data={sensorManager.magHistory}
				strokeColor="#10b981"
				fillColor="rgba(16, 185, 129, 0.15)"
				height={36}
				width={140}
			/>
		</div>

		<!-- 3-Axis Field Components with Lucide Icons (No Nested Tiles) -->
		<div class="grid grid-cols-3 gap-2 pt-3 border-t border-border/50 text-center">
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Compass class="h-3.5 w-3.5" />
					<span>X (North)</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.magnetometer.x.toFixed(1)}
				</div>
				<div class="text-[10px] text-muted-foreground font-medium">µT</div>
			</div>

			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Navigation class="h-3.5 w-3.5" />
					<span>Y (East)</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.magnetometer.y.toFixed(1)}
				</div>
				<div class="text-[10px] text-muted-foreground font-medium">µT</div>
			</div>

			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Activity class="h-3.5 w-3.5" />
					<span>Z (Down)</span>
				</div>
				<div class="text-base sm:text-lg font-bold text-foreground">
					{sensorManager.magnetometer.z.toFixed(1)}
				</div>
				<div class="text-[10px] text-muted-foreground font-medium">µT</div>
			</div>
		</div>
	</Card.Content>
</Card.Root>
