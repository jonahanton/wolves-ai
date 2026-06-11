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
