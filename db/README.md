# Esquema de datos

`0001_initial.sql` crea el modelo canónico y la cola editorial. Los rangos de PostgreSQL usan semántica `[inicio, fin)`: la fecha inicial se incluye y la final se excluye.

Reglas relevantes:

- las aristas sólo se exponen mediante `published_relationships` cuando existe una afirmación publicada;
- una afirmación publicada no puede cambiar de sujeto, predicado, objeto, relación ni vigencia;
- una corrección debe crear una afirmación con `supersedes_assertion_id`;
- los snapshots se deduplican por fuente y hash;
- `pg_trgm` proporciona búsqueda tolerante a alias y nombres.
