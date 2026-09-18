-- Corrige el término de la Presidencia de la SCJN de Hugo Aguilar Ortiz.
--
-- La presidencia es rotatoria cada dos años desde el 1 de septiembre de 2025 y
-- concluye el 31 de agosto de 2027. Con semántica `[inicio, fin)` el límite
-- superior es 2027-09-01; la base tenía 2027-10-01, un mes de más.
--
-- Una afirmación publicada es inmutable: la corrección crea otra que la
-- sustituye mediante `supersedes_assertion_id` y hereda su evidencia. La
-- anterior se marca `superseded`, no se borra.

BEGIN;

INSERT INTO assertions (
  assertion_type, subject_node_id, predicate, object_node_id, literal_value,
  relationship_id, valid_during, observed_at, extraction_method, extractor_version,
  confidence, status, supersedes_assertion_id, reviewed_by, reviewed_at, published_at
)
SELECT
  a.assertion_type, a.subject_node_id, a.predicate, a.object_node_id, a.literal_value,
  a.relationship_id, daterange('2025-09-01', '2027-09-01', '[)'), now(),
  a.extraction_method, a.extractor_version, a.confidence, 'published', a.id,
  'auditoria-editorial', now(), now()
FROM assertions a
JOIN nodes p ON p.id = a.subject_node_id
WHERE p.slug = 'hugo-aguilar-ortiz'
  AND a.predicate = 'HOLDS'
  AND a.status = 'published'
  AND NOT EXISTS (
    SELECT 1 FROM assertions corrected
    WHERE corrected.supersedes_assertion_id = a.id
  );

INSERT INTO evidence_links (assertion_id, source_fragment_id, legal_provision_id, supports, note)
SELECT corrected.id, el.source_fragment_id, el.legal_provision_id, el.supports, el.note
FROM assertions corrected
JOIN evidence_links el ON el.assertion_id = corrected.supersedes_assertion_id
JOIN nodes p ON p.id = corrected.subject_node_id
WHERE p.slug = 'hugo-aguilar-ortiz' AND corrected.predicate = 'HOLDS'
ON CONFLICT (assertion_id, source_fragment_id) DO NOTHING;

UPDATE assertions
SET status = 'superseded'
WHERE id IN (
  SELECT corrected.supersedes_assertion_id
  FROM assertions corrected
  JOIN nodes p ON p.id = corrected.subject_node_id
  WHERE p.slug = 'hugo-aguilar-ortiz'
    AND corrected.predicate = 'HOLDS'
    AND corrected.status = 'published'
    AND corrected.supersedes_assertion_id IS NOT NULL
);

UPDATE relationships r
SET valid_during = daterange('2025-09-01', '2027-09-01', '[)')
FROM nodes p
WHERE p.id = r.source_node_id
  AND p.slug = 'hugo-aguilar-ortiz'
  AND r.relationship_type = 'HOLDS';

UPDATE tenures t
SET valid_during = daterange('2025-09-01', '2027-09-01', '[)')
FROM nodes p
WHERE p.id = t.person_id AND p.slug = 'hugo-aguilar-ortiz';

COMMIT;
