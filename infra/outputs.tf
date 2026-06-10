# The backend service environment, plus release workflow inputs.
output "aws_region" {
  value = var.region
}

output "bucket" {
  value = data.aws_s3_bucket.artifacts.bucket
}

output "dynamo_table" {
  value = aws_dynamodb_table.forecaster.name
}

output "schedule_name" {
  value = aws_scheduler_schedule.daily_run.name
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "ecs_task_definition_family" {
  value = aws_ecs_task_definition.daily.family
}

output "ecs_subnets" {
  value = join(",", data.aws_subnets.default.ids)
}

output "ecs_security_group" {
  value = aws_security_group.engine.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.engine.repository_url
}

output "backend_ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "backend_service_name" {
  value = aws_ecs_service.backend.name
}

output "github_release_role_arn" {
  value = aws_iam_role.github_release.arn
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
