"use client";

import Image from "next/image";
import Link from "next/link";
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
  const googleError = searchParams.get("google_error");
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

  if (googleError) {
    return (
      <>
        <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">No se pudo iniciar sesión</h1>
        <p className="text-sm text-red-600 dark:text-red-400">
          El inicio de sesión con Google no se completó. Puedes volver a intentarlo o entrar con tu email.
        </p>
        <Link
          href="/"
          className="rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          Volver al inicio
        </Link>
      </>
    );
  }

  if (!token) {
    return <p className="text-sm text-red-600 dark:text-red-400">Este enlace no es válido.</p>;
  }

  return (
    <>
      <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">Confirmar acceso</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Pulsa el botón para iniciar sesión en TrendBuy.
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
        <p className="text-sm text-red-600 dark:text-red-400">El enlace no es válido o ha caducado.</p>
      )}
    </>
  );
}

export default function ConfirmPage() {
  return (
    <div className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-6 px-6 py-12 text-center">
      <Image
        src="/wordmark-lockup.png"
        alt="TrendBuy"
        width={1242}
        height={230}
        priority
        className="h-9 w-auto dark:hidden"
      />
      <Suspense fallback={null}>
        <ConfirmForm />
      </Suspense>
    </div>
  );
}
