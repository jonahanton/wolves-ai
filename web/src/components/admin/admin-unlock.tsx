"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function AdminUnlock() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<"idle" | "checking" | "denied">("idle");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatus("checking");
    const response = await fetch("/api/admin-session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (response.ok) router.refresh();
    else setStatus("denied");
  };

  return (
    <form onSubmit={submit} className="max-w-[420px]">
      <label htmlFor="admin-token" className="mb-3 block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
        Admin token
      </label>
      <input
        id="admin-token"
        type="password"
        value={token}
        onChange={(event) => setToken(event.target.value)}
        className="w-full border border-hairline bg-night-2 px-4 py-3 font-mono text-[15px] text-cream outline-none focus:border-gold"
        autoComplete="off"
      />
      <button
        type="submit"
        disabled={status === "checking" || token.length === 0}
        className="mt-4 rounded-pill border border-hairline px-6 py-2.5 font-mono text-[12.5px] uppercase tracking-[0.12em] text-cream-dim hover:border-gold hover:text-cream disabled:opacity-40"
      >
        {status === "checking" ? "checking" : "unlock"}
      </button>
      {status === "denied" && <p className="mt-3 font-mono text-[13px] text-red">Not authorised.</p>}
    </form>
  );
}
