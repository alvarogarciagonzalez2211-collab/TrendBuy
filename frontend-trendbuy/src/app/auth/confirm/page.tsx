"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { confirmLogin } from "@/lib/api";
import { useAuth } from "@/lib/AppProviders";

// Deliberately NOT auto-confirmed on page load: some corporate email clients
// pre-fetch links inside an email to scan them for phishing before the real
// user ever opens it. If GET-ing this page (or an automatic effect here)
// consumed the single-use token, that prefetch would burn it and the real
// user's click would fail. Requiring an explicit button press means only a
// genuine user action can consume the token.
function ConfirmForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const router = useRouter();
  const { refresh } = useAuth();
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");

  async function handleConfirm() {
    if (!token) return;
    setStatus("loading");
    try {
      await confirmLogin(token);
      await refresh();
      router.push("/");
    } catch {
      setStatus("error");
    }
  }

  if (!token) {
    return <p className="text-sm text-red-600 dark:text-red-400">Este enlace no es valido.</p>;
  }

  return (
    <>
      <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">Confirmar acceso</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Pulsa el boton para iniciar sesion en TrendBuy.
      </p>
      <button
        type="button"
        onClick={handleConfirm}
        disabled={status === "loading"}
        className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
      >
        {status === "loading" ? "Confirmando..." : "Confirmar acceso"}
      </button>
      {status === "error" && (
        <p className="text-sm text-red-600 dark:text-red-400">El enlace no es valido o ha caducado.</p>
      )}
    </>
  );
}

export default function ConfirmPage() {
  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      <Suspense fallback={null}>
        <ConfirmForm />
      </Suspense>
    </div>
  );
}
