import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { GraphExplorer } from "@/components/graph-explorer";
import { dataset } from "@/lib/data";

export const metadata: Metadata = {
  title: "Mapa interactivo",
  description: "Explora la estructura y las relaciones formales de poder del Estado mexicano."
};

export default function MapPage() {
  return (
    <div className="container">
      <header className="page-hero">
        <div className="crumbs"><Link href="/">Inicio</Link><ChevronRight size={13} /><span>Mapa</span></div>
        <span className="eyebrow">Explorador institucional</span>
        <h1 className="page-title">Una vista para la estructura. Otra para las facultades.</h1>
        <p className="page-intro">Selecciona cualquier institución o conexión para consultar su vigencia y el documento oficial que la respalda. Este conjunto es una muestra curada del núcleo federal.</p>
      </header>
      <GraphExplorer nodes={dataset.nodes} edges={dataset.edges} />
      <div className="section-sm" />
    </div>
  );
}
