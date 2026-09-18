import { NextResponse } from "next/server";

const datePattern = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return NextResponse.json({ detail: "API not configured" }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const asOf = searchParams.get("asOf") ?? new Date().toISOString().slice(0, 10);
  const root = searchParams.get("root");
  const cursor = searchParams.get("cursor");
  const depth = Number(searchParams.get("depth") ?? "2");
  const limit = Number(searchParams.get("limit") ?? "500");

  if (!datePattern.test(asOf) || !Number.isInteger(depth) || depth < 1 || depth > 4 || !Number.isInteger(limit) || limit < 1 || limit > 1000) {
    return NextResponse.json({ detail: "Invalid power map query" }, { status: 400 });
  }

  const upstream = new URL(`${apiUrl.replace(/\/$/, "")}/v1/power-map`);
  upstream.searchParams.set("as_of", asOf);
  upstream.searchParams.set("depth", String(depth));
  upstream.searchParams.set("limit", String(limit));
  if (root) upstream.searchParams.set("root", root);
  if (cursor) upstream.searchParams.set("cursor", cursor);

  try {
    const response = await fetch(upstream, { cache: "no-store" });
    const body: unknown = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "No fue posible conectar con la API." }, { status: 502 });
  }
}
