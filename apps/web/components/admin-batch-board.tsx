"use client";

import { CheckCheck, Layers3, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { ReviewBatch, ReviewTask } from "@mapa/contracts";

export function AdminBatchBoard({ initialBatches, tasks }: { initialBatches: ReviewBatch[]; tasks: ReviewTask[] }) {
  const [batches, setBatches] = useState(initialBatches);
  const [excluded, setExcluded] = useState<Record<string, Set<string>>>({});
  const [message, setMessage] = useState<string | null>(null);
  const tasksByBatch = useMemo(() => {
    const grouped = new Map<string, ReviewTask[]>();
    for (const task of tasks) {
      if (!task.batchId) continue;
      grouped.set(task.batchId, [...(grouped.get(task.batchId) ?? []), task]);
    }
    return grouped;
  }, [tasks]);

  function toggle(batchId: string, taskId: string) {
    setExcluded((current) => {
      const next = new Set(current[batchId] ?? []);
      if (next.has(taskId)) next.delete(taskId); else next.add(taskId);
      return { ...current, [batchId]: next };
    });
  }

  async function decide(batch: ReviewBatch, decision: "approved" | "rejected") {
    const note = window.prompt(decision === "approved" ? "Motivo de aprobación del lote:" : "Motivo de rechazo del lote:");
    if (!note || note.trim().length < 3) {
      setMessage("La decisión requiere una nota de al menos 3 caracteres.");
      return;
    }
    const response = await fetch(`/api/admin/review-batches/${batch.id}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision,
        note: note.trim(),
        excludedTaskIds: [...(excluded[batch.id] ?? [])]
      })
    });
    if (!response.ok) {
      setMessage("No fue posible registrar la decisión del lote.");
      return;
    }
    const payload = await response.json() as { changed: number };
    setBatches((current) => current.map((item) => item.id === batch.id ? {
      ...item,
      status: excluded[batch.id]?.size ? "partially_reviewed" : decision,
      pending: Math.max(0, item.pending - payload.changed),
      approved: item.approved + (decision === "approved" ? payload.changed : 0),
      rejected: item.rejected + (decision === "rejected" ? payload.changed : 0)
    } : item));
    setMessage(`${payload.changed} tareas del lote fueron ${decision === "approved" ? "aprobadas" : "rechazadas"}.`);
  }

  if (!batches.length) return <div className="notice">No hay lotes editoriales. Las próximas ejecuciones de ingestión crearán uno automáticamente.</div>;

  return (
    <div>
      {message && <div className="notice" role="status">{message}</div>}
      <div className="admin-list">
        {batches.map((batch) => {
          const batchTasks = (tasksByBatch.get(batch.id) ?? []).filter((task) => task.status === "needs_review");
          return (
            <article className="review-card" key={batch.id}>
              <header>
                <div><span className="tag"><Layers3 size={12} /> {batch.adapter}</span><h3>{batch.title}</h3></div>
                <span className="tag">{batch.status}</span>
              </header>
              <p>{batch.total} candidatos · {batch.pending} pendientes · {batch.approved} aprobados · {batch.rejected} rechazados · {batch.published} publicados</p>
              {batchTasks.length > 0 && (
                <details>
                  <summary>Revisar exclusiones ({batchTasks.length})</summary>
                  <div className="admin-list">
                    {batchTasks.map((task) => (
                      <label key={task.id}>
                        <input type="checkbox" checked={!excluded[batch.id]?.has(task.id)} onChange={() => toggle(batch.id, task.id)} />
                        {task.title}
                      </label>
                    ))}
                  </div>
                </details>
              )}
              {batch.pending > 0 && (
                <div className="review-actions">
                  <button className="button button-primary button-small" onClick={() => void decide(batch, "approved")}><CheckCheck size={14} /> Aprobar incluidos</button>
                  <button className="button button-secondary button-small" onClick={() => void decide(batch, "rejected")}><X size={14} /> Rechazar incluidos</button>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
