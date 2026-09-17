import { notFound } from "next/navigation";
import { NodeDetail } from "@/components/node-detail";
import { dataset, getNodeBySlug } from "@/lib/data";

export function generateStaticParams() {
  return dataset.nodes.filter((node) => node.kind === "person").map((node) => ({ slug: node.slug }));
}

export default async function PersonPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const node = getNodeBySlug(slug);
  if (!node || node.kind !== "person") notFound();
  return <div className="container"><NodeDetail node={node} /></div>;
}
