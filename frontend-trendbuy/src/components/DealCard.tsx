"use client";

import type { DashboardProduct } from "@/lib/types";
import { useProductAnalysis } from "@/lib/useProductAnalysis";
import { DiscountBadge } from "./DiscountBadge";
import { FavoriteButton } from "./FavoriteButton";
import { HistoricLowBadge } from "./HistoricLowBadge";
import { ProductAnalysisPanel } from "./ProductAnalysisPanel";
import { ProductImage } from "./ProductImage";
import { StatusBadge } from "./StatusBadge";

export function DealCard({ product }: { product: DashboardProduct }) {
  const { expanded, status, analysis, toggle } = useProductAnalysis(product.product_id);

  return (
    <article className="relative flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
      {/* Sibling to the toggle button below, not nested inside it - a
          <button> can't validly contain another <button>. */}
      <div className="absolute right-6 top-6 z-10">
        <FavoriteButton productId={product.product_id} />
      </div>

      <button type="button" onClick={toggle} aria-expanded={expanded} className="flex flex-col gap-2 text-left">
        <div className="relative">
          {product.is_historic_low && <HistoricLowBadge />}
          <ProductImage src={product.image_url} alt={product.name} />
        </div>

        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{product.name}</h3>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <StatusBadge status={product.status} />
            <DiscountBadge percent={product.discount_percent} />
          </div>
        </div>

        {product.cheapest_price && (
          <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
            {product.cheapest_price} €
            <span className="ml-2 text-xs font-normal text-zinc-500 dark:text-zinc-400">
              en {product.cheapest_store}
            </span>
          </p>
        )}

        <span className="inline-flex items-center gap-1 text-xs font-medium text-zinc-400 dark:text-zinc-500">
          {expanded ? "▲" : "▼"} Ver histórico de precios
        </span>
      </button>

      {product.cheapest_url && (
        <a
          href={product.cheapest_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(event) => event.stopPropagation()}
          className="self-start rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Ver oferta
        </a>
      )}

      {expanded && (
        <ProductAnalysisPanel
          status={status}
          analysis={analysis}
          technical={{ productId: product.product_id, ean: product.ean, trackedLinks: product.tracked_links }}
        />
      )}
    </article>
  );
}
