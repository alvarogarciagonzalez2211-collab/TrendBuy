import type { ProductAnalysis } from "@/lib/types";
import { PriceHistoryChart } from "./PriceHistoryChart";

export function ProductAnalysisPanel({
  status,
  analysis,
}: {
  status: "idle" | "loading" | "error";
  analysis: ProductAnalysis | null;
}) {
  if (status === "loading") {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">Cargando histórico de precios…</p>;
  }

  if (status === "error") {
    return <p className="text-sm text-red-600 dark:text-red-400">No se pudo cargar el histórico de precios.</p>;
  }

  if (!analysis) return null;

  const { best_moment: bestMoment } = analysis;

  return (
    <div className="flex flex-col gap-3 border-t border-zinc-200 pt-3 dark:border-zinc-800">
      <PriceHistoryChart
        history={analysis.history}
        historicMin={bestMoment.historic_min}
        forecast={analysis.forecast_30_days}
      />

      <dl className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-800/60">
          <dt className="text-zinc-400 dark:text-zinc-500">Mínimo histórico</dt>
          <dd className="font-semibold text-zinc-900 dark:text-zinc-50">
            {bestMoment.historic_min ? `${bestMoment.historic_min} €` : "—"}
          </dd>
        </div>
        <div className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-800/60">
          <dt className="text-zinc-400 dark:text-zinc-500">Percentil 25</dt>
          <dd className="font-semibold text-zinc-900 dark:text-zinc-50">
            {bestMoment.percentile_25 ? `${bestMoment.percentile_25} €` : "—"}
          </dd>
        </div>
        <div className="rounded-lg bg-zinc-50 p-2 dark:bg-zinc-800/60">
          <dt className="text-zinc-400 dark:text-zinc-500">Registros</dt>
          <dd className="font-semibold text-zinc-900 dark:text-zinc-50">{bestMoment.records ?? "—"}</dd>
        </div>
      </dl>

      {analysis.warnings.length > 0 && (
        <p className="text-xs text-zinc-400 dark:text-zinc-500">{analysis.warnings.join(" ")}</p>
      )}
    </div>
  );
}
