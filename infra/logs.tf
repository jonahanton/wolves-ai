resource "aws_cloudwatch_log_group" "engine" {
  name              = "/ecs/${var.project}-engine"
  retention_in_days = var.log_retention_days
}
