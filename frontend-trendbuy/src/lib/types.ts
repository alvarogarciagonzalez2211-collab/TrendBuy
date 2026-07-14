// Mirrors the JSON shapes returned by backend-trendbuy verbatim - see
// services/search.py::search_products and api/main.py::get_products_dashboard.
// Keep these in sync by hand; there is no shared schema between the two apps.

export type StoreOffer = {
  store: string;
  price: string;
  url: string;
};

export type ProductFamily = {
  product_id: number;
  name: string;
  is_historic_low: boolean;
  best_status: string;
  discount_percent: string;
  stores: StoreOffer[];
};

export type SearchResponse = {
  query: string;
  families: ProductFamily[];
};

export type DashboardProduct = {
  product_id: number;
  name: string;
  ean: string | null;
  last_price: string | null;
  last_store: string | null;
  cheapest_price: string | null;
  cheapest_store: string | null;
  cheapest_url: string | null;
  currency: string;
  status: string;
  tracked_links: number;
};

export type DashboardResponse = {
  products: DashboardProduct[];
};
