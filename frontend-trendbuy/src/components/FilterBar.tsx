"use client";

import { DEFAULT_FILTERS, DISCOUNT_STEPS, hasActiveFilters, type Filters } from "@/lib/filters";

const SELECT_CLASS =
  "rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50";

export function FilterBar({
  filters,
  onChange,
  categories,
  stores,
  visibleCount,
  totalCount,
}: {
  filters: Filters;
  onChange: (next: Filters) => void;
  categories: string[];
  stores: string[];
  visibleCount: number;
  totalCount: number;
}) {
  const active = hasActiveFilters(filters);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          Precio máximo
          <input
            type="number"
            inputMode="decimal"
            min={0}
            placeholder="Sin límite"
            value={filters.maxPrice}
            onChange={(event) => onChange({ ...filters, maxPrice: event.target.value })}
            className={`w-32 ${SELECT_CLASS}`}
          />
        </label>

        <label className="flex flex-col gap-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          Descuento mínimo
          <select
            value={filters.minDiscount}
            onChange={(event) => onChange({ ...filters, minDiscount: Number(event.target.value) })}
            className={SELECT_CLASS}
          >
            {DISCOUNT_STEPS.map((step) => (
              <option key={step} value={step}>
                {step === 0 ? "Cualquiera" : `${step}% o más`}
              </option>
            ))}
          </select>
        </label>

        {categories.length > 0 && (
          <label className="flex flex-col gap-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            Tipo de producto
            <select
              value={filters.category}
              onChange={(event) => onChange({ ...filters, category: event.target.value })}
              className={SELECT_CLASS}
            >
              <option value="all">Todos</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
        )}

        {stores.length > 0 && (
          <label className="flex flex-col gap-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            Tienda
            <select
              value={filters.store}
              onChange={(event) => onChange({ ...filters, store: event.target.value })}
              className={SELECT_CLASS}
            >
              <option value="all">Todas</option>
              {stores.map((store) => (
                <option key={store} value={store}>
                  {store}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="flex items-center gap-2 pb-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={filters.onlyHistoricLow}
            onChange={(event) => onChange({ ...filters, onlyHistoricLow: event.target.checked })}
            className="h-4 w-4 rounded border-zinc-300 text-amber-500 focus:ring-amber-500 dark:border-zinc-700"
          />
          Solo mínimos históricos
        </label>

        {active && (
          <button
            type="button"
            onClick={() => onChange(DEFAULT_FILTERS)}
            className="mb-0.5 rounded-lg border border-zinc-300 px-3 py-2 text-xs font-medium text-zinc-600 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {active && (
        <p className="text-xs text-zinc-400 dark:text-zinc-500">
          Mostrando {visibleCount} de {totalCount}
        </p>
      )}
    </div>
  );
}
