# AGENTS.md — Mapa de Poder México

## Propósito y estado

Mapa de Poder México es una plataforma pública para explorar la estructura formal del Estado mexicano, las personas que ocupan cargos y las relaciones de autoridad sustentadas en fuentes oficiales. El repositorio contiene un MVP vertical funcional, no una cobertura exhaustiva del Gobierno Federal.

El producto combina: mapa interactivo, fichas de instituciones/personas/relaciones, consulta temporal, fuentes y cambios, y una consola editorial protegida para revisar candidatos generados por ingestión automática.

## Arquitectura de alto nivel

```text
Fuentes oficiales
   ↓ discover/fetch/parse
apps/worker (Python)
   ├─ snapshots con SHA-256 → almacenamiento local o Supabase Storage
   └─ candidatos needs_review → PostgreSQL
                                      ↓ revisión/publicación
PostgreSQL/Supabase ← apps/api (FastAPI) ← apps/web (Next.js)
                                      ↑
                         seed JSON como fallback local
```

Es un monorepo npm con workspaces para la web y paquetes TypeScript, además de dos paquetes Python independientes para API y worker. En producción la web se despliega en Vercel, API y worker en Railway, y PostgreSQL/Auth/Storage en Supabase.

## Mapa del repositorio

- `apps/web/`: aplicación Next.js 16 + React 19. App Router, páginas públicas y administración, API routes proxy, renderizado del grafo con Sigma.js/Graphology.
- `apps/api/`: API FastAPI. Lee PostgreSQL si existe `DATABASE_URL`; sin ella sirve `packages/contracts/data/mvp.json`.
- `apps/worker/`: ingestión de fuentes oficiales. Descubre documentos, los descarga, calcula hashes, guarda snapshots y crea tareas editoriales; no publica automáticamente.
- `packages/contracts/`: tipos TypeScript compartidos y dataset MVP `data/mvp.json`.
- `packages/taxonomy/`: vocabularios de tipos de relación, organización y dominio de política pública.
- `db/migrations/0001_initial.sql`: esquema PostgreSQL, índices, restricciones, trigger de inmutabilidad y vista publicada.
- `db/seeds/`: seed SQL MVP e importador JSON→PostgreSQL.
- `sources/fixtures/`: HTML de prueba de adaptadores.
- `docs/operations.md`: despliegue, operación editorial, incorporación de fuentes, cobertura APF e incidentes.
- `docker-compose.yml`: PostgreSQL 16 local.
- `vercel.json`, `apps/*/railway.toml`, Dockerfiles: configuración de despliegue.

## Modelo de datos y publicación

El núcleo del modelo vive en `db/migrations/0001_initial.sql`:

- `nodes` es la entidad polimórfica base: `jurisdiction`, `organization`, `unit`, `position`, `person`.
- Tablas especializadas: `jurisdictions`, `organizations`, `organizational_units`, `positions`, `persons`.
- `tenures` modela ocupación persona↔cargo; `memberships` modela pertenencia persona↔organización.
- `relationships` modela aristas entre nodos. `relationship_class` distingue `structure`, `power`, `competence`, `accountability` y `tenure`.
- `procedures`/`procedure_steps` modelan procedimientos institucionales.
- `legal_instruments`/`legal_provisions` contienen fundamento normativo.
- `source_documents` identifica la fuente; `source_snapshots` conserva cada versión descargada; `source_fragments` localiza el fragmento relevante.
- `assertions` representa afirmaciones temporales extraídas o revisadas; `evidence_links` vincula afirmaciones con evidencia.
- `entity_aliases` y `external_identifiers` soportan resolución de identidad y búsqueda.
- `ingestion_runs` registra ejecuciones; `review_tasks` es la cola editorial; `government_change_events` publica cambios verificables.

### Reglas invariantes

1. Toda relación visible debe tener una afirmación `published` y evidencia asociada.
2. Un adaptador automático sólo genera candidatos `needs_review`.
3. Las fechas usan rangos PostgreSQL `[inicio, fin)`; la fecha final es exclusiva.
4. Una afirmación publicada es inmutable en sujeto, predicado, objeto, relación y vigencia. Las correcciones crean otra afirmación con `supersedes_assertion_id`.
5. `published_relationships` sólo expone relaciones con al menos una afirmación publicada.
6. Snapshots se deduplican por fuente y `content_hash` SHA-256.
7. No borrar snapshots ni evidencia durante correcciones o incidentes.

## API FastAPI

Entrada: `apps/api/app/main.py`. Conversión SQL→contrato: `apps/api/app/repository.py`; modelos Pydantic: `schemas.py`; configuración: `settings.py`; autenticación simple de administración: `auth.py`.

Endpoints principales:

- `GET /health`: estado, fecha del dataset, persistencia y conteos.
- `GET /v1/search?q=&types=&as_of=`: búsqueda temporal por nombre/alias.
- `GET /v1/nodes/{identifier}`: detalle por UUID o slug.
- `GET /v1/graph?mode=organization|power&as_of=&root=&depth=&relation_types=`: grafo publicado y temporal.
- `GET /v1/relationships/{identifier}`: detalle de relación publicada.
- `GET /v1/timeline?node_id=` y `GET /v1/changes`: eventos de cambio.
- `GET /v1/admin/review-tasks` y `GET /v1/admin/overview`: endpoints protegidos.
- `POST /v1/admin/review-tasks/{task_id}/decision`: aprueba o rechaza una tarea.

Cuando hay `DATABASE_URL`, las consultas leen PostgreSQL. Sin ella, la API cae al dataset JSON para permitir desarrollo de la interfaz. La protección API usa `Authorization: Bearer ADMIN_API_TOKEN`; en development sin token existe un bypass intencional.

## Web Next.js

La aplicación está en `apps/web/app/` y usa App Router. `lib/data.ts` carga el dataset compartido para el modo seed. `app/api/graph/route.ts` funciona como proxy server-side hacia FastAPI. `lib/admin.ts` valida sesión Supabase y allowlist de correos; el endpoint de decisión reenvía al API.

Componentes relevantes:

- `graph-explorer.tsx`: grafo Sigma, modos organigrama/poder, fecha de consulta, filtros, selección de nodos/aristas y tabla accesible.
- `node-detail.tsx`: ficha de entidad y relaciones.
- `admin-dashboard.tsx`/`admin-review-board.tsx`: revisión editorial.
- `search-box.tsx`: búsqueda local del MVP.
- `site-header.tsx`/`site-footer.tsx`: shell público.

Rutas públicas: `/`, `/mapa`, `/cambios`, `/personas/[slug]`, `/instituciones/[slug]`, `/relaciones/[id]`, `/fuentes/[id]`. Administración: `/admin/login`, `/admin`; callback: `/auth/callback`.

Al modificar Next.js, leer primero las guías locales de `apps/web/node_modules/next/dist/docs/` y conservar el bloque generado en `apps/web/AGENTS.md`.

## Worker e ingestión

Entrada CLI: `mapa-ingest <apf|gobierno|leyesbiblio|dof>` (`apps/worker/worker/cli.py`). `IngestionRunner` ejecuta:

1. `discover()` obtiene documentos.
2. `fetch()` descarga con `httpx` y user-agent del proyecto.
3. Calcula SHA-256 y guarda el snapshot en `INGESTION_STORAGE_DIR` o Supabase Storage.
4. `parse()` produce `CandidateAssertion` deterministas.
5. `normalize()` deduplica por `candidate_id`.
6. `PostgresReviewSink` registra ejecución y crea tareas `needs_review` sin duplicar candidaturas abiertas.

Adaptadores actuales: `apf.py` (LOAPF y entidades paraestatales), `gobierno.py` (directorio gob.mx), `leyesbiblio.py` (índice de leyes) y `dof.py` (publicaciones del DOF). Los parsers deben ser conservadores: no inferir nombres o relaciones ambiguas a partir de navegación, PDFs binarios o encabezados.

Para una nueva fuente: añadir adaptador, fixture representativo, prueba contractual, registro de fuente, frecuencia y revisión manual de todos los candidatos antes de programarla.

## Contratos y taxonomía

`packages/contracts/src/index.ts` define `GraphNode`, `GraphEdge`, `EvidenceSummary`, `SourceRecord`, `ChangeEvent`, `ReviewTask`, `MvpDataset` y `GraphResponse`. Mantener sus nombres camelCase alineados con los alias Pydantic de la API.

`packages/taxonomy/src/index.ts` contiene valores como `PART_OF`, `HEADS`, `HOLDS`, `APPOINTS`, `OVERSEES`, `AUDITS`, etc. Reutilizar estos vocabularios antes de inventar tipos nuevos.

## Desarrollo y comandos

Requisitos: Node.js 20+, Python 3.9+ y PostgreSQL 16 para persistencia.

```bash
npm install
npm run dev
npm run build
npm run lint
npm run typecheck
npm test
python3 -m venv .venv
source .venv/bin/activate
pip install -e 'apps/api[dev]' -e 'apps/worker[dev]'
uvicorn app.main:app --app-dir apps/api --reload
docker compose up -d postgres
```

Pruebas web: `npm test --workspace @mapa/web`, `npm run typecheck --workspace @mapa/web`, `npm run test:e2e --workspace @mapa/web`. Pruebas Python: `pytest -q apps/api/tests apps/worker/tests`; lint: `ruff check apps/api apps/worker`.

Inicialización SQL:

```bash
psql postgresql://mapa:mapa@localhost:5432/mapa_poder -f db/migrations/0001_initial.sql
psql postgresql://mapa:mapa@localhost:5432/mapa_poder -f db/seeds/0001_mvp.sql
```

## Variables de entorno

- Web: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` o publishable key, `ADMIN_EMAIL_ALLOWLIST`, opcional `ADMIN_BYPASS_AUTH` sólo local.
- API: `DATABASE_URL`, `PUBLIC_WEB_ORIGIN`, `ADMIN_API_TOKEN`, `ENVIRONMENT`.
- Worker: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `INGESTION_STORAGE_DIR`.

Nunca exponer service keys en el cliente ni versionar secretos. El archivo `.env.example` debe contener placeholders, no credenciales reales; si un valor parece válido, rotarlo antes de desplegar.

## Riesgos y deuda técnica conocida

- La autorización API es un bearer token compartido y el bypass de desarrollo debe permanecer deshabilitado en producción.
- El seed JSON y PostgreSQL son dos caminos de datos; cualquier cambio de contrato debe probar ambos.
- La vista de grafo hace consultas y carga evidencia por relación; con mayor volumen será necesario paginar, precalcular o agrupar consultas.
- La resolución de entidades y la publicación de candidatos aún dependen de revisión humana; no declarar cobertura completa por el conteo del seed.
- El worker hace descargas síncronas y no implementa todavía reintentos/backoff explícitos ni control avanzado de cambios.
- La fuente de personas (nómina/directorios) requiere importación por lotes, deduplicación, historial de ocupación y aprobación editorial; no crear millones de tareas individuales.
- Deben añadirse controles de integridad/semántica para evitar solapamientos temporales, evidencias faltantes y relaciones publicadas incompletas.
- El repo contiene artefactos locales (`.next`, caches, egg-info); no deben tratarse como fuente de arquitectura ni editarse manualmente.

## Protocolo para agentes de IA

Antes de cambiar código:

1. Revisar `README.md`, este archivo, `docs/operations.md` y el archivo de la capa afectada.
2. Consultar `git status --short` y preservar cambios locales no relacionados.
3. Si se modifica la web, consultar las guías Next.js locales indicadas en `apps/web/AGENTS.md`.
4. Mantener el flujo evidencia→afirmación→revisión→publicación; nunca insertar datos públicos directamente desde un adaptador.
5. Actualizar contratos, seed, pruebas y documentación cuando se cambie una respuesta o entidad.
6. Ejecutar las pruebas/lint disponibles y reportar explícitamente herramientas ausentes o fallos de entorno.
7. No registrar secretos, no borrar snapshots y no usar comandos destructivos para limpiar el repositorio.

Al entregar trabajo, indicar archivos modificados, comandos ejecutados, resultados y cualquier riesgo pendiente.
