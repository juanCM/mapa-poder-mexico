import { NextResponse } from "next/server";

const modes = new Set(["organization", "power"]);
const datePattern = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return NextResponse.json({ detail: "API not configured" }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const mode = searchParams.get("mode") ?? "power";
  const asOf = searchParams.get("asOf") ?? new Date().toISOString().slice(0, 10);

  if (!modes.has(mode) || !datePattern.test(asOf)) {
    return NextResponse.json({ detail: "Invalid graph query" }, { status: 400 });
  }

  try {
    const response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/v1/graph?mode=${encodeURIComponent(mode)}&as_of=${encodeURIComponent(asOf)}`,
      { cache: "no-store" }
    );
    const body: unknown = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "No fue posible conectar con la API." }, { status: 502 });
  }
}
