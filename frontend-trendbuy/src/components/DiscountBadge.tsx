// Rendered whenever a product's discount vs. its previous recorded price is
// > 0 - lets a casual reader scan the grid by "how big is the drop" without
// opening each card, same idea as StatusBadge/HistoricLowBadge.
export function DiscountBadge({ percent }: { percent: string }) {
  const value = Number(percent);
  if (!Number.isFinite(value) || value <= 0) return null;

  return (
    <span className="inline-flex items-center rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-bold text-rose-700 dark:bg-rose-900/40 dark:text-rose-300">
      -{value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)}%
    </span>
  );
}
