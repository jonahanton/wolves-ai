resource "aws_ecr_repository" "engine" {
  name                 = "${var.project}-engine"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "engine" {
  repository = aws_ecr_repository.engine.name

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

resource "aws_cloudwatch_log_group" "engine" {
  name              = "/ecs/${var.project}-engine"
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

resource "aws_iam_role" "task_execution" {
  name               = "${var.project}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

locals {
  engine_env_secrets = {
    ANTHROPIC_API_KEY = "Anthropic API key for live agent runs"
    API_FOOTBALL_KEY  = "API-Football key for live fixture polling"
    ODDS_API_KEY      = "The Odds API key for market data ingestion"
  }

  engine_environment = [
    { name = "AWS_REGION", value = var.region },
    { name = "BUCKET", value = var.bucket_name },
    { name = "STORAGE_MODE", value = "both" },
    { name = "DYNAMO_TABLE", value = var.dynamo_table_name },
    { name = "RUNS_ROOT", value = "/tmp/runs" },
    { name = "AGENT_CEILING_BASE_USD", value = tostring(var.run_policy.agent_ceiling_base_usd) },
    { name = "AGENT_CEILING_REST_DAY_USD", value = tostring(var.run_policy.agent_ceiling_rest_day_usd) },
    { name = "AGENT_CEILING_PER_RESULT_USD", value = tostring(var.run_policy.agent_ceiling_per_result_usd) },
    { name = "AGENT_CEILING_KNOCKOUT_TODAY_USD", value = tostring(var.run_policy.agent_ceiling_knockout_today_usd) },
    { name = "AGENT_CEILING_FOCUS_BONUS_USD", value = tostring(var.run_policy.agent_ceiling_focus_bonus_usd) },
    { name = "AGENT_CEILING_POLICY_MAX_USD", value = tostring(var.run_policy.agent_ceiling_policy_max_usd) },
    { name = "LIVE_POLL_INTERVAL_S", value = tostring(var.run_policy.live_poll_interval_s) },
    { name = "LIVE_STALE_AFTER_S", value = tostring(var.run_policy.live_stale_after_s) },
    { name = "LIVE_IDLE_INTERVAL_S", value = tostring(var.run_policy.live_idle_interval_s) },
    { name = "LIVE_IDLE_GRACE_HOURS", value = tostring(var.run_policy.live_idle_grace_hours) },
  ]

  engine_secrets = [
    for name, secret in aws_secretsmanager_secret.engine_env :
    { name = name, valueFrom = secret.arn }
  ]
}

resource "aws_secretsmanager_secret" "engine_env" {
  for_each = local.engine_env_secrets

  name        = "${var.project}-engine-${lower(replace(each.key, "_", "-"))}"
  description = "${each.value}. Value managed manually, not by terraform."
}

data "aws_iam_policy_document" "execution_engine_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [for secret in aws_secretsmanager_secret.engine_env : secret.arn]
  }
}

resource "aws_iam_role_policy" "execution_engine_secrets" {
  name   = "engine-env-secrets"
  role   = aws_iam_role.task_execution.id
  policy = data.aws_iam_policy_document.execution_engine_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "${var.project}-engine-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "engine_task" {
  statement {
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = [var.bucket_arn, "${var.bucket_arn}/*"]
  }

  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:Query"]
    resources = [var.dynamo_table_arn]
  }
}

resource "aws_iam_role_policy" "engine_task" {
  name   = "snapshot-store"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.engine_task.json
}

# Runs in the default VPC's public subnets with a public IP so the one-off
# task stays NAT-free; the security group permits nothing inbound.
resource "aws_security_group" "engine" {
  name        = "${var.project}-engine"
  description = "Egress-only for the engine task"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "daily" {
  family                   = "${var.project}-engine-daily"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name        = "engine"
      image       = "${aws_ecr_repository.engine.repository_url}:${var.image_tag}"
      essential   = true
      environment = local.engine_environment
      secrets     = local.engine_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.engine.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "daily"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "agent" {
  family                   = "${var.project}-engine-agent"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "engine"
      image     = "${aws_ecr_repository.engine.repository_url}:${var.image_tag}"
      essential = true
      # No --ceiling: the engine derives it from the calendar run policy.
      command     = ["wolves.run_agent", "--live", "--confirm-spend"]
      environment = local.engine_environment
      secrets     = local.engine_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.engine.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "agent"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "live" {
  family                   = "${var.project}-engine-live"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name        = "engine"
      image       = "${aws_ecr_repository.engine.repository_url}:${var.image_tag}"
      essential   = true
      command     = ["wolves.live", "--loop", "--until-idle"]
      environment = local.engine_environment
      secrets     = local.engine_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.engine.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "live"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "archive" {
  family                   = "${var.project}-engine-archive"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name        = "engine"
      image       = "${aws_ecr_repository.engine.repository_url}:${var.image_tag}"
      essential   = true
      command     = ["wolves.archive"]
      environment = local.engine_environment
      secrets     = local.engine_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.engine.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "archive"
        }
      }
    }
  ])
}
