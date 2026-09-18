import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { GraphExplorer } from "@/components/graph-explorer";
import { dataset } from "@/lib/data";
import type { GraphResponse } from "@mapa/contracts";

export const metadata: Metadata = {
  title: "Mapa interactivo",
  description: "Explora la estructura y las relaciones formales de poder del Estado mexicano."
};

export const dynamic = "force-dynamic";

function today() {
  return new Date().toISOString().slice(0, 10);
}

async function loadInitialGraph(asOf: string): Promise<{ graph: GraphResponse; error?: string }> {
  const fallback: GraphResponse = {
    asOf,
    mode: "power",
    nodes: dataset.nodes,
    edges: dataset.edges.filter((edge) => edge.mode === "power" || edge.mode === "both")
  };
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return { graph: fallback, error: "La API no está configurada; se muestran los datos semilla." };

  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/v1/graph?mode=power&as_of=${asOf}`, { cache: "no-store" });
    if (!response.ok) return { graph: fallback, error: `La API respondió con ${response.status}; se muestran los datos semilla.` };
    return { graph: await response.json() as GraphResponse };
  } catch {
    return { graph: fallback, error: "No fue posible conectar con la API; se muestran los datos semilla." };
  }
}

export default async function MapPage() {
  const { graph, error } = await loadInitialGraph(today());
  return (
    <div className="container">
      <header className="page-hero">
        <div className="crumbs"><Link href="/">Inicio</Link><ChevronRight size={13} /><span>Mapa</span></div>
        <span className="eyebrow">Explorador institucional</span>
        <h1 className="page-title">Una vista para la estructura. Otra para las facultades.</h1>
        <p className="page-intro">Selecciona cualquier institución o conexión para consultar su vigencia y el documento oficial que la respalda. Este conjunto es una muestra curada del núcleo federal.</p>
      </header>
      <GraphExplorer initialGraph={graph} initialError={error} />
      <div className="section-sm" />
    </div>
  );
}
