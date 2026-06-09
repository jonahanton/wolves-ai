import { PutItemCommand } from "@aws-sdk/client-dynamodb";
import { GetScheduleCommand, UpdateScheduleCommand } from "@aws-sdk/client-scheduler";
import { awsEnv, dynamoClient, schedulerClient } from "@/lib/server/aws";

export interface ScheduleState {
  enabled: boolean;
  cron: string;
}

export async function getScheduleState(): Promise<ScheduleState> {
  const schedule = await schedulerClient().send(new GetScheduleCommand({ Name: awsEnv.scheduleName }));
  return { enabled: schedule.State === "ENABLED", cron: schedule.ScheduleExpression ?? "" };
}

export async function setScheduleEnabled(enabled: boolean): Promise<ScheduleState> {
  const scheduler = schedulerClient();
  // UpdateSchedule replaces the whole schedule, so echo back every field from
  // GetSchedule with only State changed.
  const current = await scheduler.send(new GetScheduleCommand({ Name: awsEnv.scheduleName }));
  await scheduler.send(
    new UpdateScheduleCommand({
      Name: current.Name,
      GroupName: current.GroupName,
      ScheduleExpression: current.ScheduleExpression,
      ScheduleExpressionTimezone: current.ScheduleExpressionTimezone,
      FlexibleTimeWindow: current.FlexibleTimeWindow,
      Target: current.Target,
      State: enabled ? "ENABLED" : "DISABLED",
    }),
  );
  await setRunEnabledFlag(enabled);
  return { enabled, cron: current.ScheduleExpression ?? "" };
}

// Second layer of the kill switch: the daily task checks this flag at start,
// so disabling also stops a run the schedule has already launched.
async function setRunEnabledFlag(enabled: boolean): Promise<void> {
  await dynamoClient().send(
    new PutItemCommand({
      TableName: awsEnv.table,
      Item: { PK: { S: "CONTROL" }, SK: { S: "run_enabled" }, enabled: { BOOL: enabled } },
    }),
  );
}
