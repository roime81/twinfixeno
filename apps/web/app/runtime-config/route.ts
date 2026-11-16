import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  return NextResponse.json(
    {
      apiBaseUrl: process.env.WEB_API_BASE_URL || "http://localhost:9080",
      keycloakUrl: process.env.WEB_KEYCLOAK_URL || "http://localhost:8081",
      keycloakRealm: process.env.WEB_KEYCLOAK_REALM || "twinfixeno",
      keycloakClientId: process.env.WEB_KEYCLOAK_CLIENT_ID || "twinfixeno-web",
    },
    {
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        Pragma: "no-cache",
      },
    },
  );
}
