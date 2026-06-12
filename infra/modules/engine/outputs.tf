output "ecr_repository_url" {
  value = aws_ecr_repository.engine.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.engine.arn
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.daily.arn
}

output "task_definition_family" {
  value = aws_ecs_task_definition.daily.family
}

output "archive_task_definition_arn" {
  value = aws_ecs_task_definition.archive.arn
}

output "archive_task_definition_family" {
  value = aws_ecs_task_definition.archive.family
}

output "agent_task_definition_arn" {
  value = aws_ecs_task_definition.agent.arn
}

output "agent_task_definition_family" {
  value = aws_ecs_task_definition.agent.family
}

output "live_task_definition_arn" {
  value = aws_ecs_task_definition.live.arn
}

output "live_task_definition_family" {
  value = aws_ecs_task_definition.live.family
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}

output "task_execution_role_name" {
  value = aws_iam_role.task_execution.name
}

output "security_group_id" {
  value = aws_security_group.engine.id
}

output "live_data_secret_arns" {
  description = "API-Football and Odds API secret ARNs shared with the backend; the Anthropic key stays agent-only."
  value = {
    API_FOOTBALL_KEY = aws_secretsmanager_secret.engine_env["API_FOOTBALL_KEY"].arn
    ODDS_API_KEY     = aws_secretsmanager_secret.engine_env["ODDS_API_KEY"].arn
  }
}
