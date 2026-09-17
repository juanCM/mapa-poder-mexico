import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink, Fingerprint } from "lucide-react";
import { dataset, getSource } from "@/lib/data";

export function generateStaticParams() { return dataset.sources.map((source) => ({ id: source.id })); }

export default async function SourcePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const source = getSource(id);
  if (!source) notFound();
  const relations = dataset.edges.filter((edge) => edge.evidence.some((evidence) => evidence.sourceId === id));
  return (
    <div className="narrow">
      <header className="page-hero">
        <div className="crumbs"><Link href="/">Inicio</Link><span>›</span><span>Fuente</span></div>
        <span className="eyebrow">{source.type.replaceAll("_", " ")}</span>
        <h1 className="detail-title">{source.title}</h1>
        <p className="detail-summary">{source.description}</p>
      </header>
      <div className="card">
        <div className="fact-list">
          <div className="fact"><small>Editor</small><strong>{source.publisher}</strong></div>
          <div className="fact"><small>Consultado</small><strong>{source.retrievedAt}</strong></div>
          <div className="fact"><small>Publicación</small><strong>{source.publicationDate ?? "Publicación continua"}</strong></div>
          <div className="fact"><small>Integridad</small><strong>{source.contentHash}</strong></div>
        </div>
        <a className="button button-primary" href={source.url} target="_blank" rel="noreferrer">Abrir documento oficial <ExternalLink size={16} /></a>
      </div>
      <section className="section-sm">
        <span className="eyebrow"><Fingerprint size={14} /> Relaciones sustentadas</span>
        <div className="relation-list" style={{ marginTop: "1rem" }}>
          {relations.map((relation) => <Link className="relation-item" href={`/relaciones/${relation.id}`} key={relation.id}><span className="verb">{relation.type}</span><span>{relation.description}</span><ExternalLink size={15} /></Link>)}
        </div>
      </section>
    </div>
  );
}
