import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { PowerMapLoader } from "@/components/power-map/power-map-loader";
import { createFallbackPowerMap } from "@/lib/power-map";
import type { PowerMapResponse } from "@mapa/contracts";

export const metadata: Metadata = {
  title: "Mapa interactivo",
  description: "Explora la estructura y las relaciones formales de poder del Estado mexicano."
};

export const dynamic = "force-dynamic";

function today() {
  return new Date().toISOString().slice(0, 10);
}

async function loadInitialMap(asOf: string): Promise<{ map: PowerMapResponse; error?: string }> {
  const fallback = createFallbackPowerMap(asOf);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return { map: fallback, error: "La API no está configurada; se muestran datos demostrativos." };

  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/v1/power-map?as_of=${asOf}&depth=2&limit=1000`, { cache: "no-store" });
    if (!response.ok) return { map: fallback, error: `La API respondió con ${response.status}; se muestran datos demostrativos.` };
    return { map: await response.json() as PowerMapResponse };
  } catch {
    return { map: fallback, error: "No fue posible conectar con la API; se muestran datos demostrativos." };
  }
}

export default async function MapPage() {
  const { map, error } = await loadInitialMap(today());
  return (
    <div className="container">
      <header className="page-hero">
        <div className="crumbs"><Link href="/">Inicio</Link><ChevronRight size={13} /><span>Mapa</span></div>
        <span className="eyebrow">Explorador institucional</span>
        <h1 className="page-title">El poder público federal, desde el pueblo hasta cada cargo.</h1>
        <p className="page-intro">Recorre los Poderes de la Unión y los órganos constitucionales autónomos. Expande instituciones, selecciona cargos y consulta relaciones, vigencia y evidencia oficial.</p>
      </header>
      <PowerMapLoader initialMap={map} initialError={error} />
      <div className="section-sm" />
    </div>
  );
}
