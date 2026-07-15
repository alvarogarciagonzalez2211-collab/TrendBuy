"use client";

import { useEffect, useState } from "react";
import { createFavorite, deleteFavorite, getCategories } from "@/lib/api";
import { useAuth, useFavorites } from "@/lib/AppProviders";
import type { Category, Favorite } from "@/lib/types";
import { TelegramLinkPanel } from "@/components/TelegramLinkPanel";

function FavoriteRow({ favorite }: { favorite: Favorite }) {
  const { refresh } = useFavorites();
  const [precioMaximo, setPrecioMaximo] = useState(favorite.precio_maximo ?? "");
  const [descuentoMinimo, setDescuentoMinimo] = useState(favorite.descuento_minimo_percent ?? "");
  const [saving, setSaving] = useState(false);

  const title = favorite.producto_nombre ?? favorite.categoria_nombre ?? "Favorito";

  async function handleSave() {
    setSaving(true);
    try {
      await createFavorite({
        producto_id: favorite.producto_id ?? undefined,
        categoria_id: favorite.categoria_id ?? undefined,
        precio_maximo: precioMaximo === "" ? null : Number(precioMaximo),
        descuento_minimo_percent: descuentoMinimo === "" ? null : Number(descuentoMinimo),
      });
      await refresh();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    await deleteFavorite(favorite.id);
    await refresh();
  }

  return (
    <li className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">{title}</span>
        <span className="text-xs text-zinc-400 dark:text-zinc-500">
          {favorite.categoria_id !== null ? "Categoria" : "Producto"}
        </span>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-zinc-500 dark:text-zinc-400">
          Precio maximo (EUR)
          <input
            type="number"
            min="0"
            step="0.01"
            value={precioMaximo}
            onChange={(event) => setPrecioMaximo(event.target.value)}
            placeholder="Sin limite"
            className="w-28 rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-zinc-500 dark:text-zinc-400">
          Rebaja minima (%)
          <input
            type="number"
            min="0"
            max="100"
            step="1"
            value={descuentoMinimo}
            onChange={(event) => setDescuentoMinimo(event.target.value)}
            placeholder="Cualquiera"
            className="w-24 rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
          />
        </label>

        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          Guardar
        </button>
        <button
          type="button"
          onClick={handleDelete}
          className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950/30"
        >
          Quitar
        </button>
      </div>
    </li>
  );
}

function AddCategoryFavorite() {
  const { favorites, refresh } = useFavorites();
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState<string>("");
  const [descuentoMinimo, setDescuentoMinimo] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  const favoritedCategoryIds = new Set(favorites.map((favorite) => favorite.categoria_id));
  const availableCategories = categories.filter((category) => !favoritedCategoryIds.has(category.id));

  async function handleAdd() {
    if (!categoryId) return;
    setSaving(true);
    try {
      await createFavorite({
        categoria_id: Number(categoryId),
        descuento_minimo_percent: descuentoMinimo === "" ? null : Number(descuentoMinimo),
      });
      setCategoryId("");
      setDescuentoMinimo("");
      await refresh();
    } finally {
      setSaving(false);
    }
  }

  if (availableCategories.length === 0) return null;

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
      <label className="flex flex-col gap-1 text-xs text-zinc-500 dark:text-zinc-400">
        Categoria
        <select
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          className="w-44 rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
        >
          <option value="">Selecciona...</option>
          {availableCategories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.nombre}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs text-zinc-500 dark:text-zinc-400">
        Rebaja minima (%)
        <input
          type="number"
          min="0"
          max="100"
          step="1"
          value={descuentoMinimo}
          onChange={(event) => setDescuentoMinimo(event.target.value)}
          placeholder="Cualquiera"
          className="w-24 rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
        />
      </label>

      <button
        type="button"
        onClick={handleAdd}
        disabled={!categoryId || saving}
        className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        Anadir tema a favoritos
      </button>
    </div>
  );
}

export default function FavoritosPage() {
  const { user, loading } = useAuth();
  const { favorites, loading: favoritesLoading } = useFavorites();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-12">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Tus favoritos</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Te avisamos por correo (o por Telegram, si lo vinculas abajo) cuando un producto o tema favorito baje de
        precio, segun los limites que pongas aqui. Sin limites, te avisamos con cualquier bajada real.
      </p>

      {loading ? null : !user ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Inicia sesion (arriba a la derecha) para gestionar tus favoritos.
        </p>
      ) : (
        <>
          <TelegramLinkPanel />
          <AddCategoryFavorite />

          {favoritesLoading ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Cargando...</p>
          ) : favorites.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Aun no tienes favoritos. Anade un tema arriba, o pulsa la estrella en cualquier producto del
              buscador o del listado de ofertas.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {favorites.map((favorite) => (
                <FavoriteRow key={favorite.id} favorite={favorite} />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
