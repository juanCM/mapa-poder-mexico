# Operación y despliegue

## Entornos

- **Desarrollo:** datos semilla compartidos; PostgreSQL local opcional.
- **Pruebas:** proyecto Supabase y servicios Railway separados de producción.
- **Producción:** web en Vercel, API y worker en Railway, PostgreSQL/Auth/Storage en Supabase.

Nunca reutilizar llaves de servicio, buckets ni bases de datos entre entornos.

## Despliegue inicial

1. Crear el proyecto Supabase, ejecutar `db/migrations/0001_initial.sql` y crear el bucket privado `source-documents`.
2. En Supabase Auth, crear la persona administradora con correo y contraseña; conservar ese correo en `ADMIN_EMAIL_ALLOWLIST`.
3. Importar el conjunto inicial con `db/seeds/import_mvp.py`.
4. Crear servicios Railway separados para `apps/api` y `apps/worker`.
5. Configurar en Railway `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `PUBLIC_WEB_ORIGIN` y `ADMIN_API_TOKEN`.
6. Configurar en Vercel `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`, las variables públicas de Supabase y la lista de administradores.
7. Programar tres ejecuciones Railway: Gobierno y DOF diariamente; LeyesBiblio semanalmente.

## Flujo editorial

1. El worker conserva el documento y calcula su SHA-256.
2. Un hash ya conocido no crea un snapshot nuevo.
3. Los parsers deterministas generan candidatos `needs_review`.
4. La persona revisora verifica entidad, relación, vigencia, condición y localizador.
5. Aprobar crea una afirmación; publicar la hace visible. Nunca editar el contenido de una afirmación publicada.
6. Una corrección se publica como nueva afirmación que sustituye la anterior.

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

## Incidentes de datos

Si se publica información incorrecta, retirar la afirmación, conservar su historial, abrir una tarea crítica, publicar una versión corregida y registrar un evento explicando el cambio. No eliminar snapshots ni evidencia relacionada.
