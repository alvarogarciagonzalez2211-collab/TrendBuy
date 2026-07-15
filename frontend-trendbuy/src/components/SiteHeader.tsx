import Link from "next/link";
import { AuthHeader } from "./AuthHeader";

export function SiteHeader() {
  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
          TrendBuy
        </Link>
        <AuthHeader />
      </div>
    </header>
  );
}
