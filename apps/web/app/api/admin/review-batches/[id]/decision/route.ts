import { NextResponse } from "next/server";
import { getAdminUser } from "@/lib/admin";

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const user = await getAdminUser();
  if (!user) return NextResponse.json({ detail: "Admin authentication required" }, { status: 401 });

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return NextResponse.json({ detail: "API not configured" }, { status: 503 });
  const { id } = await params;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (process.env.ADMIN_API_TOKEN) headers.Authorization = `Bearer ${process.env.ADMIN_API_TOKEN}`;
  try {
    const response = await fetch(`${apiUrl.replace(/\/$/, "")}/v1/admin/review-batches/${encodeURIComponent(id)}/decision`, {
      method: "POST",
      headers,
      body: await request.text(),
      cache: "no-store"
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "No fue posible conectar con la API." }, { status: 502 });
  }
}
