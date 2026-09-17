import type { Metadata } from "next";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: { default: "Mapa de Poder México", template: "%s | Mapa de Poder México" },
  description: "Explora quién ocupa cada cargo, quién nombra a quién y qué norma sustenta cada relación del Estado mexicano.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  openGraph: {
    title: "Mapa de Poder México",
    description: "Instituciones, cargos y facultades con evidencia oficial.",
    type: "website",
    locale: "es_MX"
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es" data-scroll-behavior="smooth">
      <body>
        <a href="#contenido" className="skip-link">Saltar al contenido</a>
        <SiteHeader />
        <main id="contenido">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
