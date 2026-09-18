"use client";

import dynamic from "next/dynamic";
import type { PowerMapResponse } from "@mapa/contracts";

const LazyPowerMapExplorer = dynamic(
  () => import("./power-map-explorer").then((module) => module.PowerMapExplorer),
  {
    ssr: false,
    loading: () => <div className="notice" role="status">Preparando el mapa federal interactivo…</div>
  }
);

export function PowerMapLoader({ initialMap, initialError }: { initialMap: PowerMapResponse; initialError?: string }) {
  return <LazyPowerMapExplorer initialMap={initialMap} initialError={initialError} />;
}
