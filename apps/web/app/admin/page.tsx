import Link from "next/link";
import { redirect } from "next/navigation";
import { Activity, Database, GitMerge, ShieldCheck } from "lucide-react";
import { AdminReviewBoard } from "@/components/admin-review-board";
import { getAdminUser } from "@/lib/admin";
import { dataset } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const user = await getAdminUser();
  if (!user) redirect("/admin/login");
  return (
    <div className="container">
      <header className="page-hero">
        <span className="eyebrow"><ShieldCheck size={14} /> Consola editorial</span>
        <h1 className="page-title">Revisión y publicación</h1>
        <p className="page-intro">Sesión: {user.email}. Cada decisión queda registrada; aprobar un candidato no modifica ni elimina su fuente.</p>
      </header>
      {user.preview && <div className="notice"><strong>Modo demostración:</strong> configura Supabase y `ADMIN_EMAIL_ALLOWLIST` para activar autenticación real y persistir decisiones.</div>}
      <div className="admin-shell">
        <nav className="admin-nav" aria-label="Administración">
          <Link href="/admin" className="active"><ShieldCheck size={14} /> Revisión</Link>
          <Link href="/admin"><Activity size={14} /> Ejecuciones</Link>
          <Link href="/admin"><GitMerge size={14} /> Duplicados</Link>
          <Link href="/admin"><Database size={14} /> Fuentes</Link>
        </nav>
        <AdminReviewBoard initialTasks={dataset.reviewTasks} />
      </div>
      <div className="section-sm" />
    </div>
  );
}
