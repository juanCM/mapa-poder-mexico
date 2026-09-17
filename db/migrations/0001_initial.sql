BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TYPE node_kind AS ENUM ('jurisdiction', 'organization', 'unit', 'position', 'person');
CREATE TYPE assertion_status AS ENUM ('discovered', 'parsed', 'needs_review', 'approved', 'published', 'rejected', 'superseded', 'failed');
CREATE TYPE review_priority AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE ingestion_status AS ENUM ('queued', 'running', 'succeeded', 'failed', 'partial');

CREATE TABLE nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  kind node_kind NOT NULL,
  canonical_name text NOT NULL,
  short_name text,
  description text NOT NULL DEFAULT '',
  jurisdiction_id uuid REFERENCES nodes(id),
  category text NOT NULL,
  branch text NOT NULL,
  valid_during daterange NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  retired_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (NOT isempty(valid_during))
);

CREATE TABLE jurisdictions (
  node_id uuid PRIMARY KEY REFERENCES nodes(id) ON DELETE RESTRICT,
  jurisdiction_type text NOT NULL,
  parent_id uuid REFERENCES jurisdictions(node_id),
  inegi_code text
);

CREATE TABLE organizations (
  node_id uuid PRIMARY KEY REFERENCES nodes(id) ON DELETE RESTRICT,
  organization_type text NOT NULL,
  legal_status text,
  website text
);

CREATE TABLE organizational_units (
  node_id uuid PRIMARY KEY REFERENCES nodes(id) ON DELETE RESTRICT,
  organization_id uuid NOT NULL REFERENCES organizations(node_id),
  parent_unit_id uuid REFERENCES organizational_units(node_id),
  unit_type text NOT NULL
);

CREATE TABLE positions (
  node_id uuid PRIMARY KEY REFERENCES nodes(id) ON DELETE RESTRICT,
  organization_id uuid NOT NULL REFERENCES organizations(node_id),
  unit_id uuid REFERENCES organizational_units(node_id),
  position_type text NOT NULL,
  seat_number integer,
  selection_method text,
  term_months integer,
  term_limit integer,
  is_elected boolean NOT NULL DEFAULT false,
  is_collegial boolean NOT NULL DEFAULT false
);

CREATE TABLE persons (
  node_id uuid PRIMARY KEY REFERENCES nodes(id) ON DELETE RESTRICT,
  given_names text NOT NULL,
  family_names text NOT NULL,
  birth_date date,
  official_profile_url text,
  wikidata_id text
);

CREATE TABLE tenures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL REFERENCES persons(node_id),
  position_id uuid NOT NULL REFERENCES positions(node_id),
  status text NOT NULL,
  selection_method text,
  valid_during daterange NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  retired_at timestamptz,
  predecessor_id uuid REFERENCES tenures(id),
  superseded_by_id uuid REFERENCES tenures(id),
  CHECK (NOT isempty(valid_during))
);

CREATE TABLE memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL REFERENCES persons(node_id),
  organization_id uuid NOT NULL REFERENCES organizations(node_id),
  role text NOT NULL,
  valid_during daterange NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  retired_at timestamptz,
  CHECK (NOT isempty(valid_during))
);

CREATE TABLE procedures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  name text NOT NULL,
  procedure_type text NOT NULL,
  description text NOT NULL,
  valid_during daterange NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE procedure_steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  procedure_id uuid NOT NULL REFERENCES procedures(id) ON DELETE CASCADE,
  step_number integer NOT NULL,
  actor_id uuid NOT NULL REFERENCES nodes(id),
  action_type text NOT NULL,
  target_id uuid REFERENCES nodes(id),
  required_threshold text,
  condition text,
  UNIQUE (procedure_id, step_number)
);

CREATE TABLE relationships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  relationship_type text NOT NULL,
  relationship_class text NOT NULL CHECK (relationship_class IN ('structure', 'power', 'competence', 'accountability', 'tenure')),
  source_node_id uuid NOT NULL REFERENCES nodes(id),
  target_node_id uuid NOT NULL REFERENCES nodes(id),
  label text NOT NULL,
  description text NOT NULL,
  policy_domain text,
  condition text,
  procedure_id uuid REFERENCES procedures(id),
  valid_during daterange NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  retired_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (source_node_id <> target_node_id),
  CHECK (NOT isempty(valid_during))
);

CREATE TABLE legal_instruments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instrument_type text NOT NULL,
  title text NOT NULL,
  jurisdiction_id uuid REFERENCES jurisdictions(node_id),
  publication_date date,
  effective_date date,
  repeal_date date,
  official_identifier text,
  dof_url text,
  canonical_url text NOT NULL,
  version_label text
);

CREATE TABLE legal_provisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_instrument_id uuid NOT NULL REFERENCES legal_instruments(id),
  article text,
  section text,
  paragraph text,
  fraction text,
  subsection text,
  provision_text text,
  valid_during daterange NOT NULL,
  CHECK (NOT isempty(valid_during))
);

CREATE TABLE source_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  publisher text NOT NULL,
  title text NOT NULL,
  canonical_url text NOT NULL,
  source_type text NOT NULL,
  publication_date date,
  trust_tier char(1) NOT NULL DEFAULT 'A',
  adapter_key text,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE source_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_document_id uuid NOT NULL REFERENCES source_documents(id),
  retrieved_at timestamptz NOT NULL,
  final_url text NOT NULL,
  content_hash text NOT NULL,
  mime_type text NOT NULL,
  byte_size bigint NOT NULL,
  storage_path text NOT NULL,
  http_status integer NOT NULL,
  previous_snapshot_id uuid REFERENCES source_snapshots(id),
  diff_summary jsonb,
  UNIQUE (source_document_id, content_hash)
);

CREATE TABLE source_fragments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_id uuid NOT NULL REFERENCES source_snapshots(id),
  locator text NOT NULL,
  fragment_text text NOT NULL,
  fragment_hash text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE assertions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assertion_type text NOT NULL,
  subject_node_id uuid REFERENCES nodes(id),
  predicate text NOT NULL,
  object_node_id uuid REFERENCES nodes(id),
  literal_value jsonb,
  relationship_id uuid REFERENCES relationships(id),
  valid_during daterange NOT NULL,
  observed_at timestamptz NOT NULL,
  extraction_method text NOT NULL,
  extractor_version text,
  confidence numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  status assertion_status NOT NULL DEFAULT 'discovered',
  supersedes_assertion_id uuid REFERENCES assertions(id),
  reviewed_by text,
  reviewed_at timestamptz,
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (object_node_id IS NOT NULL OR literal_value IS NOT NULL OR relationship_id IS NOT NULL),
  CHECK (NOT isempty(valid_during))
);

CREATE TABLE evidence_links (
  assertion_id uuid NOT NULL REFERENCES assertions(id) ON DELETE CASCADE,
  source_fragment_id uuid NOT NULL REFERENCES source_fragments(id),
  legal_provision_id uuid REFERENCES legal_provisions(id),
  supports boolean NOT NULL DEFAULT true,
  note text,
  PRIMARY KEY (assertion_id, source_fragment_id)
);

CREATE TABLE entity_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id uuid NOT NULL REFERENCES nodes(id),
  alias text NOT NULL,
  normalized_alias text NOT NULL,
  source_document_id uuid REFERENCES source_documents(id),
  valid_during daterange NOT NULL,
  UNIQUE (node_id, normalized_alias, valid_during)
);

CREATE TABLE external_identifiers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id uuid NOT NULL REFERENCES nodes(id),
  system text NOT NULL,
  identifier text NOT NULL,
  UNIQUE (system, identifier)
);

CREATE TABLE ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  adapter_key text NOT NULL,
  status ingestion_status NOT NULL DEFAULT 'queued',
  started_at timestamptz,
  finished_at timestamptz,
  discovered_count integer NOT NULL DEFAULT 0,
  candidate_count integer NOT NULL DEFAULT 0,
  snapshot_count integer NOT NULL DEFAULT 0,
  error_message text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE review_tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assertion_id uuid REFERENCES assertions(id),
  ingestion_run_id uuid REFERENCES ingestion_runs(id),
  candidate_key text,
  title text NOT NULL,
  summary text NOT NULL,
  priority review_priority NOT NULL DEFAULT 'medium',
  status assertion_status NOT NULL DEFAULT 'needs_review',
  assigned_to text,
  decision_note text,
  decided_by text,
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (status IN ('needs_review', 'approved', 'rejected', 'published', 'superseded'))
);

CREATE TABLE government_change_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  title text NOT NULL,
  description text NOT NULL,
  occurred_on date NOT NULL,
  primary_node_id uuid REFERENCES nodes(id),
  assertion_id uuid NOT NULL REFERENCES assertions(id),
  published_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX nodes_name_trgm_idx ON nodes USING gin (canonical_name gin_trgm_ops);
CREATE INDEX nodes_valid_during_idx ON nodes USING gist (valid_during);
CREATE INDEX relationships_source_idx ON relationships (source_node_id);
CREATE INDEX relationships_target_idx ON relationships (target_node_id);
CREATE INDEX relationships_valid_during_idx ON relationships USING gist (valid_during);
CREATE INDEX assertions_status_idx ON assertions (status, created_at DESC);
CREATE INDEX aliases_trgm_idx ON entity_aliases USING gin (normalized_alias gin_trgm_ops);
CREATE INDEX snapshots_source_date_idx ON source_snapshots (source_document_id, retrieved_at DESC);
CREATE UNIQUE INDEX review_tasks_open_candidate_idx ON review_tasks (candidate_key) WHERE status = 'needs_review' AND candidate_key IS NOT NULL;

CREATE OR REPLACE FUNCTION prevent_published_assertion_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'published' AND (
    NEW.subject_node_id IS DISTINCT FROM OLD.subject_node_id OR
    NEW.predicate IS DISTINCT FROM OLD.predicate OR
    NEW.object_node_id IS DISTINCT FROM OLD.object_node_id OR
    NEW.literal_value IS DISTINCT FROM OLD.literal_value OR
    NEW.relationship_id IS DISTINCT FROM OLD.relationship_id OR
    NEW.valid_during IS DISTINCT FROM OLD.valid_during
  ) THEN
    RAISE EXCEPTION 'Published assertions are immutable; create a superseding assertion';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER assertions_immutable_when_published
BEFORE UPDATE ON assertions
FOR EACH ROW EXECUTE FUNCTION prevent_published_assertion_mutation();

CREATE OR REPLACE VIEW published_relationships AS
SELECT r.*
FROM relationships r
WHERE EXISTS (
  SELECT 1 FROM assertions a
  WHERE a.relationship_id = r.id AND a.status = 'published'
);

COMMIT;
