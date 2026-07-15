import type { DashboardProduct } from "@/lib/types";
import { DealCard } from "./DealCard";
import { EmptyState } from "./EmptyState";

export function DealsGrid({ products }: { products: DashboardProduct[] }) {
  if (products.length === 0) {
    return (
      <EmptyState message="Todavía no hay chollos detectados. Prueba a buscar un producto arriba para empezar a rastrear precios." />
    );
  }

  return (
    // Order comes pre-sorted from the backend (best status, cheapest first) -
    // see api/main.py::get_products_dashboard, not re-ranked here.
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {products.map((product) => (
        <DealCard key={product.product_id} product={product} />
      ))}
    </div>
  );
}
