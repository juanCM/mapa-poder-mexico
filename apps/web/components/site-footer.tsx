import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div><strong>Mapa de Poder México</strong><br />Instituciones, cargos y facultades con evidencia.</div>
        <div>Los datos muestran relaciones jurídicas formales, no una valoración política.</div>
        <div><Link href="/fuentes/src-constitucion">Fuentes</Link> · <Link href="/admin">Administración</Link></div>
      </div>
    </footer>
  );
}
