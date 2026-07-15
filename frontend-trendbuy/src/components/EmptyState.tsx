import Image from "next/image";

// Shared "nothing to show yet" block for the dashboard and search results.
// The illustration is decorative only (the message carries the meaning), and
// hidden in dark mode - its dark outline was generated for a light card and
// nearly disappears against the near-black dark background (see
// nano-banana-brand-assets.md for the source prompt).
export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-zinc-200 py-10 text-center dark:border-zinc-800">
      <Image
        src="/empty-state.png"
        alt=""
        width={512}
        height={512}
        className="h-24 w-24 opacity-90 dark:hidden"
      />
      <p className="max-w-sm text-sm text-zinc-500 dark:text-zinc-400">{message}</p>
    </div>
  );
}
