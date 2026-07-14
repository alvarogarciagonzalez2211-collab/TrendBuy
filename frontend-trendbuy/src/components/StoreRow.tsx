import type { StoreOffer } from "@/lib/types";
import { StoreBadge } from "./StoreBadge";

export function StoreRow({ offer, isCheapest }: { offer: StoreOffer; isCheapest: boolean }) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 ${
        isCheapest
          ? "border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30"
          : "border-zinc-200 dark:border-zinc-800"
      }`}
    >
      <StoreBadge store={offer.store} />
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{offer.price} €</span>
        <a
          href={offer.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(event) => event.stopPropagation()}
          className="rounded-md bg-zinc-900 px-3 py-1 text-xs font-medium text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Comprar
        </a>
      </div>
    </div>
  );
}
