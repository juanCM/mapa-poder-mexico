"use client";

import { useState } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { createSupabaseBrowserClient } from "@/lib/supabase";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setStatus("Supabase aún no está configurado. En desarrollo, abre /admin para usar el modo demostración.");
      return;
    }
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setStatus(error ? "No fue posible iniciar sesión. Verifica tu correo y contraseña." : "Acceso correcto. Abriendo la consola…");
    if (!error) window.location.assign("/admin");
  }

  return (
    <form onSubmit={submit}>
      <span className="card-icon"><LockKeyhole size={20} /></span>
      <h1>Acceso editorial</h1>
      <p>La consulta es pública. La revisión y publicación requieren un correo autorizado y contraseña.</p>
      <div className="form-field"><label htmlFor="email">Correo autorizado</label><input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="tu@correo.mx" /></div>
      <div className="form-field"><label htmlFor="password">Contraseña</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></div>
      <button className="button button-primary" type="submit">Entrar <ArrowRight size={16} /></button>
      {status && <div className="notice" role="status" style={{ marginTop: "1rem" }}>{status}</div>}
    </form>
  );
}
