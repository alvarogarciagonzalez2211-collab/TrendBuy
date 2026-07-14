import { getDashboard } from "@/lib/api";
import { SearchBar } from "@/components/SearchBar";
import { DealsGrid } from "@/components/DealsGrid";
import type { DashboardProduct } from "@/lib/types";

// Without this, Next.js prerenders "/" as a static page at `next build` time
// (no backend running yet, or a stale DB) and freezes that HTML for every
// request afterwards - the deals grid must reflect live DB state on every hit.
export const dynamic = "force-dynamic";

export default async function Home() {
  let products: DashboardProduct[] = [];
  let dashboardError = false;

  try {
    const dashboard = await getDashboard();
    products = dashboard.products;
  } catch {
    dashboardError = true;
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">TrendBuy</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Compara precios entre tiendas y descubre el mejor momento para comprar.
        </p>
      </header>

      <SearchBar />

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Mejores ofertas actuales</h2>
        {dashboardError ? (
          <p className="text-sm text-red-600 dark:text-red-400">
            No se pudo cargar el listado de ofertas. Comprueba que el backend esté disponible.
          </p>
        ) : (
          <DealsGrid products={products} />
        )}
      </section>
    </div>
  );
}
