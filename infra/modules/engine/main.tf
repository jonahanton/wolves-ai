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
      name      = "engine"
      image     = "${aws_ecr_repository.engine.repository_url}:${var.image_tag}"
      essential = true
      environment = [
        { name = "AWS_REGION", value = var.region },
        { name = "BUCKET", value = var.bucket_name },
        { name = "STORAGE_MODE", value = "both" },
        { name = "DYNAMO_TABLE", value = var.dynamo_table_name },
        { name = "RUNS_ROOT", value = "/tmp/runs" },
      ]
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
