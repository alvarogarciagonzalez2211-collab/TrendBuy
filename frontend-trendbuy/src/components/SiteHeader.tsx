import { HeaderNav } from "./HeaderNav";
import { Logo } from "./Logo";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-black/80">
      <div className="relative mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-3">
        <Logo withTagline />
        <HeaderNav />
      </div>
      {/* Thin accent strip echoing the four status/badge colors used
          throughout the app (Optimo, Buena Compra, minimo historico,
          descuento) - a small consistent brand touch under the header. */}
      <div className="h-0.5 w-full bg-linear-to-r from-emerald-500 via-sky-500 via-40% to-amber-500" />
    </header>
  );
}
