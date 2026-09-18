import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

export async function getAdminUser() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const allowlist = (process.env.ADMIN_EMAIL_ALLOWLIST ?? "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

  // Bypass temporal sólo para validar la consola en la máquina local. Nunca se
  // habilita en una compilación de producción, incluso si la variable llegara
  // a configurarse accidentalmente en Vercel.
  if (process.env.NODE_ENV !== "production" && process.env.ADMIN_BYPASS_AUTH === "true") {
    return { email: allowlist[0] ?? "admin@localhost", preview: true };
  }

  if (!url || !key) {
    return process.env.NODE_ENV === "development"
      ? { email: "demo@localhost", preview: true }
      : null;
  }

  const cookieStore = await cookies();
  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: () => undefined
    }
  });
  const { data } = await supabase.auth.getUser();
  const email = data.user?.email?.toLowerCase();
  if (!email || !allowlist.includes(email)) return null;
  return { email, preview: false };
}
