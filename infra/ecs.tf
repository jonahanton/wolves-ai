resource "aws_ecs_cluster" "this" {
  name = var.project
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
    resources = [aws_s3_bucket.snapshots.arn, "${aws_s3_bucket.snapshots.arn}/*"]
  }

  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.forecaster.arn]
  }
}

resource "aws_iam_role_policy" "engine_task" {
  name   = "snapshot-store"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.engine_task.json
}

resource "aws_ecs_task_definition" "daily" {
  family                   = "${var.project}-engine-daily"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.engine_cpu
  memory                   = var.engine_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "engine"
      image     = "${aws_ecr_repository.engine.repository_url}:${var.engine_image_tag}"
      essential = true
      environment = [
        { name = "AWS_REGION", value = var.region },
        { name = "SNAPSHOT_BUCKET", value = aws_s3_bucket.snapshots.bucket },
        { name = "AGENT_STATE_BUCKET", value = aws_s3_bucket.snapshots.bucket },
        { name = "DYNAMO_TABLE", value = aws_dynamodb_table.forecaster.name },
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
