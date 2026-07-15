import { getDashboard } from "@/lib/api";
import { SearchBar } from "@/components/SearchBar";
import { FilterableDeals } from "@/components/FilterableDeals";
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
      <section className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl dark:text-zinc-50">
          Compra en el momento justo
        </h1>
        <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
          Comparamos precios en Amazon, PcComponentes, MediaMarkt y Worten a la vez y te avisamos cuándo un precio
          toca su mínimo histórico real, no una estimación.
        </p>
      </section>

      <SearchBar />

      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Mejores ofertas actuales</h2>
          {!dashboardError && products.length > 0 && (
            <span className="text-xs text-zinc-400 dark:text-zinc-500">{products.length} productos</span>
          )}
        </div>
        {dashboardError ? (
          <p className="text-sm text-red-600 dark:text-red-400">
            No se pudo cargar el listado de ofertas. Comprueba que el backend esté disponible.
          </p>
        ) : (
          <FilterableDeals products={products} />
        )}
      </section>
    </div>
  );
}
