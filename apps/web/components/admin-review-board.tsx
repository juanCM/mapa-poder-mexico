"use client";

import { Check, Clock3, ExternalLink, Play, X } from "lucide-react";
import { useState } from "react";
import type { ReviewTask } from "@mapa/contracts";

export function AdminReviewBoard({ initialTasks }: { initialTasks: ReviewTask[] }) {
  const [tasks, setTasks] = useState(initialTasks);
  const [message, setMessage] = useState<string | null>(null);

  function decide(id: string, status: "approved" | "rejected") {
    setTasks((current) => current.map((task) => task.id === id ? { ...task, status } : task));
    setMessage(status === "approved" ? "Candidato aprobado. Quedó listo para publicación." : "Candidato rechazado y conservado en el historial.");
  }

  return (
    <div>
      {message && <div className="notice" role="status">{message}</div>}
      <div className="review-toolbar">
        <div><strong>{tasks.filter((task) => task.status === "needs_review").length} pendientes</strong><br /><small>Ordenadas por prioridad y antigüedad</small></div>
        <button className="button button-primary button-small" onClick={() => setMessage("Ejecución demostrativa iniciada. En producción se enviará al worker.")}><Play size={14} /> Ejecutar fuentes</button>
      </div>
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
