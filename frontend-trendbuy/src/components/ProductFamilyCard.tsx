"use client";

import type { ProductFamily } from "@/lib/types";
import { useProductAnalysis } from "@/lib/useProductAnalysis";
import { DiscountBadge } from "./DiscountBadge";
import { FavoriteButton } from "./FavoriteButton";
import { HistoricLowBadge } from "./HistoricLowBadge";
import { ProductAnalysisPanel } from "./ProductAnalysisPanel";
import { ProductImage } from "./ProductImage";
import { StatusBadge } from "./StatusBadge";
import { StoreRow } from "./StoreRow";

export function ProductFamilyCard({ family }: { family: ProductFamily }) {
  const { expanded, status, analysis, toggle } = useProductAnalysis(family.product_id);

  return (
    <article className="relative flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
      {/* Sibling to the toggle button below, not nested inside it - a
          <button> can't validly contain another <button>. */}
      <div className="absolute right-3 top-3 z-10">
        <FavoriteButton productId={family.product_id} />
      </div>

      <button
        type="button"
        onClick={toggle}
        aria-expanded={expanded}
        className="flex flex-col gap-3 text-left"
      >
        <div className="flex gap-3">
          <div className="relative w-20 shrink-0">
            {family.is_historic_low && <HistoricLowBadge />}
            <ProductImage src={family.image_url} alt={family.name} />
          </div>

          <div className="flex flex-1 flex-col gap-2">
            <div className="flex flex-wrap items-start justify-between gap-2 pr-8">
              <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{family.name}</h3>
              <div className="flex shrink-0 items-center gap-1.5">
                <DiscountBadge percent={family.discount_percent} />
                <StatusBadge status={family.best_status} />
              </div>
            </div>

            {family.categories.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {family.categories.map((category) => (
                  <span
                    key={category}
                    className="rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                  >
                    {category}
                  </span>
                ))}
              </div>
            )}

            <span className="inline-flex items-center gap-1 text-xs font-medium text-zinc-400 dark:text-zinc-500">
              {expanded ? "▲" : "▼"} Ver histórico de precios
            </span>
          </div>
        </div>
      </button>

      <div className="flex flex-col gap-2">
        {family.stores.map((offer, index) => (
          <StoreRow key={`${offer.store}-${offer.url}`} offer={offer} isCheapest={index === 0} />
        ))}
      </div>

      {expanded && (
        <ProductAnalysisPanel
          status={status}
          analysis={analysis}
          technical={{ productId: family.product_id, trackedLinks: family.stores.length }}
        />
      )}
    </article>
  );
}
