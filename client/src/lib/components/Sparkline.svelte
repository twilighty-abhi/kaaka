<script lang="ts">
	interface Props {
		data: number[];
		strokeColor?: string;
		fillColor?: string;
		height?: number;
		width?: number;
		minVal?: number;
		maxVal?: number;
	}

	let {
		data = [],
		strokeColor = "#10b981",
		fillColor = "rgba(16, 185, 129, 0.12)",
		height = 42,
		width = 130,
		minVal,
		maxVal
	}: Props = $props();

	let points = $derived.by(() => {
		if (data.length < 2) return "";
		const effectiveMin = minVal !== undefined ? minVal : Math.min(...data);
		const effectiveMax = maxVal !== undefined ? maxVal : Math.max(...data);
		const range = effectiveMax - effectiveMin || 1;
		const w = width;
		const h = height;

		return data
			.map((val, idx) => {
				const x = (idx / (data.length - 1)) * w;
				const normalized = (val - effectiveMin) / range;
				const y = h - normalized * (h - 8) - 4;
				return `${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(" ");
	});

	let areaPoints = $derived.by(() => {
		if (!points || data.length < 2) return "";
		return `0,${height} ${points} ${width},${height}`;
	});
</script>

<div class="inline-flex items-center">
	<svg class="overflow-visible" width={width} height={height} viewBox="0 0 {width} {height}">
		{#if areaPoints}
			<polygon
				fill={fillColor}
				points={areaPoints}
			/>
		{/if}
		{#if points}
			<polyline
				fill="none"
				stroke={strokeColor}
				stroke-width="2.5"
				stroke-linecap="round"
				stroke-linejoin="round"
				points={points}
			/>
		{/if}
	</svg>
</div>
