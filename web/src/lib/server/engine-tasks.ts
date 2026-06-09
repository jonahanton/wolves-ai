import { RunTaskCommand, StopTaskCommand } from "@aws-sdk/client-ecs";
import { awsEnv, ecsClient } from "@/lib/server/aws";

export async function runEngineNow(): Promise<string> {
  const result = await ecsClient().send(
    new RunTaskCommand({
      cluster: awsEnv.clusterArn,
      taskDefinition: awsEnv.taskDefinition,
      launchType: "FARGATE",
      count: 1,
      networkConfiguration: {
        awsvpcConfiguration: {
          subnets: awsEnv.subnets,
          securityGroups: awsEnv.securityGroup ? [awsEnv.securityGroup] : [],
          assignPublicIp: "ENABLED",
        },
      },
    }),
  );
  const taskArn = result.tasks?.[0]?.taskArn;
  if (!taskArn) {
    throw new Error(result.failures?.[0]?.reason ?? "RunTask returned no task");
  }
  return taskArn;
}

export async function stopEngineTask(taskArn: string): Promise<void> {
  await ecsClient().send(
    new StopTaskCommand({ cluster: awsEnv.clusterArn, task: taskArn, reason: "Stopped from admin" }),
  );
}
