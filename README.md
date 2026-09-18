# Mapa de Poder México

Plataforma pública para explorar la estructura formal del Estado mexicano, las personas que ocupan sus cargos y las relaciones de autoridad sustentadas por fuentes oficiales.

## Estado

Este repositorio contiene una segunda versión del MVP vertical. El mapa dejó de
ser un grafo genérico para convertirse en una exploración radial y semántica de
la estructura federal mexicana:

- experiencia pública multirruta y mapa radial SVG accesible, con expansión progresiva;
- API REST en FastAPI;
- esquema PostgreSQL temporal y verificable;
- consola de revisión protegida con Supabase Auth;
- trabajadores de ingestión que sólo generan candidatos para revisión;
- datos demostrativos con evidencia oficial y fechas de consulta.

Los datos incluidos permiten probar el producto, pero no deben interpretarse como una cobertura exhaustiva del Gobierno Federal.

## Mapa radial federal

`/mapa` representa la soberanía popular y la organización constitucional sin
tratar a los órganos autónomos como un cuarto poder. El centro es el nodo
**Pueblo de México**, con la referencia al artículo 39 constitucional. A su
alrededor se distribuyen cuatro sectores semánticos:

- Poder Ejecutivo, en verde nacional profundo.
- Poder Legislativo, en rojo mexicano.
- Poder Judicial, en dorado/ocre.
- Órganos constitucionales autónomos, en jade diferenciado.

Los anillos representan, de dentro hacia fuera, poderes u órganos superiores,
dependencias e instituciones, cargos y personas. El tamaño de los sectores no
depende del número de entidades. Congreso, paraestatales y órganos colegiados
empiezan como agrupaciones con conteo y se expanden bajo demanda. Al seleccionar
un nodo se atenúa el contexto, se dibujan sólo sus relaciones directas y se
abre una ficha con vigencia, ocupación, evidencia e historial.

La interacción es accesible por teclado y tiene equivalentes para toque en
móvil. La URL conserva `asOf`, `root` y `node`, por lo que una consulta puede
compartirse o restaurarse con atrás/adelante. Si la API no está disponible, la
misma experiencia se mantiene con el subconjunto de `mvp.json` y un aviso de
cobertura demostrativa.

```text
PowerMapExplorer
├── barra: búsqueda, fecha, leyenda y ruta
├── RadialPowerMap: sectores, anillos, nodos, relaciones y zoom/pan
├── tooltip de foco/hover
└── panel de selección: resumen, retrato, cargo, relaciones, evidencia e historial
```

El render deduplica entidades por identificador y reserva el nodo de ciudadanía
para el centro, incluso ante registros heredados con una rama incorrecta.
Los nodos emplean iconografía por tipo de entidad y transiciones respetuosas de
`prefers-reduced-motion`. Las cámaras legislativas ofrecen además una vista de
hemiciclo que representa cada cargo estable y agrupa los escaños por el
`parliamentaryGroup` publicado; esta vista no infiere afiliaciones ausentes.
En las expansiones, los anillos conservan la jerarquía institución → cargo →
persona y alinean cada descendiente con su entidad superior para reducir cruces.
El cargo de la Presidencia de México tiene un distintivo visual propio que no
depende de la persona que lo ocupe en el corte consultado.

## API del mapa

`/v1/graph` se conserva para compatibilidad. La nueva experiencia utiliza
endpoints especializados y paginados:

- `GET /v1/power-map?as_of=&root=&depth=&cursor=&limit=`: corte inicial o expansión.
- `GET /v1/nodes/{identifier}/context?as_of=`: ficha, relaciones, evidencia e historial de una selección.
- `GET /v1/search`: búsqueda por nombre, rama, categoría y vigencia.

Los contratos compartidos incluyen `PowerMapNode`, `PowerMapGroup`,
`OccupancySummary`, `PortraitSummary`, `PowerMapRelationship` y
`PowerMapResponse`; TypeScript y Pydantic conservan el mismo formato camelCase.

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
psql postgresql://mapa:mapa@localhost:5432/mapa_poder -f db/migrations/0002_power_map.sql
psql postgresql://mapa:mapa@localhost:5432/mapa_poder -f db/seeds/0001_mvp.sql
```

## Principios de publicación

1. Toda relación pública debe tener una afirmación aprobada y al menos una evidencia.
2. Los adaptadores automáticos sólo crean candidatos en `needs_review`.
3. Una corrección sustituye una afirmación anterior; no la sobrescribe.
4. La vigencia del hecho y la historia del sistema se registran por separado.

Consulta [docs/operations.md](docs/operations.md) para despliegue y operación editorial.
