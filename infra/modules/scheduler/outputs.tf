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

output "agent_schedule_name" {
  value = { for key, schedule in aws_scheduler_schedule.agent_daily : key => schedule.name }
}

output "agent_schedule_arn" {
  value = { for key, schedule in aws_scheduler_schedule.agent_daily : key => schedule.arn }
}

output "live_schedule_name" {
  value = aws_scheduler_schedule.live_window.name
}

output "live_schedule_arn" {
  value = aws_scheduler_schedule.live_window.arn
}
