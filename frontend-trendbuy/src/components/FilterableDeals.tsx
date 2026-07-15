"use client";

import { useMemo, useState } from "react";
import { categoriesFromDashboard, DEFAULT_FILTERS, filterDashboardProducts, storesFromDashboard } from "@/lib/filters";
import type { DashboardProduct } from "@/lib/types";
import { DealsGrid } from "./DealsGrid";
import { FilterBar } from "./FilterBar";
import { NoFilterResults } from "./NoFilterResults";

export function FilterableDeals({ products }: { products: DashboardProduct[] }) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const categories = useMemo(() => categoriesFromDashboard(products), [products]);
  const stores = useMemo(() => storesFromDashboard(products), [products]);
  const filtered = useMemo(() => filterDashboardProducts(products, filters), [products, filters]);

  if (products.length === 0) {
    return <DealsGrid products={products} />;
  }

  return (
    <div className="flex flex-col gap-4">
      <FilterBar
        filters={filters}
        onChange={setFilters}
        categories={categories}
        stores={stores}
        visibleCount={filtered.length}
        totalCount={products.length}
      />
      {filtered.length === 0 ? <NoFilterResults onChange={setFilters} /> : <DealsGrid products={filtered} />}
    </div>
  );
}
