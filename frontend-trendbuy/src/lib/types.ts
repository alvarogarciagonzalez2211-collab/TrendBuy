// Mirrors the JSON shapes returned by backend-trendbuy verbatim - see
// services/search.py::search_products and api/main.py::get_products_dashboard.
// Keep these in sync by hand; there is no shared schema between the two apps.

export type StoreOffer = {
  store: string;
  price: string;
  url: string;
  image_url: string | null;
};

export type ProductFamily = {
  product_id: number;
  name: string;
  is_historic_low: boolean;
  best_status: string;
  discount_percent: string;
  categories: string[];
  image_url: string | null;
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
  is_historic_low: boolean;
  discount_percent: string;
  categories: string[];
  image_url: string | null;
  tracked_links: number;
};

export type DashboardResponse = {
  products: DashboardProduct[];
};

// Mirrors services/predictor.py::analyze_product / classify_best_moment.
export type BestMoment = {
  status: string;
  current_price: string | null;
  percentile_25: string | null;
  historic_min: string | null;
  records?: number;
  message?: string;
};

export type PriceHistoryPoint = {
  link_id: number;
  store: string;
  date: string | null;
  price: string | null;
};

export type ForecastPoint = {
  ds: string;
  yhat: string | null;
  yhat_lower: string | null;
  yhat_upper: string | null;
};

export type ProductAnalysis = {
  product_id: number;
  product_name: string;
  image_url: string | null;
  best_moment: BestMoment;
  history: PriceHistoryPoint[];
  forecast_30_days: ForecastPoint[];
  warnings: string[];
};

// Mirrors api/auth.py and api/favorites.py.
export type User = {
  id: number;
  email: string;
};

export type Category = {
  id: number;
  nombre: string;
};

export type Favorite = {
  id: number;
  producto_id: number | null;
  producto_nombre: string | null;
  categoria_id: number | null;
  categoria_nombre: string | null;
  precio_maximo: string | null;
  descuento_minimo_percent: string | null;
};
