"use client";
/* eslint-disable @next/next/no-img-element -- official portrait hosts are dynamic and reviewed before publication */

import Link from "next/link";
import { ArrowDownLeft, ArrowUpRight, BookOpen, ChevronRight, ExternalLink, Focus, UserRound, X } from "lucide-react";
import type { NodeContextResponse, PowerMapNode } from "@mapa/contracts";
import { formatDate, formatStartDate, hrefForNode } from "@/lib/data";
import styles from "./power-map.module.css";

export function NodeSelectionPanel({
  node,
  context,
  loading,
  nodes,
  onExplore,
  onClose
}: {
  node: PowerMapNode | null;
  context: NodeContextResponse | null;
  loading: boolean;
  nodes: PowerMapNode[];
  onExplore: (node: PowerMapNode) => void;
  onClose: () => void;
}) {
  if (!node) {
    return (
      <aside className={styles.detailPanel} aria-label="Detalle del mapa">
        <div className={styles.emptyDetail}>
          <span className={styles.emptyIcon}><Focus size={22} /></span>
          <h2>Explora el poder público</h2>
          <p>Selecciona una institución, cargo o persona para consultar su lugar en el Estado, sus relaciones y las fuentes que lo sustentan.</p>
          <div className={styles.articleNote}><strong>Artículo 49</strong><span>El Supremo Poder de la Federación se divide para su ejercicio en Legislativo, Ejecutivo y Judicial.</span></div>
        </div>
      </aside>
    );
  }

  const details = context?.node ?? node;
  const occupancy = details.occupancy ?? context?.occupancies[0] ?? null;
  const portrait = details.portrait ?? occupancy?.portrait ?? null;
  const relationNodes = new Map(nodes.map((item) => [item.id, item]));

  return (
    <aside className={`${styles.detailPanel} ${styles.detailPanelSelected}`} aria-live="polite" aria-label={`Detalle de ${details.label}`}>
      <button type="button" className={styles.closeDetail} onClick={onClose} aria-label="Cerrar detalle"><X size={17} /></button>
      <header className={styles.detailHeader}>
        <span className={styles.detailType}>{typeLabel(details)}</span>
        <div className={styles.identityRow}>
          {portrait ? (
            <img src={portrait.url} alt={portrait.alt} className={styles.portrait} onError={(event) => { event.currentTarget.hidden = true; }} />
          ) : details.kind === "person" ? (
            <span className={styles.portraitFallback} role="img" aria-label="Retrato oficial no disponible"><UserRound size={25} /></span>
          ) : null}
          <div>
            <h2>{details.label}</h2>
            {details.currentRole && <p className={styles.currentRole}>{details.currentRole}</p>}
          </div>
        </div>
        <p>{details.description}</p>
      </header>

      <div className={styles.factGrid}>
        <div><span>Poder o categoría</span><strong>{branchLabel(details.branch)}</strong></div>
        <div><span>Vigencia</span><strong>{details.validTo ? `Hasta ${formatDate(details.validTo)}` : `Desde ${formatStartDate(details.validFrom)}`}</strong></div>
        <div><span>Relaciones</span><strong>{details.counts.relationships}</strong></div>
        <div><span>Estado del cargo</span><strong>{occupancyLabel(details, occupancy?.status)}</strong></div>
      </div>

      {occupancy && details.kind !== "person" && (
        <section className={styles.panelSection}>
          <h3>Titular registrado</h3>
          <div className={styles.occupancyCard}>
            {occupancy.portrait ? <img src={occupancy.portrait.url} alt={occupancy.portrait.alt} /> : <span><UserRound size={18} /></span>}
            <div><strong>{occupancy.personLabel ?? "Cargo vacante"}</strong><small>{occupancy.positionLabel}</small></div>
          </div>
        </section>
      )}

      {context && context.occupancies.length > 1 && details.kind === "organization" && (
        <section className={styles.panelSection}>
          <h3>Integrantes o titulares publicados</h3>
          <div className={styles.relationList}>
            {context.occupancies.map((item) => (
              <div className={styles.occupancyCard} key={item.id}>
                {item.portrait ? <img src={item.portrait.url} alt={item.portrait.alt} /> : <span><UserRound size={18} /></span>}
                <div><strong>{item.personLabel ?? "Vacante confirmada"}</strong><small>{item.positionLabel}</small></div>
              </div>
            ))}
          </div>
        </section>
      )}

      {details.expandable && (
        <button type="button" className="button button-primary button-small" onClick={() => onExplore(details)}>
          Explorar {details.counts.children} elementos <ChevronRight size={15} />
        </button>
      )}

      <section className={styles.panelSection}>
        <h3>Relaciones documentadas</h3>
        {loading && <p className={styles.loadingText}>Consultando relaciones y evidencia…</p>}
        {!loading && !context?.relationships.length && <p className={styles.muted}>No hay relaciones publicadas para este corte temporal.</p>}
        <div className={styles.relationList}>
          {context?.relationships.map((relation) => {
            const outgoing = relation.source === details.id;
            const peerId = outgoing ? relation.target : relation.source;
            const peer = relationNodes.get(peerId);
            return (
              <article key={relation.id} className={styles.relationCard}>
                <span className={styles.direction}>{outgoing ? <ArrowUpRight size={14} /> : <ArrowDownLeft size={14} />}{outgoing ? relation.label : `Recibe: ${relation.label}`}</span>
                <strong>{peer?.shortLabel ?? (outgoing ? relation.targetLabel : relation.sourceLabel) ?? peerId}</strong>
                <small>{relation.legalBasis}</small>
                {relation.evidence.map((source) => (
                  <a href={source.url} target="_blank" rel="noreferrer" key={`${relation.id}-${source.sourceId}`}>
                    <BookOpen size={12} /> {source.publisher} · {source.locator}
                  </a>
                ))}
              </article>
            );
          })}
        </div>
      </section>

      {context?.changes.length ? (
        <section className={styles.panelSection}>
          <h3>Historial verificable</h3>
          <div className={styles.relationList}>
            {context.changes.map((change) => (
              <article className={styles.relationCard} key={change.id}>
                <strong>{change.title}</strong>
                <small>{formatDate(change.date)} · {change.description}</small>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {portrait && (
        <a className={styles.portraitCredit} href={portrait.sourceUrl} target="_blank" rel="noreferrer">
          Retrato: {portrait.credit} <ExternalLink size={12} />
        </a>
      )}
      <Link className="button button-secondary button-small" href={hrefForNode(details)}>Abrir ficha completa <ExternalLink size={14} /></Link>
    </aside>
  );
}

function typeLabel(node: PowerMapNode) {
  if (node.category === "branch") return "Poder de la Unión";
  if (node.kind === "person") return "Persona";
  if (node.kind === "position") return "Cargo público";
  return node.category.replaceAll("_", " ");
}

function branchLabel(branch: string) {
  return ({ executive: "Ejecutivo", legislative: "Legislativo", judicial: "Judicial", independent: "Órgano autónomo", state: "Estado mexicano" } as Record<string, string>)[branch] ?? branch;
}

function occupancyLabel(node: PowerMapNode, status?: string) {
  if (status === "acting") return "En suplencia";
  if (status === "vacant") return "Vacante confirmada";
  if (status === "confirmed") return "Titular confirmado";
  if (node.kind === "position") return "Titular no registrado";
  return "No aplica";
}
