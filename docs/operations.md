# Operación y despliegue

## Entornos

- **Desarrollo:** datos semilla compartidos; PostgreSQL local opcional.
- **Pruebas:** proyecto Supabase y servicios Railway separados de producción.
- **Producción:** web en Vercel, API y worker en Railway, PostgreSQL/Auth/Storage en Supabase.

Nunca reutilizar llaves de servicio, buckets ni bases de datos entre entornos.

## Despliegue inicial

1. Crear el proyecto Supabase, ejecutar en orden `db/migrations/0001_initial.sql` y `db/migrations/0002_power_map.sql`, y crear el bucket privado `source-documents`.
2. En Supabase Auth, crear la persona administradora con correo y contraseña; conservar ese correo en `ADMIN_EMAIL_ALLOWLIST`.
3. Importar el conjunto inicial con `db/seeds/import_mvp.py`.
4. Crear servicios Railway separados para `apps/api` y `apps/worker`.
5. Configurar en Railway `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `PUBLIC_WEB_ORIGIN` y `ADMIN_API_TOKEN`.
6. Configurar en Vercel `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`, las variables públicas de Supabase y la lista de administradores.
7. Programar las ejecuciones Railway: `apf`, `gobierno`, `congress`, `cabinet`, `judicial` y `autonomous` diariamente; DOF diariamente y LeyesBiblio semanalmente. Congreso y liderazgo deben detenerse si sus validaciones de cardinalidad detectan una fuente parcial.

## Flujo editorial

1. El worker conserva el documento y calcula su SHA-256.
2. Un hash ya conocido no crea un snapshot nuevo.
3. Los parsers deterministas generan un lote y candidatos `needs_review`.
4. La persona revisora verifica entidad, relación, vigencia, condición y localizador; puede excluir tareas ambiguas al decidir el lote.
5. Aprobar no modifica el mapa. `publish-approved` materializa exclusivamente tareas con estado `approved`.
6. La publicación crea cargo, persona, tenencia, relaciones estructurales y de ocupación, afirmaciones, evidencia y un evento de cambio en una transacción.
7. Una corrección se publica como nueva afirmación que sustituye la anterior. Nunca editar el contenido factual de una afirmación publicada.

## Alertas y respaldo

- Conectar errores de Vercel y Railway a correo; elevar cualquier fuente fallida durante dos ejecuciones consecutivas.
- Habilitar respaldos diarios y recuperación a un punto en el tiempo en Supabase.
- Exportar semanalmente afirmaciones, fuentes, relaciones y eventos en JSON a un prefijo separado del bucket.
- Verificar trimestralmente una restauración en el entorno de pruebas.

## Incorporar una fuente

1. Crear un adaptador que implemente `discover`, `fetch`, `parse`, `normalize` y `emit_candidates`.
2. Añadir un fixture HTML/PDF representativo y una prueba contractual.
3. Registrar la fuente con su editor, URL canónica, nivel de confianza y frecuencia.
4. Ejecutar manualmente y revisar todos los candidatos antes de programarla.

## Cobertura de la Administración Pública Federal

El adaptador `apf` registra dos fuentes de cobertura institucional:

1. la LOAPF para la Administración Pública Centralizada; y
2. la relación de entidades paraestatales publicada por el DOF.

Ejecutar `mapa-ingest apf` crea candidatos verificables, no publicaciones
automáticas. La fuente transversal para personas es el portal público Nómina
Transparente, que se consulta por ramo, institución y página; los directorios
institucionales complementan perfiles y vigencia. No se debe convertir una
consulta masiva de nómina en millones de tareas individuales: primero debe
existir un mecanismo de importación por lote, deduplicación de personas,
historial de ocupación y aprobación editorial por lote. Antes de declarar una
cobertura como completa, verificar que cada registro tenga fuente, vigencia y
revisión editorial.

Una vez aprobados, publicar con `mapa-ingest publish-approved --adapter apf`.
Esta operación crea nodos, organizaciones, relaciones, afirmaciones publicadas
y enlaces de evidencia en una transacción. Sólo deben publicarse candidatos que
hayan sido revisados y aprobados.

Para una carga amplia, publicar en lotes (`--limit 25`) hasta que no queden
tareas aprobadas; esto acota la duración de cada transacción y facilita una
recuperación segura si una fuente o conexión falla.

También se puede limitar la publicación al lote revisado:

```bash
mapa-ingest publish-approved --batch-id UUID_DEL_LOTE --limit 100
```

### Congreso y órganos superiores

- `mapa-ingest congress` conserva y analiza los directorios oficiales de la LXVI Legislatura. Exige 500 asientos distintos para diputaciones y 128 para senadurías; si la fuente entrega menos, la ejecución falla y no crea un lote parcial.
- `mapa-ingest cabinet` procesa Presidencia y gabinete legal; `mapa-ingest judicial` procesa SCJN, Sala Superior del TEPJF, OAJ y TDJ; `mapa-ingest autonomous` procesa Consejo General del INE, Banxico, INEGI, CNDH, FGR y ASF. La separación evita que un cambio de formato en una fuente bloquee los otros dominios. `mapa-ingest leadership` conserva la ejecución conjunta para verificación manual.
- Los adaptadores sólo aceptan filas con cargo explícito y cardinalidad esperada. Un retrato se conserva únicamente junto con un perfil o fuente oficial; una fuente parcial falla antes de crear tareas editoriales.
- Las vacantes se representan como cargos sin persona. El estado `vacant` sólo se admite cuando aparece en la fuente; la ausencia de una tenencia se muestra como “titular no registrado”.
- Los metadatos legislativos se almacenan en el cargo estable: legislatura, entidad, distrito o circunscripción, principio de elección, asiento y grupo parlamentario.

Después de cada publicación, consultar `power_map_integrity_violations`. La vista reporta relaciones publicadas sin evidencia, retratos sin procedencia oficial y conteos constitucionales incompletos.

## Activación del mapa radial

El despliegue debe mantener este orden: migración aditiva, API compatible, ingestión, revisión de lotes, `publish-approved` y finalmente la web. `/v1/graph` permanece disponible, pero `/mapa` consume `/v1/power-map` y carga la evidencia completa mediante `/v1/nodes/{identifier}/context` sólo después de una selección.

Para personas, `mapa-ingest nomina` obtiene una página de Nómina Transparente
y crea candidatos `persona —HOLDS→ cargo`. Configurar la clave pública del
portal, ramo, UR, desplazamiento y límite mediante `NOMINA_TRANSPARENTE_API_KEY`,
`NOMINA_APF_RAMO`, `NOMINA_APF_UR`, `NOMINA_APF_OFFSET` y `NOMINA_APF_LIMIT`.
El publicador crea de forma idempotente la persona, el cargo, su organización,
la relación de ocupación y la evidencia después de la aprobación editorial.

## Incidentes de datos

Si se publica información incorrecta, retirar la afirmación, conservar su historial, abrir una tarea crítica, publicar una versión corregida y registrar un evento explicando el cambio. No eliminar snapshots ni evidencia relacionada.
