import { NextResponse } from "next/server";
import { adminRoute } from "@/lib/server/api";
import { stopEngineTask } from "@/lib/server/engine-tasks";

export async function POST(request: Request): Promise<NextResponse> {
  return adminRoute(async () => {
    const body = (await request.json()) as { taskArn?: unknown };
    if (typeof body.taskArn !== "string" || body.taskArn === "") {
      return NextResponse.json({ error: "taskArn must be a non-empty string" }, { status: 400 });
    }
    await stopEngineTask(body.taskArn);
    return NextResponse.json({ stopped: body.taskArn });
  });
}
