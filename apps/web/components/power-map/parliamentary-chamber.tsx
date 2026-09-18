"use client";

import { useMemo, useState, type CSSProperties } from "react";
import type { PowerMapNode } from "@mapa/contracts";
import { Armchair, Info } from "lucide-react";
import { layoutParliamentarySeats } from "./parliamentary-chamber-layout";
import styles from "./power-map.module.css";

export function ParliamentaryChamber({
  nodes,
  root,
  selectedId,
  onSelect
}: {
  nodes: PowerMapNode[];
  root: string | null;
  selectedId: string | null;
  onSelect: (node: PowerMapNode) => void;
}) {
  const [hovered, setHovered] = useState<PowerMapNode | null>(null);
  const { seats, groups } = useMemo(() => layoutParliamentarySeats(nodes), [nodes]);
  const chamber = nodes.find((node) => node.id === root);

  return (
    <div className={`${styles.canvasShell} ${styles.chamberShell}`}>
      <div className={styles.chamberHeading}>
        <span><Armchair size={16} /> Composición parlamentaria</span>
        <strong>{chamber?.shortLabel ?? chamber?.label ?? "Cámara legislativa"}</strong>
        <small>{seats.length ? `${seats.length} escaños publicados para este corte` : "Sin escaños publicados en este conjunto de datos"}</small>
      </div>
      {seats.length ? (
        <>
          <svg className={`${styles.mapSvg} ${styles.chamberSvg}`} viewBox="0 0 920 760" role="img" aria-label={`Distribución de ${seats.length} escaños por grupo parlamentario`}>
            <title>Distribución por grupo parlamentario</title>
            <desc>Cada círculo representa un escaño publicado. Los colores se agrupan por grupo parlamentario registrado.</desc>
            <path d="M 150 665 A 310 310 0 0 1 770 665" className={styles.chamberGuide} />
            {seats.map((seat, index) => (
              <circle
                data-parliamentary-seat
                role="button"
                tabIndex={0}
                aria-label={`${seat.node.label}. ${seat.group}${seat.node.occupancy?.personLabel ? `. ${seat.node.occupancy.personLabel}` : ""}`}
                aria-pressed={seat.node.id === selectedId}
                key={seat.node.id}
                cx={seat.x}
                cy={seat.y}
                r={seat.node.id === selectedId ? seat.radius + 2 : seat.radius}
                fill={seat.color}
                className={`${styles.chamberSeat} ${seat.node.id === selectedId ? styles.chamberSeatSelected : ""}`}
                style={{ "--node-delay": `${Math.min(index * 4, 420)}ms` } as CSSProperties}
                onClick={() => onSelect(seat.node)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(seat.node);
                  }
                }}
                onMouseEnter={() => setHovered(seat.node)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(seat.node)}
                onBlur={() => setHovered(null)}
              />
            ))}
          </svg>
          <div className={styles.partyLegend} aria-label="Grupos parlamentarios">
            {groups.map((group) => (
              <span key={group.label}><i style={{ background: group.color }} />{group.label}<strong>{group.count}</strong></span>
            ))}
          </div>
          {hovered && (
            <div className={styles.tooltip} role="tooltip">
              <span>{typeof hovered.metadata.parliamentaryGroup === "string" ? hovered.metadata.parliamentaryGroup : "Sin grupo registrado"}</span>
              <strong>{hovered.occupancy?.personLabel ?? hovered.label}</strong>
              <small>{hovered.occupancy?.personLabel ? hovered.label : "Titular no registrado"}</small>
            </div>
          )}
        </>
      ) : (
        <div className={styles.chamberEmpty}>
          <Info size={24} />
          <strong>La vista está preparada para datos legislativos completos.</strong>
          <p>Cuando el lote oficial de escaños esté publicado, aquí se mostrará la distribución por grupo parlamentario. Puedes consultar mientras tanto la vista de estructura.</p>
        </div>
      )}
    </div>
  );
}
