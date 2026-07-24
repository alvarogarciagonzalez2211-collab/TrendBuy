import type { DashboardProduct, ProductFamily } from "./types";

// Pure client-side subsetting of an already backend-sorted list - this never
// recomputes discount %, status or historic-low (that stays server-side per
// CLAUDE.md rule 4), it only decides which already-computed items to show.
export type Filters = {
  maxPrice: string;
  minDiscount: number;
  interest: string;
  category: string;
  store: string;
  onlyHistoricLow: boolean;
};

export const DEFAULT_FILTERS: Filters = {
  maxPrice: "",
  minDiscount: 0,
  interest: "all",
  category: "all",
  store: "all",
  onlyHistoricLow: false,
};

// One tap = one shopping intent. Each interest is a coarse bundle of the
// backend's fine-grained categories (services/categories.py) - the mapping
// lives client-side only because it's pure presentation grouping: nothing is
// recomputed, it just decides which already-tagged items to show (rule 4).
export type Interest = {
  id: string;
  label: string;
  icon: string;
  categories: string[];
};

export const INTERESTS: Interest[] = [
  {
    id: "tecnologia",
    label: "Tecnología",
    icon: "💻",
    categories: ["Moviles", "Televisores", "Portatiles", "Tablets", "Auriculares", "Informatica", "Videojuegos"],
  },
  { id: "ropa", label: "Ropa y moda", icon: "👕", categories: ["Ropa"] },
  { id: "hogar", label: "Hogar", icon: "🛋️", categories: ["Hogar", "Electrodomesticos"] },
  { id: "belleza", label: "Belleza", icon: "✨", categories: ["Belleza"] },
  { id: "deportes", label: "Deportes", icon: "🏃", categories: ["Deportes"] },
  { id: "cultura", label: "Libros y ocio", icon: "📚", categories: ["Libros", "Juguetes", "Videojuegos"] },
];

export const DISCOUNT_STEPS = [0, 10, 20, 30, 50] as const;

export function hasActiveFilters(filters: Filters): boolean {
  return (
    filters.maxPrice.trim() !== "" ||
    filters.minDiscount > 0 ||
    filters.interest !== "all" ||
    filters.category !== "all" ||
    filters.store !== "all" ||
    filters.onlyHistoricLow
  );
}

type FilterableItem = {
  price: number | null;
  discountPercent: number;
  categories: string[];
  stores: string[];
  isHistoricLow: boolean;
};

function matches(item: FilterableItem, filters: Filters): boolean {
  if (filters.maxPrice.trim() !== "") {
    const max = Number(filters.maxPrice);
    if (!Number.isNaN(max) && (item.price === null || item.price > max)) return false;
  }
  if (item.discountPercent < filters.minDiscount) return false;
  if (filters.interest !== "all") {
    const interest = INTERESTS.find((entry) => entry.id === filters.interest);
    if (interest && !item.categories.some((category) => interest.categories.includes(category))) return false;
  }
  if (filters.category !== "all" && !item.categories.includes(filters.category)) return false;
  if (filters.store !== "all" && !item.stores.includes(filters.store)) return false;
  if (filters.onlyHistoricLow && !item.isHistoricLow) return false;
  return true;
}

function toFilterableDashboard(product: DashboardProduct): FilterableItem {
  return {
    price: product.cheapest_price !== null ? Number(product.cheapest_price) : null,
    discountPercent: Number(product.discount_percent ?? "0"),
    categories: product.categories ?? [],
    stores: product.cheapest_store ? [product.cheapest_store] : [],
    isHistoricLow: product.is_historic_low,
  };
}

function toFilterableFamily(family: ProductFamily): FilterableItem {
  return {
    // family.stores is already sorted cheapest-first by the backend.
    price: family.stores[0] ? Number(family.stores[0].price) : null,
    discountPercent: Number(family.discount_percent ?? "0"),
    categories: family.categories ?? [],
    stores: family.stores.map((offer) => offer.store),
    isHistoricLow: family.is_historic_low,
  };
}

export function filterDashboardProducts(products: DashboardProduct[], filters: Filters): DashboardProduct[] {
  return products.filter((product) => matches(toFilterableDashboard(product), filters));
}

export function filterFamilies(families: ProductFamily[], filters: Filters): ProductFamily[] {
  return families.filter((family) => matches(toFilterableFamily(family), filters));
}

export function categoriesFromDashboard(products: DashboardProduct[]): string[] {
  return uniqueSorted(products.flatMap((product) => product.categories ?? []));
}

export function categoriesFromFamilies(families: ProductFamily[]): string[] {
  return uniqueSorted(families.flatMap((family) => family.categories ?? []));
}

export function storesFromDashboard(products: DashboardProduct[]): string[] {
  return uniqueSorted(products.map((product) => product.cheapest_store).filter((store): store is string => Boolean(store)));
}

export function storesFromFamilies(families: ProductFamily[]): string[] {
  return uniqueSorted(families.flatMap((family) => family.stores.map((offer) => offer.store)));
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b, "es"));
}
