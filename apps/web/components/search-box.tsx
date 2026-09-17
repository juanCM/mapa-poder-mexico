"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { GraphNode } from "@mapa/contracts";
import { hrefForNode } from "@/lib/data";

export function SearchBox({ nodes }: { nodes: GraphNode[] }) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("es-MX");
    if (normalized.length < 2) return [];
    return nodes
      .filter((node) => `${node.label} ${node.shortLabel} ${node.description}`.toLocaleLowerCase("es-MX").includes(normalized))
      .slice(0, 6);
  }, [nodes, query]);

  return (
    <div className="search-box">
      <Search size={20} aria-hidden="true" />
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Busca una institución, persona o cargo…"
        aria-label="Buscar en el mapa"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={results.length > 0}
        aria-controls="home-search-results"
      />
      {results.length > 0 && (
        <div className="search-results" id="home-search-results" role="listbox" aria-label="Resultados de búsqueda">
          {results.map((node) => (
            <Link className="search-result" href={hrefForNode(node)} key={node.id} role="option">
              <span><strong>{node.shortLabel}</strong><small>{node.label !== node.shortLabel ? node.label : node.description}</small></span>
              <span className="tag">{node.kind === "person" ? "Persona" : node.branch}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
