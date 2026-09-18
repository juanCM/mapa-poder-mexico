"""Carga editorial curada de los titulares del gabinete federal.

Por qué existe este archivo y no un adaptador: `gob.mx` sirve su directorio
mediante JavaScript y responde con un desafío anti-bot al cliente HTTP del
worker, así que `mapa-ingest cabinet` no puede alcanzarlo. Cada ficha se
recuperó desde un navegador real, se verificó contra la página oficial y se
registró con el SHA-256 y el tamaño exactos del documento recibido.

Los snapshots no guardan copia local: la fuente no es descargable por el
worker, de modo que `storage_path` declara esa condición en vez de apuntar a
un archivo inexistente. El hash permite reverificar la afirmación volviendo a
descargar la página, que es la garantía que importa.

Tres titularidades no tienen ficha oficial localizable y se publican como
atestiguación editorial (`ATTESTED`): la evidencia declara que su respaldo es
la palabra de una persona editora fechada, con `trust_tier` inferior, para que
una auditoría las distinga de las respaldadas por la fuente de gobierno. Es
preferible a inventarles una URL de gob.mx que las haría indistinguibles.

Idempotente: los identificadores son deterministas y toda escritura usa
ON CONFLICT, así que reejecutarlo no duplica registros.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "worker"))
from worker.publisher import slugify, stable_id

OBSERVED_ON = date(2026, 9, 18)
REVIEWER = "carga-editorial-gabinete"

# (slug de la dependencia, persona, cargo, fecha de inicio, confianza, url, sha256, bytes, título de la fuente)
#
# La confianza baja a 0.90 donde las fuentes discrepan en la fecha exacta de
# toma de posesión por unos días; el titular y la dependencia están
# confirmados en todos los casos.
CABINET = [
    ("secretaria-de-gobernacion", "Rosa Icela Rodríguez Velázquez", "Secretaria de Gobernación",
     "2024-10-01", 0.95,
     "https://www.gob.mx/presidencia/articulos/version-estenografica-desfile-civico-militar-216-aniversario-de-la-independencia",
     "123bdfaf9584c47673fc87ba918f447972722ad289e12030a10930ff7cf4eb3f", 104022,
     "Versión estenográfica. Desfile Cívico Militar, 216 Aniversario de la Independencia"),
    ("secretaria-de-relaciones-exteriores", "Roberto Velasco Álvarez", "Secretario de Relaciones Exteriores",
     "2026-04-01", 0.98,
     "https://www.gob.mx/sre/estructuras/roberto-velasco-alvarez",
     "7a5b5bd4951e64081e856a48c5a8308f0b3596c218a97907a5ae99fc5ea479fa", 34424,
     "Directorio de la Secretaría de Relaciones Exteriores"),
    ("secretaria-de-la-defensa-nacional", "Ricardo Trevilla Trejo", "Secretario de la Defensa Nacional",
     "2024-10-01", 0.98,
     "https://www.gob.mx/defensa/estructuras/general-ricardo-trevilla-trejo",
     "bcadb435c1a2da7f086592940b4eea877d06112a5b8451403faae0c9be4f3bb0", 39149,
     "Directorio de la Secretaría de la Defensa Nacional"),
    ("secretaria-de-marina", "Raymundo Pedro Morales Ángeles", "Secretario de Marina",
     "2024-10-01", 0.98,
     "https://www.gob.mx/semar/estructuras/almirante-raymundo-pedro-morales-angeles",
     "bb468c20fa578172815d3eeb6dd790accc9b0ef55bf4cbe303cc660ccf66a5cf", 36369,
     "Directorio de la Secretaría de Marina"),
    ("secretaria-de-seguridad-y-proteccion-ciudadana", "Omar García Harfuch",
     "Secretario de Seguridad y Protección Ciudadana", "2024-10-01", 0.95,
     "https://www.gob.mx/sspc/prensa/mensaje-del-mtro-omar-garcia-harfuch-durante-la-ceremonia-de-entrega-recepcion-de-la-titularidad-de-la-sspc",
     "4fe258f3acc0ae4ce6ebdd59853a2b2a416591979c11a88bd8f93dff02f3f2fd", 59586,
     "Ceremonia de entrega-recepción de la titularidad de la SSPC"),
    ("secretaria-de-hacienda-y-credito-publico", "Édgar Amador Zamora",
     "Secretario de Hacienda y Crédito Público", "2025-03-08", 0.98,
     "https://www.gob.mx/hacienda/estructuras/edgar-amador-zamora",
     "43f2bf41e178659c517f65230241a13b1d9020e6e6e5ea88f2922e2d3a55ffbf", 32796,
     "Directorio de la Secretaría de Hacienda y Crédito Público"),
    ("secretaria-de-bienestar", "Leticia Ramírez Amaya", "Secretaria de Bienestar",
     "2026-05-01", 0.90,
     "https://www.gob.mx/bienestar/prensa/bienestar-realiza-la-entrega-de-tarjetas-de-las-pensiones-para-adultos-mayores-y-mujeres-bienestar-leticia-ramirez",
     "8107d80b4157a53952bdfeab98b45ab41dd6548137a76f1b57387fb674c840c9", 56932,
     "Comunicado de la Secretaría de Bienestar"),
    ("secretaria-de-infraestructura-comunicaciones-y-transportes", "Jesús Antonio Esteva Medina",
     "Secretario de Infraestructura, Comunicaciones y Transportes", "2024-10-01", 0.98,
     "https://www.gob.mx/sict/estructuras/jesus-antonio-esteva-medina",
     "897b9573ff7c6fb0caed14d45c01ae9a1d883628c378b719f09fcb8c5f514f4d", 35016,
     "Directorio de la Secretaría de Infraestructura, Comunicaciones y Transportes"),
    ("secretaria-de-medio-ambiente-y-recursos-naturales", "Alicia Bárcena Ibarra",
     "Secretaria de Medio Ambiente y Recursos Naturales", "2024-10-01", 0.95,
     "https://www.gob.mx/semarnat/prensa/2026-es-un-ano-de-oportunidades-para-avanzar-en-el-sector-ambiental-alicia-barcena",
     "8c8b58b8b378884603ced9bc87669448fecf2662155b6da2126027d89582c0fb", 62381,
     "Comunicado de la Secretaría de Medio Ambiente y Recursos Naturales"),
    ("secretaria-de-energia", "Luz Elena González Escobar", "Secretaria de Energía",
     "2024-10-01", 0.98,
     "https://www.gob.mx/sener/estructuras/luz-elena-gonzalez-escobar",
     "544c8a2c34e131225248e644b0e4f7635b4e63904bfaf6193e76098a12b88c35", 32918,
     "Directorio de la Secretaría de Energía"),
    ("secretaria-de-economia", "Marcelo Ebrard Casaubon", "Secretario de Economía",
     "2024-10-01", 0.98,
     "https://www.gob.mx/se/estructuras/marcelo-ebrard",
     "d54448dbbf8c5ffd37cbba9c7ddec79e0f4ac4a19a1f0e9f9f1fde4a9bfd97f9", 32988,
     "Directorio de la Secretaría de Economía"),
    ("secretaria-de-agricultura-y-desarrollo-rural", "Columba Jazmín López Gutiérrez",
     "Secretaria de Agricultura y Desarrollo Rural", "2026-05-01", 0.95,
     "https://www.gob.mx/agricultura/prensa/columba-lopez-nueva-secretaria-de-agricultura-y-desarrollo-rural-julio-berdegue-apoyara-en-temas-internacionales-del-campo-425046",
     "25b5a196b0fc87a288287d62570bc22ffb341f331a3032f4e67b8beacc3904cc", 56926,
     "Comunicado de la Secretaría de Agricultura y Desarrollo Rural"),
    ("secretaria-de-educacion-publica", "Mario Delgado Carrillo", "Secretario de Educación Pública",
     "2024-10-01", 0.98,
     "https://www.gob.mx/sep/estructuras/mario-delgado-carrillo",
     "cf64cda7b75ba2e66a7953b1f13656cab5978394f8f33392b726d14a558fa9a9", 34993,
     "Directorio de la Secretaría de Educación Pública"),
    ("secretaria-de-salud", "David Kershenobich Stalnikowitz", "Secretario de Salud",
     "2024-10-01", 0.98,
     "https://www.gob.mx/salud/estructuras/dr-david-kershenobich-stalnikowitz",
     "42b89e1d262ab2298f152936c7cde1834a5e38ba158d5e45f0e00348875ac587", 34563,
     "Directorio de la Secretaría de Salud"),
    ("secretaria-del-trabajo-y-prevision-social", "Marath Baruch Bolaños López",
     "Secretario del Trabajo y Previsión Social", "2024-10-01", 0.95,
     "https://www.gob.mx/stps/estructuras/marath-baruch-bolanos-lopez",
     "8ac6279122c57ff7706ef607d348ed8373c6f7123c0fae7c367333d722c95b65", 33968,
     "Directorio de la Secretaría del Trabajo y Previsión Social"),
    ("secretaria-de-desarrollo-agrario-territorial-y-urbano", "Edna Elena Vega Rangel",
     "Secretaria de Desarrollo Agrario, Territorial y Urbano", "2024-10-01", 0.98,
     "https://www.gob.mx/sedatu/estructuras/edna-elena-vega-rangel",
     "8b480e6bfeb4db581245c825d28bee0bfedc44a99527426ab5964d02c46d8073", 34540,
     "Directorio de la Secretaría de Desarrollo Agrario, Territorial y Urbano"),
    ("secretaria-de-cultura", "Claudia Curiel de Icaza", "Secretaria de Cultura",
     "2024-10-01", 0.98,
     "https://www.gob.mx/cultura/estructuras/claudia-curiel-de-icaza",
     "2203b489754f41cd5c191f62bb24cf1b00b7a562273532bebf237a9396c29a26", 35219,
     "Directorio de la Secretaría de Cultura"),
    ("secretaria-de-turismo", "Josefina Rodríguez Zamora", "Secretaria de Turismo",
     "2024-10-01", 0.98,
     "https://www.gob.mx/sectur/estructuras/josefina-rodriguez-zamora",
     "481e0b032b9dd2c4aa0752273914a52ea32dbdf16c7ba0b381843e64dbba0983", 35332,
     "Directorio de la Secretaría de Turismo"),
    ("secretaria-de-ciencia-humanidades-tecnologia-e-innovacion", "Rosaura Ruiz Gutiérrez",
     "Secretaria de Ciencia, Humanidades, Tecnología e Innovación", "2024-10-01", 0.95,
     "https://www.gob.mx/inafed/articulos/reunion-de-trabajo-presidida-por-la-dra-rosaura-ruiz-gutierrez-titular-de-la-secretaria-de-ciencia-tecnologia-humanidades-e-innovacion",
     "2b62f395755d5b3ac43d38f0e45a659084a910ca9613a6330db4f1bb61584f72", 54444,
     "Comunicado oficial que identifica a la titular de la SECIHTI"),
    ("secretaria-anticorrupcion-y-buen-gobierno", "Raquel Buenrostro Sánchez",
     "Secretaria Anticorrupción y Buen Gobierno", "2024-10-01", 0.95,
     "https://www.gob.mx/buengobierno/galerias/2026-feb-27-la-secretaria-anticorrupcion-y-buen-gobierno-raquel-buenrostro-se-reune-con-el-secretario-general-de-la-ocde-mathias-cormann",
     "cb8abd4a84616abf1785ec7c447acf97de75626645f4e275b53195957eed23a6", 39677,
     "Galería oficial de la Secretaría Anticorrupción y Buen Gobierno"),
    ("secretaria-de-las-mujeres", "Laura Itzel Castillo Juárez", "Secretaria de las Mujeres",
     "2026-09-01", 0.90,
     "https://www.gob.mx/mujeres/estructuras/laura-itzel-castillo-juarez",
     "d2f2727fcb97f63ec02c38f583decac8ef89d6909b9042fb1d18c119a4826686", 34794,
     "Directorio de la Secretaría de las Mujeres"),
]

# Titularidades que el editor da por ciertas pero de las que no se localizó una
# página oficial vigente que las nombre. Se publican con evidencia que declara
# exactamente eso —una atestiguación editorial firmada y fechada, no un
# documento de gobierno— y con `trust_tier` inferior, de modo que una auditoría
# las distinga de las 21 respaldadas por la fuente oficial. Inventar una URL o
# un hash de gob.mx para que parecieran equivalentes sí corrompería el modelo.
#
# (slug de la dependencia, persona, cargo, tipo de cargo, fecha de inicio, confianza)
ATTESTED = [
    ("agencia-de-transformacion-digital-y-telecomunicaciones", "José Antonio Peña Merino",
     "Titular de la Agencia de Transformación Digital y Telecomunicaciones", "agency_head",
     "2025-01-01", 0.80),
    ("consejeria-juridica-del-ejecutivo-federal", "Luisa María Alcalde Luján",
     "Consejera Jurídica del Ejecutivo Federal", "legal_counsel", "2026-05-04", 0.85),
    ("presidencia-de-la-republica", "Lázaro Cárdenas Batel",
     "Jefe de la Oficina de la Presidencia de la República", "chief_of_staff", "2024-10-01", 0.85),
]

ATTESTATION_URN = "urn:mapapoder:atestiguacion-editorial:2026-09-18"
ATTESTED_BY = "juan.carvajal@corexcorp.com"

# Las juntas y consejos se cargaron sin arista hacia su órgano, así que el mapa
# no podía llegar de "Banco de México" a su gobernadora. La evidencia es el
# mismo directorio oficial ya descargado por el worker.
COLLEGIATE_PARENTS = [
    ("Junta de Gobierno del Banco de México", "banco-de-mexico", "directorio_banxico_junta"),
    ("Consejo General del Instituto Nacional Electoral", "instituto-nacional-electoral", "directorio_ine_consejo"),
    ("Junta de Gobierno del INEGI", "instituto-nacional-de-estadistica-y-geografia", "directorio_inegi_junta"),
    ("Sala Superior del Tribunal Electoral del Poder Judicial de la Federación",
     "tribunal-electoral-del-poder-judicial", "directorio_tepjf_sala_superior"),
]


def name_parts(label: str) -> tuple[str, str]:
    parts = label.split()
    if len(parts) < 3:
        return label, ""
    return " ".join(parts[:-2]), " ".join(parts[-2:])


def node_id_for(cursor: psycopg.Cursor, slug: str) -> str | None:
    cursor.execute("SELECT id::text FROM nodes WHERE slug = %s", (slug,))
    row = cursor.fetchone()
    return row[0] if row else None


def load_cabinet(cursor: psycopg.Cursor) -> dict:
    counts = {"personas": 0, "cargos": 0, "tenencias": 0, "relaciones": 0, "afirmaciones": 0, "sin_dependencia": []}
    for org_slug, person, role, valid_from, confidence, url, digest, byte_size, title in CABINET:
        organization_id = node_id_for(cursor, org_slug)
        if not organization_id:
            counts["sin_dependencia"].append(org_slug)
            continue

        doc_slug = f"gabinete_{org_slug}"
        document_id = stable_id(f"source-document/{doc_slug}")
        cursor.execute(
            """
            INSERT INTO source_documents (id, slug, publisher, title, canonical_url, source_type, trust_tier, enabled)
            VALUES (%s, %s, 'Gobierno de México', %s, %s, 'official_profile', 'A', true)
            ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, canonical_url = EXCLUDED.canonical_url
            RETURNING id::text
            """,
            (document_id, doc_slug, title, url),
        )
        document_id = cursor.fetchone()[0]

        snapshot_id = stable_id(f"snapshot/{doc_slug}/{digest}")
        cursor.execute(
            """
            INSERT INTO source_snapshots (
              id, source_document_id, retrieved_at, final_url, content_hash,
              mime_type, byte_size, storage_path, http_status, diff_summary
            )
            VALUES (%s, %s, %s, %s, %s, 'text/html', %s, %s, 200, %s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (snapshot_id, document_id, datetime.now(timezone.utc), url, digest, byte_size,
             "sin-archivo-local:fuente-no-descargable-por-el-worker",
             json.dumps({
                 "capture": "navegador",
                 "note": ("Recuperado y verificado desde un navegador real; la fuente responde con "
                          "desafío anti-bot al cliente HTTP del worker, por lo que no hay copia local."),
             })),
        )

        fragment_id = stable_id(f"fragment/{doc_slug}/{digest}")
        excerpt = f"{person} — {role}"
        cursor.execute(
            """
            INSERT INTO source_fragments (id, snapshot_id, locator, fragment_text, fragment_hash, metadata)
            VALUES (%s, %s, 'Ficha de titular', %s, %s, '{}'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (fragment_id, snapshot_id, excerpt, sha256(excerpt.encode()).hexdigest()),
        )

        publish_titular(
            cursor, org_slug, organization_id, person, role, "secretariat_head",
            valid_from, confidence, url, fragment_id, "curated_manual_review",
            "Ficha o comunicado oficial de la dependencia.", url, counts,
        )
    return counts


def publish_titular(
    cursor: psycopg.Cursor, org_slug: str, organization_id: str, person: str, role: str,
    position_type: str, valid_from: str, confidence: float, identity: str, fragment_id: str,
    extraction_method: str, evidence_note: str, profile_url: str | None, counts: dict,
) -> None:
    """Materializa persona, cargo, relación, afirmación, evidencia y tenencia."""
    person_slug = slugify(person)
    person_node = stable_id(f"node/person/{identity}")
    cursor.execute(
        """
        INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
        VALUES (%s, %s, 'person', %s, %s, '', 'public_official', 'executive', daterange(NULL, NULL, '[)'), %s::jsonb)
        ON CONFLICT (slug) DO UPDATE SET canonical_name = EXCLUDED.canonical_name
        RETURNING id::text, (xmax = 0)
        """,
        (person_node, person_slug, person, person,
         json.dumps({"jurisdiction": "Federal", "identityKey": identity})),
    )
    person_node, inserted = cursor.fetchone()
    counts["personas"] += int(inserted)
    given, family = name_parts(person)
    cursor.execute(
        """
        INSERT INTO persons (node_id, given_names, family_names, official_profile_url)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (node_id) DO UPDATE SET official_profile_url = COALESCE(EXCLUDED.official_profile_url, persons.official_profile_url)
        """,
        (person_node, given, family, profile_url),
    )

    position_slug = f"titular-{org_slug}"
    position_node = stable_id(f"node/position/{position_slug}")
    cursor.execute(
        """
        INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during, metadata)
        VALUES (%s, %s, 'position', %s, %s, '', 'public_office', 'executive', daterange(NULL, NULL, '[)'), %s::jsonb)
        ON CONFLICT (slug) DO UPDATE SET canonical_name = EXCLUDED.canonical_name
        RETURNING id::text, (xmax = 0)
        """,
        (position_node, position_slug, role, role, '{"jurisdiction": "Federal", "occupancyStatus": "confirmed"}'),
    )
    position_node, inserted = cursor.fetchone()
    counts["cargos"] += int(inserted)
    cursor.execute(
        """
        INSERT INTO positions (node_id, organization_id, position_type, selection_method, is_elected, is_collegial, metadata)
        VALUES (%s, %s, %s, 'presidential_appointment', false, false, '{}'::jsonb)
        ON CONFLICT (node_id) DO UPDATE SET organization_id = EXCLUDED.organization_id
        """,
        (position_node, organization_id, position_type),
    )

    relationship_id = stable_id(f"relationship/holds/{position_slug}/{person_slug}")
    cursor.execute(
        """
        INSERT INTO relationships (id, slug, relationship_type, relationship_class, source_node_id,
          target_node_id, label, description, valid_during, metadata)
        VALUES (%s, %s, 'HOLDS', 'tenure', %s, %s, %s, %s, daterange(%s::date, NULL, '[)'), '{}'::jsonb)
        ON CONFLICT (slug) DO NOTHING
        RETURNING id::text
        """,
        (relationship_id, f"rel-holds-{position_slug}", person_node, position_node,
         f"{person} ocupa {role}", f"{person} es titular de la dependencia.", valid_from),
    )
    if cursor.fetchone():
        counts["relaciones"] += 1

    assertion_id = stable_id(f"assertion/holds/{position_slug}/{person_slug}")
    cursor.execute(
        """
        INSERT INTO assertions (id, assertion_type, subject_node_id, predicate, object_node_id,
          relationship_id, valid_during, observed_at, extraction_method, confidence, status,
          reviewed_by, reviewed_at, published_at)
        VALUES (%s, 'relationship', %s, 'HOLDS', %s, %s, daterange(%s::date, NULL, '[)'), now(),
                %s, %s, 'published', %s, now(), now())
        ON CONFLICT (id) DO NOTHING
        RETURNING id::text
        """,
        (assertion_id, person_node, position_node, relationship_id, valid_from,
         extraction_method, confidence, REVIEWER),
    )
    if cursor.fetchone():
        counts["afirmaciones"] += 1
    cursor.execute(
        """
        INSERT INTO evidence_links (assertion_id, source_fragment_id, supports, note)
        VALUES (%s, %s, true, %s)
        ON CONFLICT (assertion_id, source_fragment_id) DO NOTHING
        """,
        (assertion_id, fragment_id, evidence_note),
    )

    tenure_id = stable_id(f"tenure/{position_slug}/{person_slug}")
    cursor.execute(
        """
        INSERT INTO tenures (id, person_id, position_id, status, selection_method, valid_during)
        VALUES (%s, %s, %s, 'confirmed', 'presidential_appointment', daterange(%s::date, NULL, '[)'))
        ON CONFLICT (id) DO NOTHING
        RETURNING id::text
        """,
        (tenure_id, person_node, position_node, valid_from),
    )
    if cursor.fetchone():
        counts["tenencias"] += 1


def load_attested(cursor: psycopg.Cursor) -> dict:
    """Publica titularidades que el editor sostiene sin ficha oficial localizada.

    La evidencia es la atestiguación misma: su texto es el contenido del
    snapshot y su hash es el de ese texto, así que la cadena documento →
    snapshot → fragmento es interna y verificable, sin simular un documento de
    gobierno que no se pudo recuperar.
    """
    counts = {"personas": 0, "cargos": 0, "tenencias": 0, "relaciones": 0, "afirmaciones": 0, "sin_dependencia": []}
    statement = (
        "Atestiguación editorial de titularidades del Ejecutivo Federal cuya ficha oficial "
        f"no fue localizada al {OBSERVED_ON.isoformat()}. Declarada por {ATTESTED_BY}. "
        "Pendiente de sustituirse por evidencia documental oficial."
    )
    document_id = stable_id("source-document/atestiguacion_editorial_gabinete")
    cursor.execute(
        """
        INSERT INTO source_documents (id, slug, publisher, title, canonical_url, source_type, trust_tier, enabled)
        VALUES (%s, 'atestiguacion_editorial_gabinete', %s,
                'Atestiguación editorial de titularidades sin ficha oficial localizada',
                %s, 'editorial_attestation', 'C', true)
        ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title
        RETURNING id::text
        """,
        (document_id, ATTESTED_BY, ATTESTATION_URN),
    )
    document_id = cursor.fetchone()[0]

    digest = sha256(statement.encode()).hexdigest()
    snapshot_id = stable_id(f"snapshot/atestiguacion_editorial/{digest}")
    cursor.execute(
        """
        INSERT INTO source_snapshots (id, source_document_id, retrieved_at, final_url, content_hash,
          mime_type, byte_size, storage_path, http_status, diff_summary)
        VALUES (%s, %s, now(), %s, %s, 'text/plain', %s, %s, 200, %s::jsonb)
        ON CONFLICT (id) DO NOTHING
        """,
        (snapshot_id, document_id, ATTESTATION_URN, digest, len(statement.encode()), ATTESTATION_URN,
         json.dumps({"capture": "atestiguacion-editorial", "note": statement})),
    )

    for org_slug, person, role, position_type, valid_from, confidence in ATTESTED:
        organization_id = node_id_for(cursor, org_slug)
        if not organization_id:
            counts["sin_dependencia"].append(org_slug)
            continue
        excerpt = f"{person} — {role}. {statement}"
        fragment_id = stable_id(f"fragment/atestiguacion/{org_slug}")
        cursor.execute(
            """
            INSERT INTO source_fragments (id, snapshot_id, locator, fragment_text, fragment_hash, metadata)
            VALUES (%s, %s, 'Atestiguación editorial', %s, %s, '{}'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (fragment_id, snapshot_id, excerpt, sha256(excerpt.encode()).hexdigest()),
        )
        publish_titular(
            cursor, org_slug, organization_id, person, role, position_type, valid_from, confidence,
            f"atestiguacion:{slugify(person)}", fragment_id, "editorial_attestation",
            "Atestiguación editorial: sin ficha oficial localizada. Sustituir cuando exista documento.",
            None, counts,
        )
    return counts


def link_collegiate_bodies(cursor: psycopg.Cursor) -> int:
    linked = 0
    for label, parent_slug, source_slug in COLLEGIATE_PARENTS:
        child_id = node_id_for(cursor, slugify(label))
        parent_id = node_id_for(cursor, parent_slug)
        if not child_id or not parent_id:
            continue
        cursor.execute(
            """
            SELECT sf.id::text FROM source_fragments sf
            JOIN source_snapshots ss ON ss.id = sf.snapshot_id
            JOIN source_documents sd ON sd.id = ss.source_document_id
            WHERE sd.slug = %s LIMIT 1
            """,
            (source_slug,),
        )
        fragment = cursor.fetchone()
        relationship_id = stable_id(f"relationship/part_of/{child_id}/{parent_id}")
        cursor.execute(
            """
            INSERT INTO relationships (id, slug, relationship_type, relationship_class, source_node_id,
              target_node_id, label, description, valid_during, metadata)
            VALUES (%s, %s, 'PART_OF', 'structure', %s, %s, %s, %s, daterange(NULL, NULL, '[)'), '{}'::jsonb)
            ON CONFLICT (slug) DO NOTHING
            RETURNING id::text
            """,
            (relationship_id, f"rel-part-of-{slugify(label)}", child_id, parent_id,
             f"{label} forma parte del órgano", "Órgano colegiado de gobierno de la institución."),
        )
        if not cursor.fetchone():
            continue
        assertion_id = stable_id(f"assertion/part_of/{child_id}/{parent_id}")
        cursor.execute(
            """
            INSERT INTO assertions (id, assertion_type, subject_node_id, predicate, object_node_id,
              relationship_id, valid_during, observed_at, extraction_method, confidence, status,
              reviewed_by, reviewed_at, published_at)
            VALUES (%s, 'relationship', %s, 'PART_OF', %s, %s, daterange(NULL, NULL, '[)'), now(),
                    'curated_manual_review', 0.98, 'published', %s, now(), now())
            ON CONFLICT (id) DO NOTHING
            """,
            (assertion_id, child_id, parent_id, relationship_id, REVIEWER),
        )
        if fragment:
            cursor.execute(
                """
                INSERT INTO evidence_links (assertion_id, source_fragment_id, supports, note)
                VALUES (%s, %s, true, 'Directorio oficial del órgano colegiado.')
                ON CONFLICT (assertion_id, source_fragment_id) DO NOTHING
                """,
                (assertion_id, fragment[0]),
            )
        linked += 1
    return linked


def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        counts = load_cabinet(cursor)
        attested = load_attested(cursor)
        for field in ("personas", "cargos", "tenencias", "relaciones", "afirmaciones"):
            counts[field] += attested[field]
        counts["sin_dependencia"] += attested["sin_dependencia"]
        counts["atestiguados"] = len(ATTESTED) - len(attested["sin_dependencia"])
        counts["colegiados_enlazados"] = link_collegiate_bodies(cursor)
    print(counts)


if __name__ == "__main__":
    main()
