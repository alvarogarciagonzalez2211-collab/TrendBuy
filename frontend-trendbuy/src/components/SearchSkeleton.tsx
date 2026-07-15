// Real searches take up to ~40s (4 stores scraped live, see SearchBar) - a
// static "Buscando..." line reads as stalled that long. Pulsing placeholder
// cards give continuous visual feedback that something is still happening.
export function SearchSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          className="flex animate-pulse gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="h-20 w-20 shrink-0 rounded-lg bg-zinc-200 dark:bg-zinc-800" />
          <div className="flex flex-1 flex-col gap-2 py-1">
            <div className="h-3.5 w-2/3 rounded bg-zinc-200 dark:bg-zinc-800" />
            <div className="h-3 w-1/3 rounded bg-zinc-200 dark:bg-zinc-800" />
            <div className="mt-2 h-8 w-full rounded-lg bg-zinc-100 dark:bg-zinc-800/60" />
          </div>
        </div>
      ))}
    </div>
  );
}
