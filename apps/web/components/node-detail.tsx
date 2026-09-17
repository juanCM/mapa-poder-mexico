import Link from "next/link";
import { ArrowRight, BookOpen, CalendarRange, ExternalLink } from "lucide-react";
import type { GraphNode } from "@mapa/contracts";
import {
  formatDate,
  getNodeById,
  relationshipsForNode,
  sourcesForNode
} from "@/lib/data";

export function NodeDetail({ node }: { node: GraphNode }) {
  const relations = relationshipsForNode(node.id);
  const sources = sourcesForNode(node);
  return (
    <>
      <header className="page-hero">
        <div className="crumbs"><Link href="/">Inicio</Link><span>›</span><Link href="/mapa">Mapa</Link><span>›</span><span>{node.shortLabel}</span></div>
        <span className="eyebrow">{node.kind === "person" ? "Persona" : node.category.replaceAll("_", " ")}</span>
        <h1 className="detail-title">{node.label}</h1>
        <p className="detail-summary">{node.description}</p>
      </header>
      <div className="detail-grid">
        <article>
          <div className="fact-list">
            <div className="fact"><small>Ámbito</small><strong>{node.jurisdiction}</strong></div>
            <div className="fact"><small>Poder o categoría</small><strong>{branchLabel(node.branch)}</strong></div>
            <div className="fact"><small>Vigente desde</small><strong>{formatDate(node.validFrom)}</strong></div>
            <div className="fact"><small>Estado</small><strong>{node.validTo ? `Terminó ${formatDate(node.validTo)}` : "Vigente"}</strong></div>
          </div>

          <div className="section-heading" style={{ marginTop: "3rem" }}>
            <div><span className="eyebrow">Conexiones documentadas</span><h2>¿Cómo se relaciona?</h2></div>
          </div>
          <div className="relation-list">
            {relations.map((relation) => {
              const outgoing = relation.source === node.id;
              const peer = getNodeById(outgoing ? relation.target : relation.source);
              return (
                <Link href={`/relaciones/${relation.id}`} className="relation-item" key={relation.id}>
                  <span className="verb">{outgoing ? relation.label.toUpperCase() : `RECIBE: ${relation.label.toUpperCase()}`}</span>
                  <span><strong>{peer?.shortLabel}</strong><br /><small>{relation.legalBasis}</small></span>
                  <ArrowRight size={16} />
                </Link>
              );
            })}
          </div>

          {node.kind === "person" && (
            <section className="section-sm">
              <span className="eyebrow"><CalendarRange size={14} /> Trayectoria registrada</span>
              <div className="timeline">
                {relations.filter((relation) => relation.type === "HOLDS").map((relation) => (
                  <div className="timeline-item" key={relation.id}>
                    <span className="timeline-dot"><CalendarRange size={17} /></span>
                    <div className="timeline-content"><time>{formatDate(relation.validFrom)}</time><h3>{getNodeById(relation.target)?.label}</h3><p>{relation.description}</p></div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </article>

        <aside className="card aside-card">
          <span className="eyebrow"><BookOpen size={14} /> Evidencia</span>
          <h2>Fuentes oficiales</h2>
          <p>Documentos que sustentan la información mostrada en esta ficha.</p>
          <div className="source-list">
            {sources.map((source) => (
              <Link className="source-link" href={`/fuentes/${source.id}`} key={source.id}>
                <strong>{source.title}</strong><span>{source.publisher} · consultado {source.retrievedAt}</span>
              </Link>
            ))}
          </div>
          <Link className="button button-secondary button-small" href={`/mapa`} style={{ marginTop: "1rem" }}>Ver en el mapa <ExternalLink size={14} /></Link>
        </aside>
      </div>
      <div className="section-sm" />
    </>
  );
}

function branchLabel(branch: string) {
  return ({ state: "Estado", executive: "Ejecutivo", legislative: "Legislativo", judicial: "Judicial", independent: "Autónomo o independiente" } as Record<string, string>)[branch] ?? branch;
}
