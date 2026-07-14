const STATUS_STYLES: Record<string, string> = {
  "Óptimo": "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  "Buena Compra": "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  Esperar: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  "Sin datos": "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
};

const DEFAULT_STYLE = "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? DEFAULT_STYLE}`}
    >
      {status}
    </span>
  );
}
