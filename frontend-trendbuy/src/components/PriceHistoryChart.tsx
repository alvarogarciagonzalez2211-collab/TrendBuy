import type { ForecastPoint, PriceHistoryPoint } from "@/lib/types";

type Point = { x: number; y: number };

const WIDTH = 480;
const HEIGHT = 180;
const PADDING = { top: 16, right: 16, bottom: 24, left: 48 };

function dayKey(iso: string | null): string | null {
  if (!iso) return null;
  return iso.slice(0, 10);
}

// Collapses multi-store history into one "cheapest price seen that day" series -
// several stores can report the same day, and the chart reads as a single
// coherent price line rather than a jumble of overlapping per-store points.
function toDailyMinSeries(history: PriceHistoryPoint[]): { date: string; price: number }[] {
  const byDay = new Map<string, number>();

  for (const point of history) {
    const key = dayKey(point.date);
    const price = point.price !== null ? Number(point.price) : null;
    if (key === null || price === null || Number.isNaN(price)) continue;

    const existing = byDay.get(key);
    if (existing === undefined || price < existing) {
      byDay.set(key, price);
    }
  }

  return Array.from(byDay.entries())
    .map(([date, price]) => ({ date, price }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function formatShortDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-");
  return `${day}/${month}/${year.slice(2)}`;
}

export function PriceHistoryChart({
  history,
  historicMin,
  forecast,
}: {
  history: PriceHistoryPoint[];
  historicMin: string | null;
  forecast: ForecastPoint[];
}) {
  const series = toDailyMinSeries(history);

  if (series.length < 2) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Todavía no hay suficiente histórico de precios para dibujar un gráfico.
      </p>
    );
  }

  const forecastSeries = forecast
    .map((point) => ({ date: point.ds, price: point.yhat !== null ? Number(point.yhat) : null }))
    .filter((point): point is { date: string; price: number } => point.price !== null && !Number.isNaN(point.price));

  const historicMinValue = historicMin !== null ? Number(historicMin) : null;

  const allPrices = [
    ...series.map((point) => point.price),
    ...forecastSeries.map((point) => point.price),
    ...(historicMinValue !== null ? [historicMinValue] : []),
  ];
  const allDates = [...series.map((point) => point.date), ...forecastSeries.map((point) => point.date)];

  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  // A flat series (all-same price) would divide by zero below; fake a small
  // band so the line renders centered instead of NaN-ing out.
  const priceRange = maxPrice - minPrice || maxPrice * 0.1 || 1;

  const minDate = allDates[0];
  const maxDate = allDates[allDates.length - 1];
  const minTime = new Date(minDate).getTime();
  const maxTime = new Date(maxDate).getTime();
  const timeRange = maxTime - minTime || 1;

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;

  function toXY(date: string, price: number): Point {
    const time = new Date(date).getTime();
    const x = PADDING.left + ((time - minTime) / timeRange) * plotWidth;
    const y = PADDING.top + (1 - (price - minPrice) / priceRange) * plotHeight;
    return { x, y };
  }

  const linePoints = series.map((point) => toXY(point.date, point.price));
  const linePath = linePoints.map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`).join(" ");

  const forecastPoints = forecastSeries.map((point) => toXY(point.date, point.price));
  const forecastPath =
    forecastPoints.length > 0
      ? [linePoints[linePoints.length - 1], ...forecastPoints]
          .map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`)
          .join(" ")
      : null;

  const historicMinY =
    historicMinValue !== null
      ? PADDING.top + (1 - (historicMinValue - minPrice) / priceRange) * plotHeight
      : null;

  const lastPoint = linePoints[linePoints.length - 1];

  return (
    <div className="flex flex-col gap-1">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full"
        role="img"
        aria-label="Histórico de precios"
      >
        <text x={PADDING.left} y={12} className="fill-zinc-400 text-[10px] dark:fill-zinc-500">
          {maxPrice.toFixed(0)} €
        </text>
        <text x={PADDING.left} y={HEIGHT - PADDING.bottom + 12} className="fill-zinc-400 text-[10px] dark:fill-zinc-500">
          {minPrice.toFixed(0)} €
        </text>

        {historicMinY !== null && (
          <>
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={historicMinY}
              y2={historicMinY}
              className="stroke-amber-500/70 dark:stroke-amber-400/70"
              strokeWidth={1}
              strokeDasharray="4 3"
            />
            <text
              x={WIDTH - PADDING.right}
              y={historicMinY - 4}
              textAnchor="end"
              className="fill-amber-600 text-[10px] font-medium dark:fill-amber-400"
            >
              mínimo histórico
            </text>
          </>
        )}

        {forecastPath && (
          <path
            d={forecastPath}
            fill="none"
            className="stroke-sky-400/70 dark:stroke-sky-500/70"
            strokeWidth={2}
            strokeDasharray="5 4"
          />
        )}

        <path d={linePath} fill="none" className="stroke-emerald-600 dark:stroke-emerald-400" strokeWidth={2} />

        {lastPoint && <circle cx={lastPoint.x} cy={lastPoint.y} r={3.5} className="fill-emerald-600 dark:fill-emerald-400" />}
      </svg>

      <div className="flex items-center justify-between text-[11px] text-zinc-400 dark:text-zinc-500">
        <span>{formatShortDate(minDate)}</span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="h-0.5 w-3 bg-emerald-600 dark:bg-emerald-400" /> histórico
          </span>
          {forecastPath && (
            <span className="flex items-center gap-1">
              <span className="h-0.5 w-3 bg-sky-400" /> previsión 30 días
            </span>
          )}
        </div>
        <span>{formatShortDate(forecastSeries.length > 0 ? forecastSeries[forecastSeries.length - 1].date : maxDate)}</span>
      </div>
    </div>
  );
}
