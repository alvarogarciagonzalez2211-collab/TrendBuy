// Plain <img>, not next/image: photos are hotlinked straight from each
// store's own CDN (Amazon, PcComponentes, MediaMarkt, Worten all use
// different, unpredictable subdomains), so next/image's remotePatterns
// allowlist would need constant upkeep for little benefit here.
export function ProductImage({ src, alt }: { src: string | null; alt: string }) {
  if (!src) {
    return (
      <div className="flex aspect-square w-full items-center justify-center rounded-lg bg-zinc-100 text-zinc-300 dark:bg-zinc-800 dark:text-zinc-600">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-10 w-10">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="9" cy="9" r="2" />
          <path d="m21 15-5-5L5 21" />
        </svg>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      className="aspect-square w-full rounded-lg object-contain bg-white dark:bg-zinc-950"
    />
  );
}
