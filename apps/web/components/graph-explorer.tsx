"use client";

import Link from "next/link";
import Graph from "graphology";
import type SigmaInstance from "sigma";
import { CalendarDays, ExternalLink, List, Network, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphEdge, GraphMode, GraphNode } from "@mapa/contracts";
import { formatDate, hrefForNode } from "@/lib/data";

const branchColors: Record<string, string> = {
  state: "#142c2b",
  executive: "#e6654b",
  legislative: "#d49d35",
  judicial: "#466f9a",
  independent: "#0d7b70"
};

type Selection = { kind: "node"; node: GraphNode } | { kind: "edge"; edge: GraphEdge };

export function GraphExplorer({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<SigmaInstance | null>(null);
  const [mode, setMode] = useState<GraphMode>("power");
  const [branches, setBranches] = useState(() => new Set(["state", "executive", "legislative", "judicial", "independent"]));
  const [selection, setSelection] = useState<Selection | null>({ kind: "edge", edge: edges.find((edge) => edge.id === "rel-asf-ejecutivo") ?? edges[0] });
  const [showTable, setShowTable] = useState(false);
  const [asOf, setAsOf] = useState("2026-09-17");

  const visibleEdges = useMemo(() => edges.filter((edge) => edge.mode === mode || edge.mode === "both"), [edges, mode]);
  const connectedIds = useMemo(() => new Set(visibleEdges.flatMap((edge) => [edge.source, edge.target])), [visibleEdges]);
  const visibleNodes = useMemo(
    () => nodes.filter((node) => connectedIds.has(node.id) && branches.has(node.branch)),
    [nodes, connectedIds, branches]
  );

  useEffect(() => {
    if (!containerRef.current) return;
    rendererRef.current?.kill();
    let cancelled = false;
    let renderer: SigmaInstance | null = null;

    async function mountGraph() {
      const { default: Sigma } = await import("sigma");
      if (cancelled || !containerRef.current) return;
      const graph = new Graph();
      const allowedIds = new Set(visibleNodes.map((node) => node.id));
      visibleNodes.forEach((node, index) => {
        const angle = (index / Math.max(visibleNodes.length, 1)) * Math.PI * 2;
        const radius = node.slug === "estado-mexicano" ? 0 : 10 + (index % 3) * 2.8;
        graph.addNode(node.id, {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
          size: node.kind === "person" ? 8 : node.category === "branch" ? 16 : 11,
          label: node.shortLabel,
          color: node.kind === "person" ? "#9d4d92" : branchColors[node.branch] ?? "#49615e",
          borderColor: "#fffdf8"
        });
      });
      visibleEdges.forEach((edge) => {
        if (allowedIds.has(edge.source) && allowedIds.has(edge.target) && !graph.hasEdge(edge.id)) {
          graph.addEdgeWithKey(edge.id, edge.source, edge.target, {
            label: edge.label,
            color: edge.type === "PART_OF" ? "#a8b0aa" : "#e6654b",
            size: edge.type === "PART_OF" ? 1.2 : 2,
            type: "arrow"
          });
        }
      });
      renderer = new Sigma(graph, containerRef.current, {
        renderEdgeLabels: true,
        labelDensity: 0.1,
        labelGridCellSize: 90,
        labelRenderedSizeThreshold: 8,
        defaultEdgeType: "arrow",
        minCameraRatio: 0.2,
        maxCameraRatio: 3
      });
      renderer.on("clickNode", ({ node }) => {
        const selected = nodes.find((item) => item.id === node);
        if (selected) setSelection({ kind: "node", node: selected });
      });
      renderer.on("clickEdge", ({ edge }) => {
        const selected = edges.find((item) => item.id === edge);
        if (selected) setSelection({ kind: "edge", edge: selected });
      });
      rendererRef.current = renderer;
    }

    void mountGraph();
    return () => {
      cancelled = true;
      renderer?.kill();
    };
  }, [visibleNodes, visibleEdges, nodes, edges]);

  function toggleBranch(branch: string) {
    setBranches((current) => {
      const next = new Set(current);
      if (next.has(branch)) next.delete(branch); else next.add(branch);
      return next;
    });
  }

  return (
    <>
      <div className="map-layout">
        <aside className="map-sidebar" aria-label="Filtros del mapa">
          <div className="control-group">
            <span className="control-title">Vista</span>
            <div className="segmented">
              <button className={mode === "organization" ? "active" : ""} onClick={() => setMode("organization")}>Organigrama</button>
              <button className={mode === "power" ? "active" : ""} onClick={() => setMode("power")}>Poder</button>
            </div>
          </div>
          <div className="control-group">
            <label htmlFor="as-of"><CalendarDays size={13} /> Fecha de consulta</label>
            <input id="as-of" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} style={{ width: "100%" }} />
          </div>
          <div className="control-group">
            <span className="control-title">Poder o categoría</span>
            <div className="filter-list">
              {[
                ["state", "Estado", branchColors.state],
                ["executive", "Ejecutivo", branchColors.executive],
                ["legislative", "Legislativo", branchColors.legislative],
                ["judicial", "Judicial", branchColors.judicial],
                ["independent", "Autónomos", branchColors.independent]
              ].map(([value, label, color]) => (
                <label className="filter-row" key={value}>
                  <input type="checkbox" checked={branches.has(value)} onChange={() => toggleBranch(value)} />
                  <span className="filter-dot" style={{ background: color }} /> {label}
                </label>
              ))}
            </div>
          </div>
          <button className="button button-secondary button-small" onClick={() => rendererRef.current?.getCamera().animatedReset()}>
            <RotateCcw size={14} /> Recentrar
          </button>
          <button className="button button-secondary button-small table-toggle" onClick={() => setShowTable((value) => !value)} aria-expanded={showTable}>
            <List size={14} /> {showTable ? "Ocultar tabla" : "Vista en tabla"}
          </button>
        </aside>

        <div className="map-canvas-wrap">
          <div ref={containerRef} className="map-canvas" role="img" aria-label={`Mapa de ${mode === "power" ? "facultades" : "estructura"} del Gobierno Federal`} />
          <span className="map-watermark"><Network size={12} /> {visibleNodes.length} nodos · {visibleEdges.length} relaciones · corte {asOf}</span>
        </div>

        <aside className="map-detail" aria-live="polite">
          {!selection && <p>Selecciona un nodo o una conexión para consultar sus detalles.</p>}
          {selection?.kind === "node" && (
            <>
              <span className="tag">{selection.node.kind}</span>
              <h2>{selection.node.label}</h2>
              <p>{selection.node.description}</p>
              <div className="fact"><small>Vigencia</small><strong>Desde {formatDate(selection.node.validFrom)}</strong></div>
              <Link className="button button-primary button-small" href={hrefForNode(selection.node)}>Abrir ficha <ExternalLink size={14} /></Link>
            </>
          )}
          {selection?.kind === "edge" && (
            <>
              <span className="tag">{selection.edge.type}</span>
              <h2>{getNodeLabel(selection.edge.source, nodes)} <em>{selection.edge.label}</em> {getNodeLabel(selection.edge.target, nodes)}</h2>
              <p>{selection.edge.description}</p>
              {selection.edge.condition && <p><strong>Condición:</strong> {selection.edge.condition}</p>}
              <div className="detail-evidence">
                <span className="control-title">Fundamento</span>
                <strong>{selection.edge.legalBasis}</strong>
                {selection.edge.evidence.map((evidence) => (
                  <a className="source-link" href={evidence.url} target="_blank" rel="noreferrer" key={`${selection.edge.id}-${evidence.sourceId}`}>
                    <strong>{evidence.publisher}</strong><span>{evidence.locator} · consultado {evidence.retrievedAt}</span>
                  </a>
                ))}
              </div>
              <Link className="button button-secondary button-small" href={`/relaciones/${selection.edge.id}`}>Ficha de relación</Link>
            </>
          )}
        </aside>
      </div>

      {showTable && (
        <div className="section-sm" style={{ overflowX: "auto" }}>
          <table className="relation-table">
            <caption className="control-title" style={{ textAlign: "left" }}>Relaciones visibles en el mapa</caption>
            <thead><tr><th>Actor</th><th>Relación</th><th>Objetivo</th><th>Fundamento</th></tr></thead>
            <tbody>
              {visibleEdges.map((edge) => (
                <tr key={edge.id}>
                  <td>{getNodeLabel(edge.source, nodes)}</td><td><Link href={`/relaciones/${edge.id}`}>{edge.label}</Link></td>
                  <td>{getNodeLabel(edge.target, nodes)}</td><td>{edge.legalBasis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function getNodeLabel(id: string, nodes: GraphNode[]) {
  return nodes.find((node) => node.id === id)?.shortLabel ?? id;
}
