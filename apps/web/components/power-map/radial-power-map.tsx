"use client";

import { Minus, Plus, RotateCcw, UsersRound } from "lucide-react";
import { useMemo, useRef, useState, type CSSProperties } from "react";
import type { PowerMapNode, PowerMapRelationship } from "@mapa/contracts";
import { EntityIcon, isFederalPresidency } from "./entity-icon";
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
  const contextEdges = root
    ? relationships.filter((edge) => !selectedEdges.some((selectedEdge) => selectedEdge.id === edge.id))
    : [];
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

          {(root ? [205, 340, 405] : [205, 286, 356]).map((radius) => <circle key={radius} cx={MAP_CENTER} cy={MAP_CENTER} r={radius} className={styles.ring} />)}

          <g className={styles.relationships}>
            {contextEdges.map((edge) => {
              const source = byId.get(edge.source);
              const target = byId.get(edge.target);
              if (!source || !target) return null;
              return (
                <path
                  key={`context-${edge.id}`}
                  d={relationshipPath(source, target)}
                  className={`${styles.relationship} ${styles.relationshipContext} ${root && selectedId === root ? styles.relationshipContextRoot : ""} ${styles[`relationship_${edge.relationshipClass}`]}`}
                />
              );
            })}
            {selectedEdges.map((edge) => {
              const source = byId.get(edge.source);
              const target = byId.get(edge.target);
              if (!source || !target) return null;
              return (
                <path
                  key={edge.id}
                  d={relationshipPath(source, target)}
                  className={`${styles.relationship} ${styles.relationshipActive} ${styles[`relationship_${edge.relationshipClass}`]}`}
                  markerEnd="url(#power-map-arrow)"
                />
              );
            })}
          </g>

          {visibleNodes.map((node, index) => (
            <MapNode
              key={node.id}
              node={node}
              index={index}
              selected={node.id === selectedId}
              dimmed={Boolean(selectedId && !(root && selectedId === root) && node.id !== selectedId && !connected.has(node.id))}
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
              <UsersRound x={MAP_CENTER - 13} y={MAP_CENTER - 49} width={26} height={26} className={styles.sovereigntyIcon} />
              <text x={MAP_CENTER} y={MAP_CENTER - 3} textAnchor="middle">Pueblo de México</text>
              <text x={MAP_CENTER} y={MAP_CENTER + 24} textAnchor="middle" className={styles.sovereigntyArticle}>La soberanía reside en el pueblo</text>
              <text x={MAP_CENTER} y={MAP_CENTER + 45} textAnchor="middle" className={styles.sovereigntyArticle}>CPEUM · artículo 39</text>
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
      {(root || selectedEdges.length > 0) && (
        <div className={styles.relationshipLegend} aria-label="Leyenda de relaciones">
          <strong>{selectedEdges.length ? `${selectedEdges.length} relaciones directas` : "Relaciones visibles"}</strong>
          <span><i className={styles.legendStructure} />Estructura</span>
          <span><i className={styles.legendPower} />Autoridad</span>
          <span><i className={styles.legendAccountability} />Control</span>
          <span><i className={styles.legendTenure} />Ocupación</span>
        </div>
      )}
      <p className="sr-only" aria-live="polite">{selectedId ? `Nodo seleccionado: ${byId.get(selectedId)?.label ?? selectedId}` : "Ningún nodo seleccionado"}</p>
    </div>
  );
}

function MapNode({
  node,
  index,
  selected,
  dimmed,
  onSelect,
  onHover
}: {
  node: PositionedNode;
  index: number;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
  onHover: (node: PositionedNode | null) => void;
}) {
  const person = node.kind === "person";
  const position = node.kind === "position";
  const branch = node.category === "branch";
  const presidential = isFederalPresidency(node);
  const size = presidential ? 27 : branch ? 29 : node.expandable ? 23 : person ? 16 : position ? 15 : 16;
  const labelVisible = presidential || (!node.compact && (branch || node.expandable || selected || person || node.radius < 220));
  return (
    <g
      data-map-node
      role="button"
      tabIndex={0}
      aria-label={`${node.label}. ${nodeTypeLabel(node)}${node.expandable ? `. Contiene ${node.counts.children} elementos` : ""}`}
      aria-pressed={selected}
      className={`${styles.node} ${styles[`node_${node.kind}`]} ${branch ? styles.node_branch : ""} ${presidential ? styles.nodePresidency : ""} ${selected ? styles.node_selected : ""} ${dimmed ? styles.node_dimmed : ""}`}
      transform={`translate(${node.x} ${node.y})`}
      style={{ "--node-delay": `${Math.min(index * 22, 420)}ms` } as CSSProperties}
      onClick={(event) => { event.stopPropagation(); onSelect(); }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(); }
      }}
      onMouseEnter={() => onHover(node)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(node)}
      onBlur={() => onHover(null)}
    >
      <g className={styles.nodeGlyph}>
        {presidential && <circle cx="0" cy="0" r={size + 9} className={styles.presidentialHalo} />}
        {node.portrait ? (
          <image href={node.portrait.url} x={-size} y={-size} width={size * 2} height={size * 2} preserveAspectRatio="xMidYMid slice" clipPath={`url(#portrait-${node.id})`} />
        ) : (
          <circle cx="0" cy="0" r={size} />
        )}
        {!node.portrait && <EntityIcon node={node} x={-size * .43} y={-size * .58} width={size * .86} height={size * .86} className={styles.nodeIcon} strokeWidth={1.8} />}
        {node.expandable && <text className={styles.nodeCount} y={size * .62} textAnchor="middle">{node.counts.children}</text>}
      </g>
      {labelVisible && <text className={styles.nodeLabel} y={size + 17} textAnchor="middle">{shorten(node.shortLabel, 24)}</text>}
    </g>
  );
}

function relationshipPath(source: PositionedNode, target: PositionedNode) {
  const middleX = (source.x + target.x) / 2;
  const middleY = (source.y + target.y) / 2;
  const towardCenter = .18;
  const controlX = middleX + (MAP_CENTER - middleX) * towardCenter;
  const controlY = middleY + (MAP_CENTER - middleY) * towardCenter;
  return `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`;
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
