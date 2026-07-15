// Honest counterpart to HistoricLowBadge: a just-discovered product can't
// claim a historic low yet (backend gates the badge on >= 2 tracked days),
// and pretending otherwise was exactly the bug where every first search lit
// up "mínimo histórico" everywhere. This quietly says why the badge isn't
// there yet instead of leaving an unexplained gap.
export function TrackingSinceHint({ daysTracked }: { daysTracked: number }) {
  if (daysTracked > 1) return null;

  return (
    <span className="inline-flex w-fit items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 dark:bg-sky-950/40 dark:text-sky-300">
      ✦ Nuevo en seguimiento — histórico en construcción
    </span>
  );
}
