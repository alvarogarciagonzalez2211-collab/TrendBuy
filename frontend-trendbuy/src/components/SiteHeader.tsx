import Link from "next/link";
import { AuthHeader } from "./AuthHeader";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-black/80">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-1.5 text-lg font-bold text-zinc-900 dark:text-zinc-50">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-emerald-500 text-xs text-white">
            ↓
          </span>
          TrendBuy
        </Link>
        <AuthHeader />
      </div>
    </header>
  );
}
