import type { ProductFamily } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { StoreRow } from "./StoreRow";

export function ProductFamilyCard({ family }: { family: ProductFamily }) {
  const hasDiscount = Number(family.discount_percent) > 0;

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{family.name}</h3>
        <div className="flex flex-wrap items-center gap-2">
          {family.is_historic_low && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
              ↓ Mínimo histórico
            </span>
          )}
          <StatusBadge status={family.best_status} />
        </div>
      </div>

      {hasDiscount && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Bajada del {family.discount_percent}% respecto al precio anterior
        </p>
      )}

      <div className="flex flex-col gap-2">
        {family.stores.map((offer, index) => (
          <StoreRow key={`${offer.store}-${offer.url}`} offer={offer} isCheapest={index === 0} />
        ))}
      </div>
    </article>
  );
}
