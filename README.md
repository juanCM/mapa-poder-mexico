# Mapa de Poder México

Plataforma pública para explorar la estructura formal del Estado mexicano, las personas que ocupan sus cargos y las relaciones de autoridad sustentadas por fuentes oficiales.

## Estado

Este repositorio contiene el primer MVP vertical:

- experiencia pública multirruta y mapa interactivo con Sigma.js;
- API REST en FastAPI;
- esquema PostgreSQL temporal y verificable;
- consola de revisión protegida con Supabase Auth;
- trabajadores de ingestión que sólo generan candidatos para revisión;
- datos demostrativos con evidencia oficial y fechas de consulta.

Los datos incluidos permiten probar el producto, pero no deben interpretarse como una cobertura exhaustiva del Gobierno Federal.

## Desarrollo local

Requisitos: Node.js 20+, Python 3.9+ y, para persistencia completa, PostgreSQL 16.

```bash
npm install
npm run dev
```

En otra terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e 'apps/api[dev]' -e 'apps/worker[dev]'
uvicorn app.main:app --app-dir apps/api --reload
```

La web utiliza datos semilla si `NEXT_PUBLIC_API_URL` no está disponible. Copia `.env.example` a `.env.local` para configurar Supabase y la API.

## Base de datos

```bash
docker compose up -d postgres
psql postgresql://mapa:mapa@localhost:5432/mapa_poder -f db/migrations/0001_initial.sql
psql postgresql://mapa:mapa@localhost:5432/mapa_poder -f db/seeds/0001_mvp.sql
```

## Principios de publicación

1. Toda relación pública debe tener una afirmación aprobada y al menos una evidencia.
2. Los adaptadores automáticos sólo crean candidatos en `needs_review`.
3. Una corrección sustituye una afirmación anterior; no la sobrescribe.
4. La vigencia del hecho y la historia del sistema se registran por separado.

Consulta [docs/operations.md](docs/operations.md) para despliegue y operación editorial.
