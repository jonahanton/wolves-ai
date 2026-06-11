output "schedule_name" {
  value = aws_scheduler_schedule.daily_run.name
}

output "schedule_arn" {
  value = aws_scheduler_schedule.daily_run.arn
}

output "scheduler_role_arn" {
  value = aws_iam_role.scheduler.arn
}

output "scheduler_role_name" {
  value = aws_iam_role.scheduler.name
}

output "archive_schedule_name" {
  value = aws_scheduler_schedule.odds_archive.name
}

output "archive_schedule_arn" {
  value = aws_scheduler_schedule.odds_archive.arn
}
