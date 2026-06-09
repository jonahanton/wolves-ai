import { QueryCommand, type AttributeValue } from "@aws-sdk/client-dynamodb";
import { awsEnv, dynamoClient } from "@/lib/server/aws";

export interface RunRecord {
  runId: string;
  createdAt: string;
  s3Key: string;
  status: "completed" | "failed";
  cost: number;
  durationS: number;
  kind: string;
}

export async function listRuns(limit = 50): Promise<RunRecord[]> {
  const result = await dynamoClient().send(
    new QueryCommand({
      TableName: awsEnv.table,
      KeyConditionExpression: "PK = :pk",
      ExpressionAttributeValues: { ":pk": { S: "RUN" } },
      ScanIndexForward: false,
      Limit: limit,
    }),
  );
  return (result.Items ?? []).map(toRecord);
}

function toRecord(item: Record<string, AttributeValue>): RunRecord {
  return {
    runId: item.run_id?.S ?? "",
    createdAt: item.created_at?.S ?? "",
    s3Key: item.s3_key?.S ?? "",
    status: item.status?.S === "failed" ? "failed" : "completed",
    cost: Number(item.cost?.N ?? 0),
    durationS: Number(item.duration_s?.N ?? 0),
    kind: item.kind?.S ?? "",
  };
}
