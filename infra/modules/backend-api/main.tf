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

data "aws_iam_policy_document" "execution_admin_token" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.admin_token.arn]
  }
}

resource "aws_iam_role_policy" "execution_admin_token" {
  name   = "backend-admin-token"
  role   = var.task_execution_role_name
  policy = data.aws_iam_policy_document.execution_admin_token.json
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
        { name = "DYNAMO_TABLE", value = var.dynamo_table_name },
        { name = "SCHEDULE_NAME", value = var.schedule_name },
        { name = "ECS_CLUSTER_ARN", value = var.cluster_arn },
        { name = "ECS_TASK_DEFINITION", value = var.engine_task_definition_family },
        { name = "ECS_SUBNETS", value = join(",", var.subnets) },
        { name = "ECS_SECURITY_GROUP", value = var.engine_security_group_id },
      ]
      secrets = [
        { name = "ADMIN_TOKEN", valueFrom = aws_secretsmanager_secret.admin_token.arn }
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
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
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

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
