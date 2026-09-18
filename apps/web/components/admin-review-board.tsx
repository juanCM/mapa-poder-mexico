"use client";

import { Check, Clock3, ExternalLink, X } from "lucide-react";
import { useState } from "react";
import type { ReviewTask } from "@mapa/contracts";

export function AdminReviewBoard({ initialTasks }: { initialTasks: ReviewTask[] }) {
  const [tasks, setTasks] = useState(initialTasks);
  const [message, setMessage] = useState<string | null>(null);

  async function decide(id: string, status: "approved" | "rejected") {
    const note = window.prompt(status === "approved" ? "Motivo de aprobación:" : "Motivo de rechazo:");
    if (!note || note.trim().length < 3) { setMessage("La decisión requiere una nota de al menos 3 caracteres."); return; }
    const response = await fetch(`/api/admin/review-tasks/${id}/decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision: status, note: note.trim() }) });
    if (!response.ok) { setMessage("No fue posible registrar la decisión. Vuelve a intentarlo."); return; }
    setTasks((current) => current.map((task) => task.id === id ? { ...task, status } : task));
    setMessage(status === "approved" ? "Candidato aprobado y registrado." : "Candidato rechazado y conservado en el historial.");
  }

  return (
    <div>
      {message && <div className="notice" role="status">{message}</div>}
      <div className="review-toolbar">
        <div><strong>{tasks.filter((task) => task.status === "needs_review").length} pendientes</strong><br /><small>Datos cargados desde la API; ordenadas por prioridad y antigüedad</small></div>
      </div>
      {tasks.length === 0 && <div className="notice">No hay tareas reales de revisión. Ejecuta una fuente con <code>mapa-ingest gobierno</code> para generar candidatos.</div>}
      {tasks.map((task) => (
        <article className="review-card" key={task.id}>
          <header>
            <div><span className={`tag priority-${task.priority}`}>{task.priority}</span><h3>{task.title}</h3></div>
            <span className="tag"><Clock3 size={12} /> {task.status}</span>
          </header>
          <p>{task.summary}</p>
          <div className="card-meta"><span>{task.source}</span><span>{new Date(task.detectedAt).toLocaleString("es-MX")}</span></div>
          {task.status === "needs_review" && (
            <div className="review-actions">
              <button className="button button-primary button-small" onClick={() => decide(task.id, "approved")}><Check size={14} /> Aprobar</button>
              <button className="button button-secondary button-small" onClick={() => decide(task.id, "rejected")}><X size={14} /> Rechazar</button>
              <button className="button button-secondary button-small" onClick={() => setMessage(`Abriendo comparación de ${task.source}.`)}><ExternalLink size={14} /> Comparar</button>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
