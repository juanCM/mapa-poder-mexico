import Link from "next/link";
import { Network } from "lucide-react";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="nav-shell">
        <Link href="/" className="brand" aria-label="Mapa de Poder México, inicio">
          <span className="brand-mark"><Network size={18} aria-hidden="true" /></span>
          <span>Mapa de Poder <small>México</small></span>
        </Link>
        <nav className="nav-links" aria-label="Navegación principal">
          <Link href="/mapa">Explorar mapa</Link>
          <Link href="/cambios">Cambios</Link>
          <Link href="/#metodologia">Metodología</Link>
          <Link href="/admin">Administrar</Link>
        </nav>
        <span className="status-pill"><span className="status-dot" /> Datos verificados</span>
      </div>
    </header>
  );
}
