"use client";

import { Minus, Plus, RotateCcw } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import type { PowerMapNode, PowerMapRelationship } from "@mapa/contracts";
import styles from "./power-map.module.css";
import {
  annularSector,
  labelArc,
  MAP_CENTER,
  MAP_SIZE,
  positionNodes,
  sectors,
  type PositionedNode,
  uniqueNodes
} from "./power-map-layout";

type Camera = { x: number; y: number; scale: number };

export function RadialPowerMap({
  nodes,
  relationships,
  root,
  selectedId,
  enabledBranches,
  onSelect
}: {
  nodes: PowerMapNode[];
  relationships: PowerMapRelationship[];
  root: string | null;
  selectedId: string | null;
  enabledBranches: Set<string>;
  onSelect: (node: PowerMapNode) => void;
}) {
  const [camera, setCamera] = useState<Camera>({ x: 0, y: 0, scale: 1 });
  const [hovered, setHovered] = useState<PositionedNode | null>(null);
  const drag = useRef<{ x: number; y: number; cameraX: number; cameraY: number } | null>(null);
  const positioned = useMemo(
    () => positionNodes(uniqueNodes(nodes).filter((node) => enabledBranches.has(node.branch) || node.branch === "state" || node.slug === "ciudadania"), root),
    [nodes, root, enabledBranches]
  );
  const visibleNodes = useMemo(
    () => uniqueNodes(positioned.filter((node) => root || node.branch !== "state")),
    [positioned, root]
  );
  const byId = useMemo(() => new Map(positioned.map((node) => [node.id, node])), [positioned]);
  const connected = useMemo(() => {
    if (!selectedId) return new Set<string>();
    return new Set(relationships.filter((edge) => edge.source === selectedId || edge.target === selectedId).flatMap((edge) => [edge.source, edge.target]));
  }, [relationships, selectedId]);
  const selectedEdges = [...new Map(
    relationships
      .filter((edge) => selectedId && (edge.source === selectedId || edge.target === selectedId))
      .map((edge) => [edge.id, edge])
  ).values()];
  const sovereigntyNode = positioned.find((node) => node.slug === "ciudadania") ?? positioned.find((node) => node.branch === "state");

  function zoom(delta: number) {
    setCamera((current) => ({ ...current, scale: Math.min(2.4, Math.max(0.65, current.scale + delta)) }));
  }

  function reset() {
    setCamera({ x: 0, y: 0, scale: 1 });
  }

  return (
    <div className={styles.canvasShell}>
      <div className={styles.zoomControls} aria-label="Controles del mapa">
        <button type="button" onClick={() => zoom(0.2)} aria-label="Acercar"><Plus size={16} /></button>
        <button type="button" onClick={() => zoom(-0.2)} aria-label="Alejar"><Minus size={16} /></button>
        <button type="button" onClick={reset} aria-label="Recentrar"><RotateCcw size={15} /></button>
      </div>
      <svg
        className={styles.mapSvg}
        viewBox={`0 0 ${MAP_SIZE} ${MAP_SIZE}`}
        role="img"
        aria-label={root ? "Detalle radial del grupo seleccionado" : "Mapa radial de los poderes del Estado mexicano"}
        onWheel={(event) => {
          event.preventDefault();
          zoom(event.deltaY > 0 ? -0.1 : 0.1);
        }}
        onPointerDown={(event) => {
          if ((event.target as Element).closest?.("[data-map-node]")) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          drag.current = { x: event.clientX, y: event.clientY, cameraX: camera.x, cameraY: camera.y };
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          setCamera((current) => ({
            ...current,
            x: drag.current!.cameraX + (event.clientX - drag.current!.x) / current.scale,
            y: drag.current!.cameraY + (event.clientY - drag.current!.y) / current.scale
          }));
        }}
        onPointerUp={() => { drag.current = null; }}
        onPointerCancel={() => { drag.current = null; }}
      >
        <title>Mapa radial del poder público federal en México</title>
        <desc>Los tres Poderes de la Unión y los órganos autónomos se organizan alrededor del Pueblo de México.</desc>
        <defs>
          <marker id="power-map-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L7,3 z" className={styles.arrowHead} />
          </marker>
          {sectors.map((sector) => <path key={sector.branch} id={`sector-label-${sector.branch}`} d={labelArc(sector.start + 5, sector.end - 5, 405)} />)}
          {visibleNodes.filter((node) => node.portrait).map((node) => (
            <clipPath id={`portrait-${node.id}`} key={node.id} clipPathUnits="objectBoundingBox"><circle cx=".5" cy=".5" r=".5" /></clipPath>
          ))}
        </defs>

        <g transform={`translate(${camera.x} ${camera.y}) translate(${MAP_CENTER} ${MAP_CENTER}) scale(${camera.scale}) translate(${-MAP_CENTER} ${-MAP_CENTER})`}>
          {!root && sectors.map((sector) => (
            <g key={sector.branch} className={styles.sector} data-branch={sector.branch}>
              <path d={annularSector(sector.start, sector.end, 126, 416)} style={{ fill: sector.color }} />
              <text className={styles.sectorLabel}>
                <textPath href={`#sector-label-${sector.branch}`} startOffset="50%" textAnchor="middle">{sector.label}</textPath>
              </text>
            </g>
          ))}

          {[205, 286, 356].map((radius) => <circle key={radius} cx={MAP_CENTER} cy={MAP_CENTER} r={radius} className={styles.ring} />)}

          <g className={styles.relationships}>
            {selectedEdges.map((edge) => {
              const source = byId.get(edge.source);
              const target = byId.get(edge.target);
              if (!source || !target) return null;
              const controlX = (source.x + target.x + MAP_CENTER) / 3;
              const controlY = (source.y + target.y + MAP_CENTER) / 3;
              return (
                <path
                  key={edge.id}
                  d={`M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`}
                  className={`${styles.relationship} ${styles[`relationship_${edge.relationshipClass}`]}`}
                  markerEnd="url(#power-map-arrow)"
                />
              );
            })}
          </g>

          {visibleNodes.map((node) => (
            <MapNode
              key={node.id}
              node={node}
              selected={node.id === selectedId}
              dimmed={Boolean(selectedId && node.id !== selectedId && !connected.has(node.id))}
              onSelect={() => onSelect(node)}
              onHover={setHovered}
            />
          ))}

          {!root && sovereigntyNode && (
            <g
              data-map-node
              role="button"
              tabIndex={0}
              aria-label="Pueblo de México. Fuente de la soberanía nacional, artículo 39 constitucional"
              aria-pressed={sovereigntyNode.id === selectedId}
              className={`${styles.sovereignty} ${sovereigntyNode.id === selectedId ? styles.node_selected : ""}`}
              onClick={() => onSelect(sovereigntyNode)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(sovereigntyNode);
                }
              }}
            >
              <circle cx={MAP_CENTER} cy={MAP_CENTER} r="106" />
              <text x={MAP_CENTER} y={MAP_CENTER - 10} textAnchor="middle">Pueblo de México</text>
              <text x={MAP_CENTER} y={MAP_CENTER + 18} textAnchor="middle" className={styles.sovereigntyArticle}>La soberanía reside en el pueblo</text>
              <text x={MAP_CENTER} y={MAP_CENTER + 39} textAnchor="middle" className={styles.sovereigntyArticle}>CPEUM · artículo 39</text>
            </g>
          )}
        </g>
      </svg>

      {hovered && (
        <div className={styles.tooltip} role="tooltip">
          <span>{nodeTypeLabel(hovered)}</span>
          <strong>{hovered.label}</strong>
          <small>{hovered.occupancy?.personLabel ?? (hovered.counts.children ? `${hovered.counts.children} elementos` : "Selecciona para consultar relaciones")}</small>
        </div>
      )}
      <p className="sr-only" aria-live="polite">{selectedId ? `Nodo seleccionado: ${byId.get(selectedId)?.label ?? selectedId}` : "Ningún nodo seleccionado"}</p>
    </div>
  );
}

function MapNode({
  node,
  selected,
  dimmed,
  onSelect,
  onHover
}: {
  node: PositionedNode;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
  onHover: (node: PositionedNode | null) => void;
}) {
  const person = node.kind === "person";
  const position = node.kind === "position";
  const branch = node.category === "branch";
  const size = branch ? 24 : node.expandable ? 18 : person ? 13 : position ? 12 : 10;
  const labelVisible = !node.compact && (branch || node.expandable || selected || node.radius < 220);
  return (
    <g
      data-map-node
      role="button"
      tabIndex={0}
      aria-label={`${node.label}. ${nodeTypeLabel(node)}${node.expandable ? `. Contiene ${node.counts.children} elementos` : ""}`}
      aria-pressed={selected}
      className={`${styles.node} ${styles[`node_${node.kind}`]} ${branch ? styles.node_branch : ""} ${selected ? styles.node_selected : ""} ${dimmed ? styles.node_dimmed : ""}`}
      transform={`translate(${node.x} ${node.y})`}
      onClick={(event) => { event.stopPropagation(); onSelect(); }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(); }
      }}
      onMouseEnter={() => onHover(node)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(node)}
      onBlur={() => onHover(null)}
    >
      {node.portrait ? (
        <image href={node.portrait.url} x={-size} y={-size} width={size * 2} height={size * 2} preserveAspectRatio="xMidYMid slice" clipPath={`url(#portrait-${node.id})`} />
      ) : position ? (
        <><rect x={-size} y={-size} width={size * 2} height={size * 2} rx="5" /><circle cx={size * 0.65} cy={-size * 0.65} r="4" /></>
      ) : (
        <circle cx="0" cy="0" r={size} />
      )}
      {node.expandable && <text className={styles.nodeCount} y="4" textAnchor="middle">{node.counts.children}</text>}
      {labelVisible && <text className={styles.nodeLabel} y={size + 17} textAnchor="middle">{shorten(node.shortLabel, 24)}</text>}
    </g>
  );
}

function shorten(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function nodeTypeLabel(node: PowerMapNode) {
  if (node.category === "branch") return "Poder constitucional";
  if (node.kind === "person") return "Persona servidora pública";
  if (node.kind === "position") return "Cargo público";
  if (node.category === "navigation_group" || node.category === "administrative_group") return "Agrupación institucional";
  return "Institución";
}
