import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET() {
  return proxyRoute(() => api.listDrafts());
}
