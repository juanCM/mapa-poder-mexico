import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenCheck,
  Building2,
  CalendarClock,
  Landmark,
  Network,
  Scale,
  SearchCheck,
  ShieldCheck
} from "lucide-react";
import { SearchBox } from "@/components/search-box";
import { dataset, hrefForNode } from "@/lib/data";

const featured = [
  "poder-ejecutivo-federal",
  "poder-legislativo-federal",
  "poder-judicial-federal"
].map((slug) => dataset.nodes.find((node) => node.slug === slug)!);

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <span className="eyebrow"><BadgeCheck size={15} /> Plataforma pública y verificable</span>
            <h1>Entiende cómo se organiza y <em>ejerce</em> el poder.</h1>
            <p>
              Explora las instituciones del Estado mexicano, las personas que ocupan sus cargos
              y las facultades legales que conectan a cada actor.
            </p>
            <SearchBox nodes={dataset.nodes} />
            <div className="hero-actions">
              <Link className="button button-primary" href="/mapa">Abrir el mapa <ArrowRight size={17} /></Link>
              <Link className="button button-secondary" href="#metodologia">Cómo verificamos los datos</Link>
            </div>
          </div>
          <div className="hero-map" aria-label="Representación del mapa institucional">
            <span className="orbit-line l1" /><span className="orbit-line l2" /><span className="orbit-line l3" /><span className="orbit-line l4" />
            <span className="orbit-node main"><Network size={28} /><br />Estado Mexicano</span>
            <span className="orbit-node a">Poder Ejecutivo</span>
            <span className="orbit-node b">Poder Legislativo</span>
            <span className="orbit-node c">Poder Judicial</span>
            <span className="orbit-node d">Órganos autónomos</span>
          </div>
        </div>
      </section>

      <section className="stats-band" aria-label="Cobertura del prototipo">
        <div className="container stats-grid">
          <div className="stat"><strong>{dataset.nodes.filter((node) => node.kind === "organization").length}</strong><span>instituciones representativas</span></div>
          <div className="stat"><strong>{dataset.edges.length}</strong><span>relaciones documentadas</span></div>
          <div className="stat"><strong>{dataset.sources.length}</strong><span>fuentes oficiales</span></div>
          <div className="stat"><strong>100%</strong><span>de aristas con evidencia</span></div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-heading">
            <div><span className="eyebrow">Tres puertas de entrada</span><h2>Explora el Estado federal</h2></div>
            <p>Navega por estructura para entender el organigrama o cambia al mapa de poder para ver nombramientos, controles y facultades.</p>
          </div>
          <div className="card-grid">
            {featured.map((node, index) => {
              const icons = [Building2, Landmark, Scale];
              const Icon = icons[index];
              const count = dataset.edges.filter((edge) => edge.source === node.id || edge.target === node.id).length;
              return (
                <Link className="card" href={hrefForNode(node)} key={node.id}>
                  <span className="card-icon"><Icon size={21} /></span>
                  <span className="tag">{node.branch}</span>
                  <h3>{node.label}</h3>
                  <p>{node.description}</p>
                  <span className="card-meta"><span>{count} conexiones directas</span><ArrowRight size={16} /></span>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <section className="section dark-section" id="metodologia">
        <div className="container">
          <div className="section-heading">
            <div><span className="eyebrow">Metodología</span><h2>No mostramos una línea sin explicar por qué existe.</h2></div>
            <p>Cada dato publicado conserva su fuente, fragmento aplicable, vigencia y fecha de verificación.</p>
          </div>
          <div className="card-grid">
            <article className="card"><span className="card-icon"><SearchCheck size={21} /></span><h3>1. Detectamos</h3><p>Los adaptadores vigilan directorios, normas y publicaciones oficiales y conservan una copia verificable.</p></article>
            <article className="card"><span className="card-icon"><ShieldCheck size={21} /></span><h3>2. Revisamos</h3><p>La automatización genera candidatos. Una revisión humana confirma identidad, alcance y vigencia.</p></article>
            <article className="card"><span className="card-icon"><BookOpenCheck size={21} /></span><h3>3. Publicamos evidencia</h3><p>La relación visible enlaza al artículo, directorio o documento oficial que la sustenta.</p></article>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-heading">
            <div><span className="eyebrow"><CalendarClock size={15} /> Actividad reciente</span><h2>El Estado también cambia</h2></div>
            <Link className="button button-secondary" href="/cambios">Ver todos los cambios <ArrowRight size={16} /></Link>
          </div>
          <div className="card-grid">
            {dataset.changes.map((change) => (
              <article className="card" key={change.id}>
                <span className="tag">{change.type}</span>
                <h3>{change.title}</h3>
                <p>{change.description}</p>
                <span className="card-meta"><time>{change.date}</time><span>Fuente oficial</span></span>
              </article>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
