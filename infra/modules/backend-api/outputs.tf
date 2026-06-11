output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.backend.arn
}

output "service_name" {
  value = aws_ecs_service.backend.name
}

output "service_arn" {
  value = aws_ecs_service.backend.id
}

output "task_role_arn" {
  value = aws_iam_role.backend_task.arn
}

output "task_role_name" {
  value = aws_iam_role.backend_task.name
}
