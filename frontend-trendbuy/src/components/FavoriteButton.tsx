"use client";

import { useState } from "react";
import { createFavorite, deleteFavorite } from "@/lib/api";
import { useAuth, useFavorites } from "@/lib/AppProviders";

export function FavoriteButton({ productId }: { productId: number }) {
  const { user } = useAuth();
  const { favorites, refresh } = useFavorites();
  const [busy, setBusy] = useState(false);

  // Cards are clickable to expand the price-history chart (see
  // ProductFamilyCard/DealCard) - this button lives inside that clickable
  // area, so every handler here stops propagation to avoid toggling both.
  if (!user) return null;

  const favorite = favorites.find((entry) => entry.producto_id === productId);
  const active = Boolean(favorite);

  async function toggle(event: React.MouseEvent) {
    event.stopPropagation();
    if (busy) return;

    setBusy(true);
    try {
      if (active && favorite) {
        await deleteFavorite(favorite.id);
      } else {
        await createFavorite({ producto_id: productId });
      }
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={active}
      title={active ? "Quitar de favoritos" : "Anadir a favoritos"}
      className={`rounded-full bg-white/80 p-1.5 backdrop-blur transition dark:bg-zinc-900/80 ${
        active ? "text-amber-500" : "text-zinc-300 hover:text-zinc-400 dark:text-zinc-600 dark:hover:text-zinc-500"
      }`}
    >
      <svg viewBox="0 0 24 24" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
        <path
          d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
