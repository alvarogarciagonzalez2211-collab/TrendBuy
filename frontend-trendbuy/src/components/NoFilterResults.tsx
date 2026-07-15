import { DEFAULT_FILTERS, type Filters } from "@/lib/filters";

export function NoFilterResults({ onChange }: { onChange: (next: Filters) => void }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-xl border border-dashed border-zinc-300 p-6 text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
      <p>Ningún resultado cumple los filtros seleccionados.</p>
      <button
        type="button"
        onClick={() => onChange(DEFAULT_FILTERS)}
        className="rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
      >
        Limpiar filtros
      </button>
    </div>
  );
}
