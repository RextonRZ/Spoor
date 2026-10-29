/**
 * Demo sign-in: picks which of the three local users (investigator / reviewer / site admin) the proxy acts as.
 * Hackathon scope (backend/src/spoor/api/auth.py): a production build replaces this with an identity provider.
 */
import { cookies } from "next/headers";

const ROLES = ["investigator", "reviewer", "site_admin"] as const;

export async function GET() {
  const role = (await cookies()).get("spoor_role")?.value ?? "investigator";
  return Response.json({ role });
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as { role?: string };
  if (!ROLES.includes(body.role as (typeof ROLES)[number])) {
    return Response.json({ detail: "unknown role" }, { status: 422 });
  }
  (await cookies()).set("spoor_role", body.role!, { httpOnly: true, sameSite: "strict", path: "/" });
  return Response.json({ role: body.role });
}
