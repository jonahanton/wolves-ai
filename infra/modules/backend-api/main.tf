resource "aws_ecr_repository" "backend" {
  name                 = "${var.project}-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project}-backend"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backend_task" {
  name               = "${var.project}-backend-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "backend_task" {
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [var.bucket_arn, "${var.bucket_arn}/*"]
  }

  # Only the in-process loops' families; the agent plane's prefixes stay out of reach.
  statement {
    actions = ["s3:PutObject"]
    resources = [
      "${var.bucket_arn}/live/*",
      "${var.bucket_arn}/odds-archive/*",
      "${var.bucket_arn}/snapshots/*",
      "${var.bucket_arn}/models/fitted/*",
    ]
  }

  statement {
    actions   = ["sns:Publish"]
    resources = [var.alerts_topic_arn]
  }

  statement {
    actions   = ["dynamodb:Query", "dynamodb:PutItem"]
    resources = [var.dynamo_table_arn]
  }

  statement {
    actions   = ["scheduler:GetSchedule", "scheduler:UpdateSchedule"]
    resources = [var.schedule_arn]
  }

  statement {
    actions   = ["ecs:RunTask"]
    resources = ["arn:aws:ecs:${var.region}:${var.account_id}:task-definition/${var.engine_task_definition_family}:*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [var.cluster_arn]
    }
  }

  statement {
    actions   = ["ecs:StopTask", "ecs:DescribeTasks"]
    resources = ["arn:aws:ecs:${var.region}:${var.account_id}:task/${var.cluster_name}/*"]
  }

  # ListTasks scopes by cluster condition, not task resource ARNs.
  statement {
    actions   = ["ecs:ListTasks"]
    resources = ["*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [var.cluster_arn]
    }
  }

  statement {
    actions   = ["iam:PassRole"]
    resources = [var.task_execution_role_arn, var.engine_task_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  statement {
    actions   = ["iam:PassRole"]
    resources = [var.scheduler_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "backend_task" {
  name   = "snapshot-and-run-control"
  role   = aws_iam_role.backend_task.id
  policy = data.aws_iam_policy_document.backend_task.json
}

# The token value is set out of band (aws secretsmanager put-secret-value)
# so it never enters terraform state; terraform manages only the container.
resource "aws_secretsmanager_secret" "admin_token" {
  name        = "${var.project}-backend-admin-token"
  description = "Bearer token for the backend admin API. Value managed manually, not by terraform."
}

resource "aws_secretsmanager_secret" "frontend_key" {
  name        = "${var.project}-backend-frontend-key"
  description = "Shared secret the frontend sends as X-Wolves-Key. Value managed manually, not by terraform."
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.admin_token.arn, aws_secretsmanager_secret.frontend_key.arn]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "backend-secrets"
  role   = var.task_execution_role_name
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# No ALB in front of this service: it is a single public task whose admin
# surface denies by default in-app, so ingress on the app port is acceptable.
resource "aws_security_group" "backend" {
  name        = "${var.project}-backend"
  description = "Backend API ingress on the app port, egress anywhere"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = aws_iam_role.backend_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.image_tag}"
      essential = true
      portMappings = [
        { containerPort = 8080, protocol = "tcp" }
      ]
      environment = [
        { name = "ENVIRONMENT", value = "production" },
        { name = "AWS_REGION", value = var.region },
        { name = "BUCKET", value = var.bucket_name },
        { name = "STORAGE_MODE", value = "both" },
        { name = "RUNS_ROOT", value = "/tmp/runs" },
        { name = "DYNAMO_TABLE", value = var.dynamo_table_name },
        { name = "SCHEDULE_NAME", value = var.schedule_name },
        { name = "ALERTS_TOPIC_ARN", value = var.alerts_topic_arn },
        { name = "ECS_CLUSTER_ARN", value = var.cluster_arn },
        { name = "ECS_TASK_DEFINITION", value = var.engine_task_definition_family },
        { name = "ECS_AGENT_TASK_DEFINITION", value = var.agent_task_definition_family },
        { name = "ECS_SUBNETS", value = join(",", var.subnets) },
        { name = "ECS_SECURITY_GROUP", value = var.engine_security_group_id },
        { name = "AGENT_CEILING_OPENING_USD", value = tostring(var.run_policy.agent_ceiling_opening_usd) },
        { name = "AGENT_CEILING_BIG_GROUP_USD", value = tostring(var.run_policy.agent_ceiling_big_group_usd) },
        { name = "AGENT_CEILING_GROUP_USD", value = tostring(var.run_policy.agent_ceiling_group_usd) },
        { name = "AGENT_CEILING_REST_USD", value = tostring(var.run_policy.agent_ceiling_rest_usd) },
        { name = "AGENT_CEILING_R32_R16_USD", value = tostring(var.run_policy.agent_ceiling_r32_r16_usd) },
        { name = "AGENT_CEILING_QF_FINAL_USD", value = tostring(var.run_policy.agent_ceiling_qf_final_usd) },
        { name = "AGENT_CEILING_SINGLE_GAME_DISCOUNT_USD", value = tostring(var.run_policy.agent_ceiling_single_game_discount_usd) },
        { name = "AGENT_BIG_TEAM_COUNT", value = tostring(var.run_policy.agent_big_team_count) },
        { name = "LIVE_POLL_INTERVAL_S", value = tostring(var.run_policy.live_poll_interval_s) },
        { name = "LIVE_STALE_AFTER_S", value = tostring(var.run_policy.live_stale_after_s) },
        { name = "LIVE_IDLE_INTERVAL_S", value = tostring(var.run_policy.live_idle_interval_s) },
        { name = "LIVE_IDLE_GRACE_HOURS", value = tostring(var.run_policy.live_idle_grace_hours) },
      ]
      secrets = concat(
        [
          { name = "ADMIN_TOKEN", valueFrom = aws_secretsmanager_secret.admin_token.arn },
          { name = "FRONTEND_KEY", valueFrom = aws_secretsmanager_secret.frontend_key.arn },
        ],
        [for name, arn in var.live_data_secret_arns : { name = name, valueFrom = arn }],
      )
      # SIGTERM grace covers a live pass finishing its atomic writes.
      stopTimeout = 120
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.backend.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "backend" {
  name            = "${var.project}-backend"
  cluster         = var.cluster_id
  task_definition = aws_ecs_task_definition.backend.arn
  # Single-writer pin lives on the variable; deploy overlap is benign (merge-on-write stores).
  desired_count = var.desired_count
  launch_type   = "FARGATE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.subnets
    security_groups  = [aws_security_group.backend.id]
    assign_public_ip = true
  }
}
