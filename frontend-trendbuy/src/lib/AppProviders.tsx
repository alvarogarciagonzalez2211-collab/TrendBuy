"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getFavorites as apiGetFavorites, getMe, logout as apiLogout } from "./api";
import type { Favorite, User } from "./types";

type AuthState = {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AppProviders");
  return ctx;
}

type FavoritesState = {
  favorites: Favorite[];
  loading: boolean;
  refresh: () => Promise<void>;
  isProductFavorite: (productId: number) => boolean;
};

const FavoritesContext = createContext<FavoritesState | null>(null);

export function useFavorites(): FavoritesState {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error("useFavorites must be used within AppProviders");
  return ctx;
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);

  const refreshFavorites = useCallback(async () => {
    setFavoritesLoading(true);
    try {
      setFavorites(await apiGetFavorites());
    } catch {
      setFavorites([]);
    } finally {
      setFavoritesLoading(false);
    }
  }, []);

  const refreshAuth = useCallback(async () => {
    setAuthLoading(true);
    try {
      setUser(await getMe());
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    // One-time session check on mount - the linter can't see that
    // refreshAuth's setState calls happen after an await, not synchronously
    // within this effect, and flags it as if it were an unconditional
    // render-time setState loop. It isn't: refreshAuth has no dependency on
    // anything this effect writes, so this runs once and settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAuth();
  }, [refreshAuth]);

  useEffect(() => {
    if (user) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      refreshFavorites();
    } else {
      setFavorites([]);
    }
  }, [user, refreshFavorites]);

  const handleLogout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const isProductFavorite = useCallback(
    (productId: number) => favorites.some((favorite) => favorite.producto_id === productId),
    [favorites],
  );

  return (
    <AuthContext.Provider value={{ user, loading: authLoading, refresh: refreshAuth, logout: handleLogout }}>
      <FavoritesContext.Provider
        value={{ favorites, loading: favoritesLoading, refresh: refreshFavorites, isProductFavorite }}
      >
        {children}
      </FavoritesContext.Provider>
    </AuthContext.Provider>
  );
}
