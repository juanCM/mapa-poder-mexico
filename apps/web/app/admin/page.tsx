import { redirect } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { AdminDashboard, type AdminOverview } from "@/components/admin-dashboard";
import { getAdminUser } from "@/lib/admin";
import type { ReviewBatch, ReviewTask } from "@mapa/contracts";

export const dynamic = "force-dynamic";

function adminHeaders(): Record<string, string> {
  return process.env.ADMIN_API_TOKEN ? { Authorization: `Bearer ${process.env.ADMIN_API_TOKEN}` } : {};
}

async function loadReviewTasks(): Promise<{ tasks: ReviewTask[]; error?: string }> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return { tasks: [], error: "La URL de la API no está configurada." };

  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/v1/admin/review-tasks`, {
      cache: "no-store", headers: adminHeaders()
    });
    if (!response.ok) return { tasks: [], error: `La API respondió con ${response.status}.` };
    const tasks = await response.json() as ReviewTask[];
    return { tasks };
  } catch {
    return { tasks: [], error: "No fue posible conectar con la API local." };
  }
}

async function loadAdminOverview(): Promise<{ overview: AdminOverview; error?: string }> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const empty: AdminOverview = { runs: [], duplicates: [], sources: [] };
  if (!apiUrl) return { overview: empty, error: "La URL de la API no está configurada." };
  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/v1/admin/overview`, { cache: "no-store", headers: adminHeaders() });
    if (!response.ok) return { overview: empty, error: `La API respondió con ${response.status}.` };
    return { overview: await response.json() as AdminOverview };
  } catch { return { overview: empty, error: "No fue posible conectar con la API local." }; }
}

async function loadReviewBatches(): Promise<{ batches: ReviewBatch[]; error?: string }> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return { batches: [], error: "La URL de la API no está configurada." };
  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/v1/admin/review-batches`, {
      cache: "no-store", headers: adminHeaders()
    });
    if (!response.ok) return { batches: [], error: `La API respondió con ${response.status}.` };
    return { batches: await response.json() as ReviewBatch[] };
  } catch {
    return { batches: [], error: "No fue posible cargar los lotes editoriales." };
  }
}

export default async function AdminPage() {
  const user = await getAdminUser();
  if (!user) redirect("/admin/login");
  const [{ tasks, error: taskError }, { batches, error: batchError }, { overview, error: overviewError }] = await Promise.all([loadReviewTasks(), loadReviewBatches(), loadAdminOverview()]);
  const error = taskError ?? batchError ?? overviewError;
  return (
    <div className="container">
      <header className="page-hero">
        <span className="eyebrow"><ShieldCheck size={14} /> Consola editorial</span>
        <h1 className="page-title">Revisión y publicación</h1>
        <p className="page-intro">Sesión: {user.email}. Cada decisión queda registrada; aprobar un candidato no modifica ni elimina su fuente.</p>
      </header>
      {user.preview && <div className="notice"><strong>Acceso local temporal:</strong> el bypass está activo sólo para validar la consola. Los datos mostrados provienen de la API y PostgreSQL.</div>}
      {error && <div className="notice"><strong>Datos no disponibles:</strong> {error}</div>}
      <AdminDashboard initialTasks={tasks} initialBatches={batches} overview={overview} />
      <div className="section-sm" />
    </div>
  );
}
