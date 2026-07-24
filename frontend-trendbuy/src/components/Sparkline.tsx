// Minimal single-series trend mark for product cards: daily cheapest price,
// one thin neutral line + an endpoint dot. Deliberately no axes, grid,
// tooltip or color-coded meaning - state (deal/historic low) is already
// carried by the labeled badges next to it; this only answers "how has it
// been moving?" at a glance. Neutral ink keeps it from competing with them.
export function Sparkline({ values, label }: { values: number[]; label?: string }) {
  if (values.length < 2) return null;

  const width = 96;
  const height = 28;
  const pad = 3;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;

  const points = values.map((value, index) => {
    const x = pad + (index * (width - pad * 2)) / (values.length - 1);
    // Flat history renders as a midline instead of dividing by zero.
    const y = range === 0 ? height / 2 : pad + ((max - value) * (height - pad * 2)) / range;
    return [x, y] as const;
  });

  const last = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={label ?? "Evolución del precio"}
      className="shrink-0 text-zinc-400 dark:text-zinc-500"
    >
      <polyline
        points={points.map(([x, y]) => `${x},${y}`).join(" ")}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill="currentColor" />
    </svg>
  );
}
