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
