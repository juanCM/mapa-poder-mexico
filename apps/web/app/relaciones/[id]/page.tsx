import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, BookOpenCheck, CalendarRange, ExternalLink } from "lucide-react";
import { dataset, formatDate, getNodeById, getRelationship, hrefForNode } from "@/lib/data";

export function generateStaticParams() {
  return dataset.edges.map((edge) => ({ id: edge.id }));
}

export default async function RelationshipPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const relation = getRelationship(id);
  if (!relation) notFound();
  const source = getNodeById(relation.source)!;
  const target = getNodeById(relation.target)!;
  return (
    <div className="container">
      <header className="page-hero">
        <div className="crumbs"><Link href="/">Inicio</Link><span>›</span><Link href="/mapa">Mapa</Link><span>›</span><span>Relación</span></div>
        <span className="eyebrow">{relation.type}</span>
        <h1 className="detail-title">{source.shortLabel} <em style={{ color: "var(--coral)" }}>{relation.label}</em> {target.shortLabel}</h1>
        <p className="detail-summary">{relation.description}</p>
      </header>
      <div className="detail-grid">
        <article>
          <div className="card-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <Link className="card" href={hrefForNode(source)}><span className="tag">Actor</span><h3>{source.label}</h3><p>{source.description}</p></Link>
            <Link className="card" href={hrefForNode(target)}><span className="tag">Objetivo</span><h3>{target.label}</h3><p>{target.description}</p></Link>
          </div>
          <div className="section-sm">
            <span className="eyebrow"><CalendarRange size={14} /> Vigencia</span>
            <h2>{formatDate(relation.validFrom)} <ArrowRight size={18} /> {formatDate(relation.validTo)}</h2>
            {relation.condition && <div className="notice"><strong>Condición del ejercicio:</strong> {relation.condition}</div>}
            <h2>Fundamento jurídico</h2>
            <p className="detail-summary">{relation.legalBasis}</p>
          </div>
        </article>
        <aside className="card aside-card">
          <span className="eyebrow"><BookOpenCheck size={14} /> Evidencia primaria</span>
          {relation.evidence.map((evidence) => (
            <div key={evidence.sourceId} style={{ marginTop: "1rem" }}>
              <h3>{evidence.title}</h3>
              <p><strong>{evidence.locator}</strong><br />{evidence.publisher}<br />Consultado {evidence.retrievedAt}</p>
              <a className="button button-primary button-small" href={evidence.url} target="_blank" rel="noreferrer">Abrir fuente <ExternalLink size={14} /></a>
            </div>
          ))}
        </aside>
      </div>
      <div className="section-sm" />
    </div>
  );
}
