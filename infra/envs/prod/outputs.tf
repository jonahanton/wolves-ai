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
  value = module.scheduler.schedule_name
}

output "archive_schedule_name" {
  value = module.scheduler.archive_schedule_name
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "ecs_task_definition_family" {
  value = module.engine.task_definition_family
}

output "ecs_archive_task_definition_family" {
  value = module.engine.archive_task_definition_family
}

output "ecs_subnets" {
  value = join(",", data.aws_subnets.default.ids)
}

output "ecs_security_group" {
  value = module.engine.security_group_id
}

output "ecr_repository_url" {
  value = module.engine.ecr_repository_url
}

output "backend_ecr_repository_url" {
  value = module.backend_api.ecr_repository_url
}

output "backend_service_name" {
  value = module.backend_api.service_name
}

output "github_release_role_arn" {
  value = module.release_oidc.release_role_arn
}

output "github_ops_role_arn" {
  value = module.release_oidc.ops_role_arn
}

output "alerts_topic_arn" {
  value = module.alerting.alerts_topic_arn
}
