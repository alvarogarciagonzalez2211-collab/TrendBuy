import { useState } from "react";
import type { ProductAnalysis } from "@/lib/types";
import { PriceHistoryChart } from "./PriceHistoryChart";

// Extra raw fields only a technically-minded shopper cares about (EAN, how
// many stores/links feed this product's history, its internal id) - kept
// behind an opt-in toggle so the default view stays approachable.
export type TechnicalDetails = {
  productId: number;
  ean?: string | null;
  trackedLinks?: number;
};

export function ProductAnalysisPanel({
  status,
  analysis,
  technical,
}: {
  status: "idle" | "loading" | "error";
  analysis: ProductAnalysis | null;
  technical?: TechnicalDetails;
}) {
  const [showTechnical, setShowTechnical] = useState(false);

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

      {technical && (
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setShowTechnical((value) => !value);
            }}
            className="self-start text-xs font-medium text-zinc-400 underline-offset-2 hover:underline dark:text-zinc-500"
          >
            {showTechnical ? "Ocultar" : "Ver"} detalles técnicos
          </button>

          {showTechnical && (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-lg bg-zinc-50 p-3 font-mono text-[11px] text-zinc-500 sm:grid-cols-3 dark:bg-zinc-800/60 dark:text-zinc-400">
              <div>
                <dt className="text-zinc-400 dark:text-zinc-500">product_id</dt>
                <dd className="text-zinc-700 dark:text-zinc-300">{technical.productId}</dd>
              </div>
              <div>
                <dt className="text-zinc-400 dark:text-zinc-500">EAN</dt>
                <dd className="text-zinc-700 dark:text-zinc-300">{technical.ean ?? "—"}</dd>
              </div>
              {technical.trackedLinks !== undefined && (
                <div>
                  <dt className="text-zinc-400 dark:text-zinc-500">enlaces rastreados</dt>
                  <dd className="text-zinc-700 dark:text-zinc-300">{technical.trackedLinks}</dd>
                </div>
              )}
              <div>
                <dt className="text-zinc-400 dark:text-zinc-500">precio actual</dt>
                <dd className="text-zinc-700 dark:text-zinc-300">
                  {bestMoment.current_price ? `${bestMoment.current_price} €` : "—"}
                </dd>
              </div>
            </dl>
          )}
        </div>
      )}
    </div>
  );
}
