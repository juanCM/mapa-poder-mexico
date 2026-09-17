BEGIN;

INSERT INTO nodes (id, slug, kind, canonical_name, short_name, description, category, branch, valid_during)
VALUES
  ('10000000-0000-4000-8000-000000000001', 'estado-mexicano', 'organization', 'Estado Mexicano', 'Estado Mexicano', 'Raíz conceptual del mapa institucional.', 'state', 'state', daterange('1917-02-05', NULL, '[)')),
  ('10000000-0000-4000-8000-000000000003', 'poder-ejecutivo-federal', 'organization', 'Poder Ejecutivo Federal', 'Ejecutivo', 'Poder de la Unión depositado en la Presidencia.', 'branch', 'executive', daterange('1917-02-05', NULL, '[)')),
  ('10000000-0000-4000-8000-000000000004', 'poder-legislativo-federal', 'organization', 'Poder Legislativo Federal', 'Legislativo', 'Congreso General dividido en dos cámaras.', 'branch', 'legislative', daterange('1917-02-05', NULL, '[)')),
  ('10000000-0000-4000-8000-000000000005', 'poder-judicial-federal', 'organization', 'Poder Judicial de la Federación', 'Judicial', 'Órganos responsables de impartir justicia federal.', 'branch', 'judicial', daterange('1917-02-05', NULL, '[)'))
ON CONFLICT (id) DO NOTHING;

INSERT INTO organizations (node_id, organization_type)
VALUES
  ('10000000-0000-4000-8000-000000000001', 'state'),
  ('10000000-0000-4000-8000-000000000003', 'branch'),
  ('10000000-0000-4000-8000-000000000004', 'branch'),
  ('10000000-0000-4000-8000-000000000005', 'branch')
ON CONFLICT (node_id) DO NOTHING;

COMMIT;
