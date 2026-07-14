import type { DashboardProduct } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

export function DealCard({ product }: { product: DashboardProduct }) {
  return (
    <article className="flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{product.name}</h3>
        <StatusBadge status={product.status} />
      </div>

      {product.cheapest_price && (
        <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
          {product.cheapest_price} €
          <span className="ml-2 text-xs font-normal text-zinc-500 dark:text-zinc-400">
            en {product.cheapest_store}
          </span>
        </p>
      )}

      {product.cheapest_url && (
        <a
          href={product.cheapest_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-auto self-start rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Ver oferta
        </a>
      )}
    </article>
  );
}
