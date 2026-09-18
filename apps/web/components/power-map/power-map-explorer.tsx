"use client";

import { CalendarDays, ChevronLeft, Database, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { GraphNode, NodeContextResponse, PowerMapNode, PowerMapResponse } from "@mapa/contracts";
import { createFallbackNodeContext, createFallbackPowerMap } from "@/lib/power-map";
import { NodeSelectionPanel } from "./node-selection-panel";
import { RadialPowerMap } from "./radial-power-map";
import styles from "./power-map.module.css";

const branchOptions = [
  ["executive", "Ejecutivo"],
  ["legislative", "Legislativo"],
  ["judicial", "Judicial"],
  ["independent", "Autónomos"]
] as const;

export function PowerMapExplorer({ initialMap, initialError }: { initialMap: PowerMapResponse; initialError?: string }) {
  const [map, setMap] = useState(initialMap);
  const [asOf, setAsOf] = useState(initialMap.asOf);
  const [selected, setSelected] = useState<PowerMapNode | null>(null);
  const [context, setContext] = useState<NodeContextResponse | null>(null);
  const [enabledBranches, setEnabledBranches] = useState<Set<string>>(() => new Set(branchOptions.map(([branch]) => branch)));
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GraphNode[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [contextLoading, setContextLoading] = useState(false);
  const [error, setError] = useState(initialError);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function restore() {
      const params = new URLSearchParams(window.location.search);
      const nextDate = params.get("asOf") ?? new Date().toISOString().slice(0, 10);
      const root = params.get("root");
      const node = params.get("node");
      void loadMap(nextDate, root, false).then((next) => {
        if (node) {
          const found = next.nodes.find((item) => item.id === node || item.slug === node);
          if (found) void selectNode(found, false);
        } else {
          setSelected(null);
          setContext(null);
        }
      });
    }
    window.addEventListener("popstate", restore);
    const params = new URLSearchParams(window.location.search);
    const initialNode = params.get("node");
    if (initialNode) {
      const found = initialMap.nodes.find((item) => item.id === initialNode || item.slug === initialNode);
      if (found) void selectNode(found, false);
    }
    return () => window.removeEventListener("popstate", restore);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const breadcrumbs = [...map.ancestors, ...(map.root ? map.nodes.filter((node) => node.id === map.root) : [])];

  function writeUrl(values: { root?: string | null; node?: string | null; date?: string }, replace = false) {
    const params = new URLSearchParams(window.location.search);
    const root = values.root === undefined ? map.root : values.root;
    const node = values.node === undefined ? selected?.slug : values.node;
    const date = values.date ?? asOf;
    if (root) params.set("root", root); else params.delete("root");
    if (node) params.set("node", node); else params.delete("node");
    params.set("asOf", date);
    window.history[replace ? "replaceState" : "pushState"]({}, "", `${window.location.pathname}?${params}`);
  }

  async function loadMap(nextDate: string, root: string | null, updateUrl = true, cursor?: string | null) {
    setLoading(true);
    setError(undefined);
    try {
      const params = new URLSearchParams({ asOf: nextDate, depth: "2", limit: root ? "120" : "500" });
      if (root) params.set("root", root);
      if (cursor) params.set("cursor", cursor);
      const response = await fetch(`/api/power-map?${params}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`La API respondió con ${response.status}.`);
      const responseMap = await response.json() as PowerMapResponse;
      const next = cursor && map.root === responseMap.root && map.asOf === responseMap.asOf
        ? {
            ...responseMap,
            nodes: [...new Map([...map.nodes, ...responseMap.nodes].map((node) => [node.id, node])).values()],
            relationships: [...new Map([...map.relationships, ...responseMap.relationships].map((edge) => [edge.id, edge])).values()]
          }
        : responseMap;
      setMap(next);
      setAsOf(nextDate);
      if (updateUrl) writeUrl({ root: next.root, node: null, date: nextDate });
      return next;
    } catch (cause) {
      const fallback = createFallbackPowerMap(nextDate, root);
      setMap(fallback);
      setAsOf(nextDate);
      setError(cause instanceof Error ? `${cause.message} Se muestran datos demostrativos.` : "No fue posible cargar el mapa.");
      if (updateUrl) writeUrl({ root: fallback.root, node: null, date: nextDate });
      return fallback;
    } finally {
      setLoading(false);
    }
  }

  async function selectNode(node: PowerMapNode, updateUrl = true) {
    setSelected(node);
    setContext(null);
    setContextLoading(true);
    if (updateUrl) writeUrl({ node: node.slug });
    try {
      const response = await fetch(`/api/nodes/${encodeURIComponent(node.id)}/context?asOf=${encodeURIComponent(asOf)}`, { cache: "no-store" });
      if (!response.ok) throw new Error();
      setContext(await response.json() as NodeContextResponse);
    } catch {
      setContext(createFallbackNodeContext(node.id, asOf));
    } finally {
      setContextLoading(false);
    }
  }

  async function explore(node: PowerMapNode) {
    const next = await loadMap(asOf, node.id);
    const rootNode = next.nodes.find((item) => item.id === next.root) ?? null;
    setSelected(rootNode);
    setContext(null);
    if (rootNode) {
      writeUrl({ root: next.root, node: rootNode.slug, date: asOf }, true);
      void selectNode(rootNode, false);
    }
  }

  async function chooseSearchResult(node: GraphNode) {
    setQuery("");
    setResults([]);
    setSearchOpen(false);
    const next = await loadMap(asOf, node.id);
    const found = next.nodes.find((item) => item.id === node.id);
    if (found) {
      writeUrl({ root: next.root, node: found.slug, date: asOf }, true);
      void selectNode(found, false);
    }
  }

  function search(value: string) {
    setQuery(value);
    setSearchOpen(Boolean(value));
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (value.trim().length < 2) { setResults([]); return; }
    searchTimer.current = setTimeout(async () => {
      try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(value.trim())}&asOf=${encodeURIComponent(asOf)}`);
        if (!response.ok) throw new Error();
        const payload = await response.json() as { results: GraphNode[] };
        setResults(payload.results.slice(0, 12));
      } catch {
        setResults(map.nodes.filter((node) => `${node.label} ${node.shortLabel}`.toLocaleLowerCase("es").includes(value.toLocaleLowerCase("es"))).slice(0, 12));
      }
    }, 180);
  }

  function toggleBranch(branch: string) {
    setEnabledBranches((current) => {
      const next = new Set(current);
      if (next.has(branch)) next.delete(branch); else next.add(branch);
      return next;
    });
  }

  return (
    <section className={styles.explorer} aria-label="Explorador del poder público federal">
      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <Search size={16} aria-hidden="true" />
          <input value={query} onChange={(event) => search(event.target.value)} onFocus={() => setSearchOpen(Boolean(query))} placeholder="Buscar institución, cargo o persona" aria-label="Buscar en el mapa" />
          {query && <button type="button" onClick={() => { setQuery(""); setResults([]); }} aria-label="Limpiar búsqueda"><X size={14} /></button>}
          {searchOpen && (
            <div className={styles.searchResults} role="listbox" aria-label="Resultados de búsqueda">
              {results.length ? results.map((node) => (
                <button type="button" role="option" aria-selected="false" key={node.id} onClick={() => void chooseSearchResult(node)}>
                  <strong>{node.shortLabel}</strong><span>{node.kind} · {branchLabel(node.branch)}</span>
                </button>
              )) : <p>{query.trim().length < 2 ? "Escribe al menos dos caracteres." : "No se encontraron coincidencias."}</p>}
            </div>
          )}
        </div>
        <label className={styles.dateControl}><CalendarDays size={15} /><span>Fecha</span><input type="date" value={asOf} onChange={(event) => void loadMap(event.target.value, map.root)} /></label>
        {map.root && <button className={styles.backButton} type="button" onClick={() => void loadMap(asOf, map.ancestors.at(-1)?.id ?? null)}><ChevronLeft size={15} /> Volver</button>}
      </div>

      <div className={styles.legendRow}>
        <div className={styles.breadcrumbs} aria-label="Ruta del mapa">
          <button type="button" onClick={() => void loadMap(asOf, null)}>México</button>
          {breadcrumbs.map((node) => <span key={node.id}>/ <button type="button" onClick={() => void loadMap(asOf, node.id)}>{node.shortLabel}</button></span>)}
        </div>
        <div className={styles.branchFilters} aria-label="Filtrar poderes">
          {branchOptions.map(([branch, label]) => (
            <button key={branch} type="button" data-branch={branch} aria-pressed={enabledBranches.has(branch)} onClick={() => toggleBranch(branch)}><span />{label}</button>
          ))}
        </div>
      </div>

      <div className={styles.workspace}>
        <div className={styles.mapColumn}>
          <RadialPowerMap nodes={map.nodes} relationships={map.relationships} root={map.root} selectedId={selected?.id ?? null} enabledBranches={enabledBranches} onSelect={(node) => void selectNode(node)} />
          <div className={styles.mapStatus}>
            <span><Database size={12} /> {map.stats.organizations} instituciones · {map.stats.positions} cargos · {map.stats.people} personas</span>
            <span>{loading ? "Actualizando…" : `Corte ${asOf}`}</span>
          </div>
          {error && <div className={styles.mapNotice} role="status">{error}</div>}
          {map.nextCursor && <button type="button" className="button button-secondary button-small" onClick={() => void loadMap(asOf, map.root, false, map.nextCursor)}>Cargar más elementos</button>}
        </div>
        <NodeSelectionPanel node={selected} context={context} loading={contextLoading} nodes={map.nodes} onExplore={explore} onClose={() => { setSelected(null); setContext(null); writeUrl({ node: null }); }} />
      </div>
      <p className={styles.coverageNote}>El mapa muestra relaciones publicadas con evidencia oficial. “Titular no registrado” describe la cobertura del sistema; “vacante” sólo se usa cuando una fuente lo confirma.</p>
    </section>
  );
}

function branchLabel(branch: string) {
  return ({ executive: "Ejecutivo", legislative: "Legislativo", judicial: "Judicial", independent: "Autónomo", state: "Estado" } as Record<string, string>)[branch] ?? branch;
}
