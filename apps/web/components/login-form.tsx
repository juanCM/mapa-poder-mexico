"use client";

import { useState } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { createSupabaseBrowserClient } from "@/lib/supabase";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setStatus("Supabase aún no está configurado. En desarrollo, abre /admin para usar el modo demostración.");
      return;
    }
    const redirectTo = `${window.location.origin}/auth/callback?next=/admin`;
    const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: redirectTo } });
    setStatus(error ? error.message : "Revisa tu correo para continuar.");
  }

  return (
    <form onSubmit={submit}>
      <span className="card-icon"><LockKeyhole size={20} /></span>
      <h1>Acceso editorial</h1>
      <p>La consulta es pública. La revisión y publicación están reservadas al equipo autorizado.</p>
      <div className="form-field"><label htmlFor="email">Correo autorizado</label><input id="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="tu@correo.mx" /></div>
      <button className="button button-primary" type="submit">Enviar enlace de acceso <ArrowRight size={16} /></button>
      {status && <div className="notice" role="status" style={{ marginTop: "1rem" }}>{status}</div>}
    </form>
  );
}
