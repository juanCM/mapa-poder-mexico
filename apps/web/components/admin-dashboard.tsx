"use client";

import { Activity, Database, GitMerge, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { AdminReviewBoard } from "@/components/admin-review-board";
import { AdminBatchBoard } from "@/components/admin-batch-board";
import type { ReviewBatch, ReviewTask } from "@mapa/contracts";

type Run = { id: string; adapter: string; status: string; startedAt: string | null; finishedAt: string | null; discoveredCount: number; candidateCount: number; snapshotCount: number; errorMessage: string | null };
type Duplicate = { candidateKey: string; count: number; detectedAt: string; titles: string[] };
type Source = { id: string; publisher: string; title: string; url: string; type: string; enabled: boolean; trustTier: string; adapter: string | null; lastRetrievedAt: string | null; snapshotCount: number };

export type AdminOverview = { runs: Run[]; duplicates: Duplicate[]; sources: Source[] };
type Section = "batches" | "review" | "runs" | "duplicates" | "sources";

const sections: { id: Section; label: string; Icon: typeof ShieldCheck }[] = [
  { id: "batches", label: "Lotes", Icon: ShieldCheck },
  { id: "review", label: "Revisión", Icon: ShieldCheck },
  { id: "runs", label: "Ejecuciones", Icon: Activity },
  { id: "duplicates", label: "Duplicados", Icon: GitMerge },
  { id: "sources", label: "Fuentes", Icon: Database },
];

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
}

export function AdminDashboard({ initialTasks, initialBatches, overview }: { initialTasks: ReviewTask[]; initialBatches: ReviewBatch[]; overview: AdminOverview }) {
  const [section, setSection] = useState<Section>("batches");
  const labels = { batches: ["Lotes editoriales", "Aprueba o rechaza importaciones completas y excluye casos ambiguos antes de publicar."], review: ["Revisión editorial", "Candidatos pendientes de validar antes de afectar el mapa público."], runs: ["Ejecuciones de ingesta", "Historial de procesos ejecutados por cada adaptador."], duplicates: ["Posibles duplicados", "Fuentes distintas con el mismo contenido capturado."], sources: ["Fuentes registradas", "Documentos oficiales y sus últimas capturas disponibles."] } as const;

  return (
    <div className="admin-shell">
      <nav className="admin-nav" aria-label="Administración">
        {sections.map(({ id, label, Icon }) => <button key={id} type="button" className={section === id ? "active" : ""} aria-current={section === id ? "page" : undefined} onClick={() => setSection(id)}><Icon size={14} /> {label}</button>)}
      </nav>
      <section aria-labelledby="admin-section-title">
        <div className="admin-section-heading"><h2 id="admin-section-title">{labels[section][0]}</h2><p>{labels[section][1]}</p></div>
        {section === "batches" && <AdminBatchBoard initialBatches={initialBatches} tasks={initialTasks} />}
        {section === "review" && <AdminReviewBoard initialTasks={initialTasks} />}
        {section === "runs" && (overview.runs.length ? <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Adaptador</th><th>Estado</th><th>Inicio</th><th>Hallazgos</th><th>Candidatos</th><th>Capturas</th></tr></thead><tbody>{overview.runs.map((run) => <tr key={run.id}><td><strong>{run.adapter}</strong>{run.errorMessage && <small>{run.errorMessage}</small>}</td><td><span className="tag">{run.status}</span></td><td>{formatDate(run.startedAt)}</td><td>{run.discoveredCount}</td><td>{run.candidateCount}</td><td>{run.snapshotCount}</td></tr>)}</tbody></table></div> : <Empty text="Aún no hay ejecuciones registradas. La lista se llenará cuando el worker ejecute una fuente." />)}
        {section === "duplicates" && (overview.duplicates.length ? <div className="admin-list">{overview.duplicates.map((item) => <article className="review-card" key={item.candidateKey}><span className="tag">{item.count} coincidencias</span><h3>{item.titles[0]}</h3><p>Huella de contenido: <code>{item.candidateKey}</code></p><div className="card-meta"><span>Detectado {formatDate(item.detectedAt)}</span><span>{item.titles.length} fuentes</span></div></article>)}</div> : <Empty text="No hay fuentes duplicadas. Esta comprobación compara la huella de contenido de las capturas." />)}
        {section === "sources" && <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Fuente</th><th>Estado</th><th>Tipo</th><th>Última captura</th><th>Versiones</th></tr></thead><tbody>{overview.sources.map((source) => <tr key={source.id}><td><a href={source.url} target="_blank" rel="noreferrer"><strong>{source.title}</strong></a><small>{source.publisher}</small></td><td><span className="tag">{source.enabled ? "activa" : "desactivada"} · nivel {source.trustTier}</span></td><td>{source.type}</td><td>{formatDate(source.lastRetrievedAt)}</td><td>{source.snapshotCount}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  );
}

function Empty({ text }: { text: string }) { return <div className="notice">{text}</div>; }
