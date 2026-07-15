import Link from "next/link";

// Icon mark: a rounded square with a descending price-trend line, echoing the
// down-arrow used across the app (HistoricLowBadge, DiscountBadge) so the
// logo and the in-product badges read as the same visual language.
export function Logo({ withTagline = false }: { withTagline?: boolean }) {
  return (
    <Link href="/" className="group flex shrink-0 items-center gap-2.5">
      <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-emerald-400 to-emerald-600 shadow-sm shadow-emerald-500/30 transition group-hover:shadow-emerald-500/50">
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-white">
          <path
            d="M4 8L10 14L13.5 10.5L20 17"
            stroke="currentColor"
            strokeWidth={2.25}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M15 17H20V12" stroke="currentColor" strokeWidth={2.25} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="flex flex-col leading-none">
        <span className="text-lg font-bold tracking-tight text-zinc-900 dark:text-zinc-50">TrendBuy</span>
        {withTagline && (
          <span className="mt-0.5 hidden text-[11px] font-medium text-zinc-400 sm:block dark:text-zinc-500">
            Comparador de precios
          </span>
        )}
      </span>
    </Link>
  );
}
