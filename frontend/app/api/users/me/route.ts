import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET() {
  return proxyRoute(() => api.getMe());
}

export async function PATCH(request: Request) {
  const payload = (await request.json()) as { notification_email: string | null };
  return proxyRoute(() => api.updateMe(payload));
}
