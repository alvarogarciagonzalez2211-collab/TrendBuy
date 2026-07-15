"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { requestLogin } from "@/lib/api";
import { useAuth } from "@/lib/AppProviders";

export function AuthHeader() {
  const { user, loading, logout } = useAuth();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;

    setStatus("sending");
    try {
      await requestLogin(trimmed);
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  if (loading) return <div className="h-8" />;

  if (user) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <Link href="/favoritos" className="text-zinc-600 hover:underline dark:text-zinc-300">
          Favoritos
        </Link>
        <span className="text-zinc-500 dark:text-zinc-400">{user.email}</span>
        <button
          type="button"
          onClick={() => logout()}
          className="rounded-md border border-zinc-300 px-2.5 py-1 text-xs text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
        >
          Cerrar sesion
        </button>
      </div>
    );
  }

  if (status === "sent") {
    return <p className="text-xs text-zinc-500 dark:text-zinc-400">Revisa tu correo para confirmar el acceso.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        type="email"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="tu@email.com"
        className="w-40 rounded-md border border-zinc-300 px-2.5 py-1 text-xs text-zinc-900 outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
      />
      <button
        type="submit"
        disabled={status === "sending"}
        className="rounded-md bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {status === "sending" ? "Enviando..." : "Entrar"}
      </button>
      {status === "error" && <span className="text-xs text-red-600 dark:text-red-400">Error</span>}
    </form>
  );
}
