<script lang="ts">
	import * as Card from "#lib/components/ui/card/index.js";
	import { Progress } from "#lib/components/ui/progress/index.js";
	import Sparkline from "./Sparkline.svelte";
	import { sensorManager } from "#lib/services/sensorManager.svelte.js";
	import { SunMedium, Moon, Building2, Sun } from "lucide-svelte";

	let luxProgress = $derived(
		Math.min(100, Math.round((Math.log10(Math.max(1, sensorManager.ambientLight.lux)) / 4) * 100))
	);
</script>

<Card.Root class="relative overflow-hidden border-border/70 bg-card/90 shadow-md transition-all hover:border-emerald-500/40 rounded-2xl">
	<!-- Ambient glow -->
	<div class="pointer-events-none absolute -right-12 -top-12 h-36 w-36 rounded-full bg-emerald-500/10 blur-2xl"></div>

	<Card.Header class="pb-2">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30 shadow-sm">
					<SunMedium class="h-6 w-6" />
				</div>
				<div>
					<Card.Title class="text-lg sm:text-xl font-bold tracking-tight">Ambient Light</Card.Title>
					<Card.Description class="text-xs text-muted-foreground">Illuminance</Card.Description>
				</div>
			</div>

			<div class="text-xs font-semibold text-emerald-400">
				{sensorManager.ambientLight.environment}
			</div>
		</div>
	</Card.Header>

	<Card.Content class="space-y-5 pt-2">
		<!-- Giant Lux Readout -->
		<div class="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
			<div>
				<div class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
					Illuminance Flux
				</div>
				<div class="flex items-baseline gap-2">
					<span class="text-5xl sm:text-6xl font-black tracking-tight text-foreground leading-none">
						{Math.round(sensorManager.ambientLight.lux).toLocaleString()}
					</span>
					<span class="text-base font-semibold text-muted-foreground">lux</span>
				</div>
			</div>
			<div class="flex justify-end sm:justify-start">
				<Sparkline
					data={sensorManager.lightHistory}
					strokeColor="#10b981"
					fillColor="rgba(16, 185, 129, 0.15)"
					height={46}
					width={140}
				/>
			</div>
		</div>

		<!-- Light Intensity Meter -->
		<div class="space-y-2 pt-1">
			<div class="flex justify-between items-center text-xs">
				<span class="text-muted-foreground font-medium">Brightness Spectrum</span>
				<span class="font-bold text-emerald-400 text-sm">{luxProgress}%</span>
			</div>
			<Progress value={luxProgress} class="h-2.5 bg-secondary/80" />
		</div>

		<!-- 3 Zone Indicators with Lucide Icons (No Nested Tiles) -->
		<div class="grid grid-cols-3 gap-2 pt-3 border-t border-border/50 text-center">
			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Moon class="h-3.5 w-3.5" />
					<span>Night</span>
				</div>
				<div class="text-sm font-bold text-foreground">&lt;50 lx</div>
				<div class="text-[10px] font-medium {sensorManager.ambientLight.lux < 50 ? 'text-emerald-400 font-bold' : 'text-muted-foreground'} mt-0.5">
					{sensorManager.ambientLight.lux < 50 ? "Active" : "Inactive"}
				</div>
			</div>

			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Building2 class="h-3.5 w-3.5" />
					<span>Indoor</span>
				</div>
				<div class="text-sm font-bold text-foreground">50-1000 lx</div>
				<div class="text-[10px] font-medium {sensorManager.ambientLight.lux >= 50 && sensorManager.ambientLight.lux <= 1000 ? 'text-emerald-400 font-bold' : 'text-muted-foreground'} mt-0.5">
					{sensorManager.ambientLight.lux >= 50 && sensorManager.ambientLight.lux <= 1000 ? "Active" : "Inactive"}
				</div>
			</div>

			<div class="flex flex-col items-center">
				<div class="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mb-0.5">
					<Sun class="h-3.5 w-3.5" />
					<span>Sunlight</span>
				</div>
				<div class="text-sm font-bold text-foreground">&gt;1000 lx</div>
				<div class="text-[10px] font-medium {sensorManager.ambientLight.lux > 1000 ? 'text-emerald-400 font-bold' : 'text-muted-foreground'} mt-0.5">
					{sensorManager.ambientLight.lux > 1000 ? "Active" : "Inactive"}
				</div>
			</div>
		</div>
	</Card.Content>
</Card.Root>
