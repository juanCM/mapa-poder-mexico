import {
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  ChartNoAxesColumnIncreasing,
  Landmark,
  Medal,
  Network,
  Scale,
  ShieldCheck,
  UserRound,
  UsersRound,
  Vote,
  type LucideProps
} from "lucide-react";
import type { PowerMapNode } from "@mapa/contracts";

type IconNode = Pick<PowerMapNode, "branch" | "category" | "kind" | "label" | "slug">;

export function isFederalPresidency(node: Pick<PowerMapNode, "branch" | "kind" | "label" | "slug">) {
  return node.kind === "position" && node.branch === "executive" && (
    node.slug === "presidencia-de-mexico"
    || node.label.toLocaleLowerCase("es") === "presidencia de los estados unidos mexicanos"
  );
}

export function EntityIcon({ node, ...props }: { node: IconNode } & LucideProps) {
  if (isFederalPresidency(node)) return <Medal aria-hidden="true" {...props} />;
  if (node.category === "legislative_chamber") return <UsersRound aria-hidden="true" {...props} />;
  if (node.category === "legislative_seat") return <Vote aria-hidden="true" {...props} />;
  if (node.category === "technical_oversight_body") return <ChartNoAxesColumnIncreasing aria-hidden="true" {...props} />;
  if (node.category === "navigation_group" || node.category === "administrative_group") return <Network aria-hidden="true" {...props} />;
  if (node.category === "branch") {
    if (node.branch === "judicial") return <Scale aria-hidden="true" {...props} />;
    if (node.branch === "legislative") return <UsersRound aria-hidden="true" {...props} />;
    if (node.branch === "independent") return <ShieldCheck aria-hidden="true" {...props} />;
    return <Landmark aria-hidden="true" {...props} />;
  }
  if (node.kind === "person") return <UserRound aria-hidden="true" {...props} />;
  if (node.kind === "position") return <BriefcaseBusiness aria-hidden="true" {...props} />;
  if (node.kind === "unit") return <BadgeCheck aria-hidden="true" {...props} />;
  return <Building2 aria-hidden="true" {...props} />;
}
