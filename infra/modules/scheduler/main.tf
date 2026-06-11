data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.project}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler_run_task" {
  statement {
    actions = ["ecs:RunTask"]
    resources = [
      "arn:aws:ecs:${var.region}:${var.account_id}:task-definition/${var.task_definition_family}:*",
      "arn:aws:ecs:${var.region}:${var.account_id}:task-definition/${var.archive_task_definition_family}:*",
      "arn:aws:ecs:${var.region}:${var.account_id}:task-definition/${var.agent_task_definition_family}:*",
      "arn:aws:ecs:${var.region}:${var.account_id}:task-definition/${var.live_task_definition_family}:*",
    ]
  }

  statement {
    actions   = ["iam:PassRole"]
    resources = [var.task_execution_role_arn, var.task_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "scheduler_run_task" {
  name   = "run-engine-tasks"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_run_task.json
}

resource "aws_scheduler_schedule" "daily_run" {
  name  = "${var.project}-daily-run"
  state = var.initial_state

  schedule_expression = var.initial_cron

  # The backend admin API owns cron and state at runtime via UpdateSchedule;
  # applies must not stomp those edits.
  lifecycle {
    ignore_changes = [schedule_expression, state]
  }

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.cluster_arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      # Revisionless ARN so each release's freshly registered task definition
      # is picked up without touching the schedule.
      task_definition_arn = replace(var.task_definition_arn, "/:\\d+$/", "")
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = var.subnets
        security_groups  = [var.security_group_id]
        assign_public_ip = true
      }
    }

    retry_policy {
      maximum_retry_attempts = 1
    }
  }
}

resource "aws_scheduler_schedule" "agent_daily" {
  for_each = { for window in var.agent_schedule_windows : window.name => window }

  name  = "${var.project}-agent-${each.key}"
  state = var.agent_initial_state

  schedule_expression = each.value.cron
  start_date          = each.value.start
  end_date            = each.value.end

  lifecycle {
    ignore_changes = [schedule_expression, state]
  }

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.cluster_arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = replace(var.agent_task_definition_arn, "/:\\d+$/", "")
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = var.subnets
        security_groups  = [var.security_group_id]
        assign_public_ip = true
      }
    }

    retry_policy {
      maximum_retry_attempts = 1
    }
  }
}

resource "aws_scheduler_schedule" "live_window" {
  name  = "${var.project}-live-window"
  state = var.live_initial_state

  schedule_expression = var.live_initial_cron

  lifecycle {
    ignore_changes = [schedule_expression, state]
  }

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.cluster_arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = replace(var.live_task_definition_arn, "/:\\d+$/", "")
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = var.subnets
        security_groups  = [var.security_group_id]
        assign_public_ip = true
      }
    }

    retry_policy {
      maximum_retry_attempts = 1
    }
  }
}

resource "aws_scheduler_schedule" "odds_archive" {
  name  = "${var.project}-odds-archive"
  state = var.archive_initial_state

  schedule_expression = var.archive_initial_cron

  lifecycle {
    ignore_changes = [schedule_expression, state]
  }

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.cluster_arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = replace(var.archive_task_definition_arn, "/:\\d+$/", "")
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = var.subnets
        security_groups  = [var.security_group_id]
        assign_public_ip = true
      }
    }

    retry_policy {
      maximum_retry_attempts = 1
    }
  }
}
