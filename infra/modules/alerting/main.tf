resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

data "aws_iam_policy_document" "alerts_topic" {
  statement {
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.alerts.arn]

    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }
  }

  statement {
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.alerts.arn]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.engine_task_failed.arn]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts_topic.json
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count = var.alert_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_event_rule" "engine_task_failed" {
  name        = "${var.project}-engine-task-failed"
  description = "Engine task stopped with a non-zero exit or failed to start"

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      clusterArn = [var.cluster_arn]
      lastStatus = ["STOPPED"]
      taskDefinitionArn = [
        for family in var.engine_task_definition_families :
        { prefix = "arn:aws:ecs:${var.region}:${var.account_id}:task-definition/${family}" }
      ]
      "$or" = [
        { containers = { exitCode = [{ anything-but = [0] }] } },
        { stopCode = ["TaskFailedToStart"] },
      ]
    }
  })
}

resource "aws_cloudwatch_event_target" "engine_task_failed_sns" {
  rule = aws_cloudwatch_event_rule.engine_task_failed.name
  arn  = aws_sns_topic.alerts.arn

  input_transformer {
    input_paths = {
      stopCode      = "$.detail.stopCode"
      stoppedReason = "$.detail.stoppedReason"
      taskArn       = "$.detail.taskArn"
    }
    input_template = "\"Engine task failed: <stopCode>. Reason: <stoppedReason>. Task: <taskArn>\""
  }
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.project}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.alerts.arn]
    subscriber_email_addresses = var.alert_email == "" ? [] : [var.alert_email]
  }
}

# Budget actions cannot flip an EventBridge Scheduler state, so at 100 percent
# the action attaches this deny policy to the scheduler role instead, which
# stops RunTask just as dead.
resource "aws_iam_policy" "deny_run_task" {
  name = "${var.project}-deny-run-task"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Deny"
        Action   = "ecs:RunTask"
        Resource = "*"
      }
    ]
  })
}

data "aws_iam_policy_document" "budgets_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "budget_action" {
  name               = "${var.project}-budget-action"
  assume_role_policy = data.aws_iam_policy_document.budgets_assume.json
}

data "aws_iam_policy_document" "budget_action" {
  statement {
    actions   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
    resources = [var.scheduler_role_arn, var.backend_run_role_arn, var.github_ops_role_arn]
  }

  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
}

resource "aws_iam_role_policy" "budget_action" {
  name   = "execute-kill-switch"
  role   = aws_iam_role.budget_action.id
  policy = data.aws_iam_policy_document.budget_action.json
}

resource "aws_budgets_budget_action" "kill_switch" {
  budget_name        = aws_budgets_budget.monthly.name
  action_type        = "APPLY_IAM_POLICY"
  approval_model     = "AUTOMATIC"
  notification_type  = "ACTUAL"
  execution_role_arn = aws_iam_role.budget_action.arn

  action_threshold {
    action_threshold_type  = "PERCENTAGE"
    action_threshold_value = 100
  }

  definition {
    iam_action_definition {
      policy_arn = aws_iam_policy.deny_run_task.arn
      roles      = [var.scheduler_role_name, var.backend_run_role_name, var.github_ops_role_name]
    }
  }

  subscriber {
    address           = aws_sns_topic.alerts.arn
    subscription_type = "SNS"
  }
}
