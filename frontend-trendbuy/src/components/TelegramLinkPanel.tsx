"use client";

import { useEffect, useRef, useState } from "react";
import { getMe, getTelegramLinkCode, unlinkTelegram } from "@/lib/api";
import { useAuth } from "@/lib/AppProviders";

const POLL_INTERVAL_MS = 3000;
const POLL_MAX_ATTEMPTS = 40; // ~2 minutes, generous for switching to the Telegram app and back

export function TelegramLinkPanel() {
  const { user, refresh } = useAuth();
  const [status, setStatus] = useState<"idle" | "linking" | "error">("idle");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => stopPolling, []);

  async function handleLink() {
    setStatus("linking");
    try {
      const { deep_link: deepLink } = await getTelegramLinkCode();
      window.open(deepLink, "_blank", "noopener,noreferrer");

      let attempts = 0;
      // Polls getMe() directly (not useAuth().refresh(), which flips a
      // global loading flag the whole header reacts to) so this doesn't
      // flicker the rest of the page every 3s while waiting for the user
      // to confirm inside Telegram.
      pollRef.current = setInterval(async () => {
        attempts += 1;
        const me = await getMe().catch(() => null);

        if (me?.telegram_linked) {
          stopPolling();
          setStatus("idle");
          await refresh();
          return;
        }

        if (attempts >= POLL_MAX_ATTEMPTS) {
          stopPolling();
          setStatus("idle");
        }
      }, POLL_INTERVAL_MS);
    } catch {
      setStatus("error");
    }
  }

  async function handleUnlink() {
    await unlinkTelegram();
    await refresh();
  }

  if (!user) return null;

  if (user.telegram_linked) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">Telegram vinculado</span>
          <span className="text-xs text-zinc-400 dark:text-zinc-500">
            Tus avisos de bajada de precio llegan por Telegram en vez de por correo. Envia /stop al bot para
            silenciarlos.
          </span>
        </div>
        <button
          type="button"
          onClick={handleUnlink}
          className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950/30"
        >
          Desvincular
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">Recibe tus avisos por Telegram</span>
        <span className="text-xs text-zinc-400 dark:text-zinc-500">
          En vez de por correo. Se abre Telegram para confirmar la vinculacion.
        </span>
      </div>
      <button
        type="button"
        onClick={handleLink}
        disabled={status === "linking"}
        className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {status === "linking" ? "Esperando confirmacion..." : "Vincular Telegram"}
      </button>
      {status === "error" && (
        <span className="text-xs text-red-600 dark:text-red-400">No se pudo generar el enlace.</span>
      )}
    </div>
  );
}
