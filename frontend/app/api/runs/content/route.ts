import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function POST() {
  return proxyRoute(() => api.triggerContentRun(), 202);
}
