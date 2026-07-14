// Approximate real brand colors per store, matched by substring so backend
// naming variants ("Amazon Espana", "Amazon.es"...) still resolve correctly.
const STORE_STYLES: { match: string; className: string }[] = [
  { match: "amazon", className: "bg-[#FF9900]/15 text-[#B96E00] dark:text-[#FFA733]" },
  { match: "pccomponentes", className: "bg-[#E30613]/10 text-[#E30613] dark:bg-[#E30613]/20" },
  { match: "mediamarkt", className: "bg-[#DF0000]/10 text-[#DF0000] dark:bg-[#DF0000]/20" },
  { match: "worten", className: "bg-[#E4032E]/10 text-[#E4032E] dark:bg-[#E4032E]/20" },
];

const DEFAULT_STYLE = "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";

function styleFor(store: string): string {
  const lowered = store.toLowerCase();
  return STORE_STYLES.find((entry) => lowered.includes(entry.match))?.className ?? DEFAULT_STYLE;
}

export function StoreBadge({ store }: { store: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${styleFor(store)}`}
    >
      {store}
    </span>
  );
}
