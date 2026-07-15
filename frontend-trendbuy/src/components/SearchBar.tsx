"use client";

import { useMemo, useState, type FormEvent } from "react";
import { searchProducts } from "@/lib/api";
import {
  categoriesFromFamilies,
  DEFAULT_FILTERS,
  filterFamilies,
  storesFromFamilies,
} from "@/lib/filters";
import type { SearchResponse } from "@/lib/types";
import { FilterBar } from "./FilterBar";
import { NoFilterResults } from "./NoFilterResults";
import { SearchResults } from "./SearchResults";
import { SearchSkeleton } from "./SearchSkeleton";

// A real search scrapes 4 stores live and can take 30-40s uncached (Redis
// caches repeats for 15 min, see services/search.py) - this is not an
// as-you-type autocomplete, it fires on submit with an explicit loading state
// so the wait doesn't read as a broken UI.
export function SearchBar() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const categories = useMemo(() => (result ? categoriesFromFamilies(result.families) : []), [result]);
  const stores = useMemo(() => (result ? storesFromFamilies(result.families) : []), [result]);
  const filteredFamilies = useMemo(
    () => (result ? filterFamilies(result.families, filters) : []),
    [result, filters],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    setStatus("loading");
    setErrorMessage(null);
    setFilters(DEFAULT_FILTERS);

    try {
      const data = await searchProducts(trimmed);
      setResult(data);
      setStatus("idle");
    } catch {
      setErrorMessage("No se pudo completar la búsqueda. Inténtalo de nuevo.");
      setStatus("error");
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Busca un producto, p. ej. iphone"
          className="flex-1 rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
        />
        <button
          type="submit"
          disabled={status === "loading" || query.trim().length === 0}
          className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Buscar
        </button>
      </form>

      {status === "loading" && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Buscando en Amazon, PcComponentes, MediaMarkt y Worten… puede tardar hasta 40 segundos.
          </p>
          <SearchSkeleton />
        </div>
      )}

      {status === "error" && errorMessage && (
        <p className="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
      )}

      {status === "idle" && result && (
        <div className="flex flex-col gap-4">
          {result.families.length > 0 && (
            <FilterBar
              filters={filters}
              onChange={setFilters}
              categories={categories}
              stores={stores}
              visibleCount={filteredFamilies.length}
              totalCount={result.families.length}
            />
          )}
          {result.families.length > 0 && filteredFamilies.length === 0 ? (
            <NoFilterResults onChange={setFilters} />
          ) : (
            <SearchResults families={filteredFamilies} query={result.query} />
          )}
        </div>
      )}
    </section>
  );
}
