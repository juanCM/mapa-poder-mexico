BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE persons
  ADD COLUMN IF NOT EXISTS official_portrait_url text,
  ADD COLUMN IF NOT EXISTS portrait_source_document_id uuid REFERENCES source_documents(id);

ALTER TABLE positions
  ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'persons_portrait_requires_official_source'
  ) THEN
    ALTER TABLE persons
      ADD CONSTRAINT persons_portrait_requires_official_source
      CHECK (
        official_portrait_url IS NULL
        OR (official_profile_url IS NOT NULL AND portrait_source_document_id IS NOT NULL)
      ) NOT VALID;
  END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS review_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingestion_run_id uuid NOT NULL UNIQUE REFERENCES ingestion_runs(id) ON DELETE RESTRICT,
  title text NOT NULL,
  status text NOT NULL DEFAULT 'needs_review'
    CHECK (status IN ('needs_review', 'partially_reviewed', 'approved', 'rejected', 'published')),
  decided_by text,
  decision_note text,
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE review_tasks
  ADD COLUMN IF NOT EXISTS batch_id uuid REFERENCES review_batches(id) ON DELETE RESTRICT;

INSERT INTO review_batches (ingestion_run_id, title, status, created_at)
SELECT ir.id,
       'Lote ' || ir.adapter_key || ' · ' || to_char(ir.created_at, 'YYYY-MM-DD HH24:MI'),
       CASE
         WHEN bool_and(rt.status = 'published') THEN 'published'
         WHEN bool_and(rt.status = 'approved') THEN 'approved'
         WHEN bool_and(rt.status = 'rejected') THEN 'rejected'
         WHEN bool_or(rt.status <> 'needs_review') THEN 'partially_reviewed'
         ELSE 'needs_review'
       END,
       ir.created_at
FROM ingestion_runs ir
JOIN review_tasks rt ON rt.ingestion_run_id = ir.id
GROUP BY ir.id
ON CONFLICT (ingestion_run_id) DO NOTHING;

UPDATE review_tasks rt
SET batch_id = rb.id
FROM review_batches rb
WHERE rt.ingestion_run_id = rb.ingestion_run_id
  AND rt.batch_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS tenures_identity_idx
  ON tenures (person_id, position_id, valid_during);
CREATE INDEX IF NOT EXISTS tenures_position_valid_idx
  ON tenures USING gist (position_id, valid_during);
CREATE INDEX IF NOT EXISTS positions_organization_idx
  ON positions (organization_id);
CREATE INDEX IF NOT EXISTS review_tasks_batch_status_idx
  ON review_tasks (batch_id, status, created_at);
CREATE INDEX IF NOT EXISTS relationships_active_source_idx
  ON relationships (source_node_id, relationship_type) WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS relationships_active_target_idx
  ON relationships (target_node_id, relationship_type) WHERE retired_at IS NULL;

INSERT INTO tenures (person_id, position_id, status, selection_method, valid_during, recorded_at)
SELECT r.source_node_id,
       r.target_node_id,
       COALESCE(r.metadata->>'occupancyStatus', 'confirmed'),
       p.selection_method,
       r.valid_during,
       r.recorded_at
FROM published_relationships r
JOIN persons pe ON pe.node_id = r.source_node_id
JOIN positions p ON p.node_id = r.target_node_id
WHERE r.relationship_type = 'HOLDS'
ON CONFLICT (person_id, position_id, valid_during) DO NOTHING;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tenures_no_active_overlap'
  ) THEN
    ALTER TABLE tenures
      ADD CONSTRAINT tenures_no_active_overlap
      EXCLUDE USING gist (position_id WITH =, valid_during WITH &&)
      WHERE (retired_at IS NULL);
  END IF;
END;
$$;

CREATE OR REPLACE VIEW power_map_integrity_violations AS
SELECT 'published_relationship_without_evidence'::text AS issue,
       r.id::text AS entity_id,
       r.slug AS detail
FROM published_relationships r
WHERE NOT EXISTS (
  SELECT 1
  FROM assertions a
  JOIN evidence_links el ON el.assertion_id = a.id AND el.supports
  WHERE a.relationship_id = r.id AND a.status = 'published'
)
UNION ALL
SELECT 'portrait_without_official_profile_or_source', p.node_id::text, n.slug
FROM persons p
JOIN nodes n ON n.id = p.node_id
WHERE p.official_portrait_url IS NOT NULL
  AND (p.official_profile_url IS NULL OR p.portrait_source_document_id IS NULL)
UNION ALL
SELECT 'constitutional_seat_count', o.node_id::text,
       n.slug || ': ' || COUNT(pos.node_id)::text || ' de ' ||
       CASE WHEN n.slug = 'camara-de-diputados' THEN '500' ELSE '128' END
FROM organizations o
JOIN nodes n ON n.id = o.node_id
LEFT JOIN positions pos ON pos.organization_id = o.node_id
WHERE n.slug IN ('camara-de-diputados', 'senado-de-la-republica')
GROUP BY o.node_id, n.slug
HAVING COUNT(pos.node_id) <> CASE WHEN n.slug = 'camara-de-diputados' THEN 500 ELSE 128 END;

ALTER TABLE persons VALIDATE CONSTRAINT persons_portrait_requires_official_source;

COMMIT;
