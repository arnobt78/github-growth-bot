import { NextResponse } from "next/server";
import { BackendError } from "@/lib/backend-client";

export async function proxyRoute<T>(fn: () => Promise<T>, successStatus = 200) {
  try {
    const data = await fn();
    if (data === undefined) {
      return new NextResponse(null, { status: 204 });
    }
    return NextResponse.json(data, { status: successStatus });
  } catch (error) {
    if (error instanceof BackendError) {
      return NextResponse.json({ error: error.message }, { status: error.status });
    }
    throw error;
  }
}
