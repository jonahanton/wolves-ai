import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { ECSClient } from "@aws-sdk/client-ecs";
import { S3Client } from "@aws-sdk/client-s3";
import { SchedulerClient } from "@aws-sdk/client-scheduler";

export const awsEnv = {
  region: process.env.AWS_REGION ?? "eu-west-2",
  table: process.env.DYNAMO_TABLE ?? "wolves-forecaster",
  bucket: process.env.SNAPSHOT_BUCKET ?? "",
  dynamoEndpoint: process.env.DYNAMO_ENDPOINT ?? "",
  scheduleName: process.env.SCHEDULE_NAME ?? "wolves-daily-run",
  clusterArn: process.env.ECS_CLUSTER_ARN ?? "",
  taskDefinition: process.env.ECS_TASK_DEFINITION ?? "wolves-engine-daily",
  subnets: (process.env.ECS_SUBNETS ?? "").split(",").filter(Boolean),
  securityGroup: process.env.ECS_SECURITY_GROUP ?? "",
};

let dynamo: DynamoDBClient | undefined;
let s3: S3Client | undefined;
let scheduler: SchedulerClient | undefined;
let ecs: ECSClient | undefined;

export function dynamoClient(): DynamoDBClient {
  dynamo ??= new DynamoDBClient({
    region: awsEnv.region,
    ...(awsEnv.dynamoEndpoint ? { endpoint: awsEnv.dynamoEndpoint } : {}),
  });
  return dynamo;
}

export function s3Client(): S3Client {
  s3 ??= new S3Client({ region: awsEnv.region });
  return s3;
}

export function schedulerClient(): SchedulerClient {
  scheduler ??= new SchedulerClient({ region: awsEnv.region });
  return scheduler;
}

export function ecsClient(): ECSClient {
  ecs ??= new ECSClient({ region: awsEnv.region });
  return ecs;
}
