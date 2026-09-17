import Link from "next/link";
import { CalendarClock, ChevronRight } from "lucide-react";
import { dataset, getSource } from "@/lib/data";

export default function ChangesPage() {
  return (
    <div className="narrow">
      <header className="page-hero">
        <div className="crumbs"><Link href="/">Inicio</Link><ChevronRight size={13} /><span>Cambios</span></div>
        <span className="eyebrow"><CalendarClock size={14} /> Historial institucional</span>
        <h1 className="page-title">Lo que cambió, cuándo y con qué evidencia.</h1>
        <p className="page-intro">Nombramientos, reformas y transformaciones detectadas en las fuentes oficiales.</p>
      </header>
      <div className="timeline">
        {dataset.changes.map((change) => {
          const source = getSource(change.sourceId);
          return (
            <div className="timeline-item" key={change.id}>
              <span className="timeline-dot"><CalendarClock size={17} /></span>
              <div className="timeline-content">
                <time>{change.date} · {change.type}</time>
                <h3>{change.title}</h3><p>{change.description}</p>
                {source && <Link href={`/fuentes/${source.id}`} className="eyebrow" style={{ marginTop: ".6rem" }}>{source.publisher} →</Link>}
              </div>
            </div>
          );
        })}
      </div>
      <div className="section-sm" />
    </div>
  );
}
