import { NextResponse } from "next/server";

const datePattern = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return NextResponse.json({ detail: "API not configured" }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const query = searchParams.get("q")?.trim() ?? "";
  const asOf = searchParams.get("asOf") ?? new Date().toISOString().slice(0, 10);
  if (query.length < 2 || query.length > 120 || !datePattern.test(asOf)) {
    return NextResponse.json({ detail: "Invalid search query" }, { status: 400 });
  }

  const upstream = new URL(`${apiUrl.replace(/\/$/, "")}/v1/search`);
  upstream.searchParams.set("q", query);
  upstream.searchParams.set("as_of", asOf);
  for (const name of ["types", "branch", "category"]) {
    const value = searchParams.get(name);
    if (value) upstream.searchParams.set(name, value);
  }

  try {
    const response = await fetch(upstream, { cache: "no-store" });
    const body: unknown = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "No fue posible conectar con la API." }, { status: 502 });
  }
}
