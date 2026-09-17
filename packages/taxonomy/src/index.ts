export const relationshipTypes = [
  "PART_OF",
  "HEADS",
  "HOLDS",
  "ELECTS",
  "NOMINATES",
  "APPOINTS",
  "DESIGNATES",
  "RATIFIES",
  "REMOVES",
  "OVERSEES",
  "AUDITS",
  "REGULATES",
  "PROPOSES_BUDGET",
  "APPROVES_BUDGET",
  "PROPOSES_LEGISLATION",
  "APPROVES_LEGISLATION",
  "PROMULGATES"
] as const;

export const organizationTypes = [
  "branch",
  "presidency",
  "secretariat",
  "legislative_chamber",
  "court",
  "judicial_body",
  "constitutional_autonomous_body",
  "technical_oversight_body"
] as const;

export const policyDomains = [
  "public_administration",
  "legislation",
  "justice",
  "elections",
  "monetary_policy",
  "statistics",
  "human_rights",
  "audit",
  "public_finance"
] as const;

export type RelationshipType = (typeof relationshipTypes)[number];
export type OrganizationType = (typeof organizationTypes)[number];
export type PolicyDomain = (typeof policyDomains)[number];
