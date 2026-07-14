// A plain pill (used previously) reads as "just another label" next to the
// status badge - the user asked for historic lows to stand out more, so this
// renders as a corner ribbon over the product image with stronger color and a
// subtle pulse instead of competing for attention with everything else.
export function HistoricLowBadge() {
  return (
    <span className="absolute left-2 top-2 z-10 inline-flex animate-pulse items-center gap-1 rounded-full bg-amber-500 px-2.5 py-1 text-xs font-bold text-white shadow-md shadow-amber-500/30">
      ↓ Mínimo histórico
    </span>
  );
}
