import { NextResponse } from "next/server";
import { adminRoute } from "@/lib/server/api";
import { stopEngineTask } from "@/lib/server/engine-tasks";

const TASK_ARN = /^arn:aws:ecs:[a-z0-9-]+:\d{12}:task\/[A-Za-z0-9_-]+\/[a-f0-9]+$/;

export async function POST(request: Request): Promise<NextResponse> {
  return adminRoute(async () => {
    const body = (await request.json()) as { taskArn?: unknown };
    if (typeof body.taskArn !== "string" || !TASK_ARN.test(body.taskArn)) {
      return NextResponse.json({ error: "taskArn must be a valid ECS task ARN" }, { status: 400 });
    }
    await stopEngineTask(body.taskArn);
    return NextResponse.json({ stopped: body.taskArn });
  });
}
