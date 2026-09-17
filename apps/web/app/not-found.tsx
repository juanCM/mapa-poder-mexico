import Link from "next/link";

export default function NotFound() {
  return (
    <div className="narrow page-hero">
      <span className="eyebrow">404</span>
      <h1 className="page-title">Esta ficha no existe.</h1>
      <p className="page-intro">Puede que la entidad todavía no forme parte de la cobertura publicada.</p>
      <Link href="/mapa" className="button button-primary">Volver al mapa</Link>
    </div>
  );
}
