import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET() {
  return proxyRoute(() => api.listRuns());
}

export async function POST() {
  return proxyRoute(() => api.triggerRun(), 202);
}
