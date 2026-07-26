provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

# Default VPC with public subnets keeps the stack NAT-free.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# The artifact buckets (prod and dev) were created manually with versioning
# on and public access blocked; terraform references prod, never manages it.
data "aws_s3_bucket" "artifacts" {
  bucket = var.bucket
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = data.aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-runs"
    status = "Enabled"

    filter {
      prefix = "runs/"
    }

    expiration {
      days = 90
    }
  }

  # The live loop writes one immutable history point per poll, roughly 1440
  # objects a day, so these expire fast.
  rule {
    id     = "expire-live-history"
    status = "Enabled"

    filter {
      prefix = "live/history/"
    }

    expiration {
      days = 30
    }
  }

  # Bucket-wide hygiene; snapshots/ and datasets/ current versions are kept
  # indefinitely because no rule expires them.
  rule {
    id     = "bucket-hygiene"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_ecs_cluster" "this" {
  name = var.project
}

resource "aws_dynamodb_table" "forecaster" {
  name         = "${var.project}-forecaster"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

resource "aws_sesv2_email_identity" "sender" {
  count = var.ses_sender_email == "" ? 0 : 1

  email_identity = var.ses_sender_email
}

module "engine" {
  source = "../../modules/engine"

  project            = var.project
  region             = var.region
  vpc_id             = data.aws_vpc.default.id
  bucket_name        = data.aws_s3_bucket.artifacts.bucket
  bucket_arn         = data.aws_s3_bucket.artifacts.arn
  dynamo_table_name  = aws_dynamodb_table.forecaster.name
  dynamo_table_arn   = aws_dynamodb_table.forecaster.arn
  image_tag          = var.engine_image_tag
  cpu                = var.engine_cpu
  memory             = var.engine_memory
  log_retention_days = var.log_retention_days
  run_policy         = var.run_policy
}

module "scheduler" {
  source = "../../modules/scheduler"

  project                      = var.project
  region                       = var.region
  account_id                   = data.aws_caller_identity.current.account_id
  cluster_arn                  = aws_ecs_cluster.this.arn
  task_definition_arn          = module.engine.task_definition_arn
  task_definition_family       = module.engine.task_definition_family
  agent_task_definition_arn    = module.engine.agent_task_definition_arn
  agent_task_definition_family = module.engine.agent_task_definition_family
  task_role_arn                = module.engine.task_role_arn
  task_execution_role_arn      = module.engine.task_execution_role_arn
  subnets                      = data.aws_subnets.default.ids
  security_group_id            = module.engine.security_group_id
  state                        = var.schedule_state
  schedule_expression          = var.schedule_cron
  agent_state                  = var.agent_schedule_state
  agent_schedule_windows       = var.agent_schedule_windows
}

module "backend_api" {
  source = "../../modules/backend-api"

  project                       = var.project
  region                        = var.region
  account_id                    = data.aws_caller_identity.current.account_id
  vpc_id                        = data.aws_vpc.default.id
  subnets                       = data.aws_subnets.default.ids
  cluster_id                    = aws_ecs_cluster.this.id
  cluster_arn                   = aws_ecs_cluster.this.arn
  cluster_name                  = aws_ecs_cluster.this.name
  bucket_name                   = data.aws_s3_bucket.artifacts.bucket
  bucket_arn                    = data.aws_s3_bucket.artifacts.arn
  dynamo_table_name             = aws_dynamodb_table.forecaster.name
  dynamo_table_arn              = aws_dynamodb_table.forecaster.arn
  schedule_name                 = module.scheduler.schedule_name
  schedule_arn                  = module.scheduler.schedule_arn
  scheduler_role_arn            = module.scheduler.scheduler_role_arn
  engine_task_definition_family = module.engine.task_definition_family
  agent_task_definition_family  = module.engine.agent_task_definition_family
  engine_task_role_arn          = module.engine.task_role_arn
  engine_security_group_id      = module.engine.security_group_id
  task_execution_role_arn       = module.engine.task_execution_role_arn
  task_execution_role_name      = module.engine.task_execution_role_name
  image_tag                     = var.backend_image_tag
  cpu                           = var.backend_cpu
  memory                        = var.backend_memory
  desired_count                 = var.backend_desired_count
  log_retention_days            = var.log_retention_days
  live_data_secret_arns         = module.engine.live_data_secret_arns
  run_policy                    = var.run_policy
  enable_tunnel                 = var.enable_tunnel
  # Constructed, not referenced: a module reference here would cycle through alerting.
  alerts_topic_arn = "arn:aws:sns:${var.region}:${data.aws_caller_identity.current.account_id}:${var.project}-alerts"
}

module "alerting" {
  source = "../../modules/alerting"

  project               = var.project
  region                = var.region
  account_id            = data.aws_caller_identity.current.account_id
  monthly_budget_usd    = var.monthly_budget_usd
  alert_email           = var.alert_email
  scheduler_role_arn    = module.scheduler.scheduler_role_arn
  scheduler_role_name   = module.scheduler.scheduler_role_name
  backend_run_role_arn  = module.backend_api.task_role_arn
  backend_run_role_name = module.backend_api.task_role_name
  github_ops_role_arn   = module.release_oidc.ops_role_arn
  github_ops_role_name  = module.release_oidc.ops_role_name
  cluster_arn           = aws_ecs_cluster.this.arn
  # Only ECS-launched families can fail as tasks; live and archive are in-process now.
  engine_task_definition_families = [
    module.engine.task_definition_family,
    module.engine.agent_task_definition_family,
  ]
}

module "release_oidc" {
  source = "../../modules/release-oidc"

  project                       = var.project
  region                        = var.region
  account_id                    = data.aws_caller_identity.current.account_id
  github_repo                   = var.github_repo
  engine_ecr_repository_arn     = module.engine.ecr_repository_arn
  backend_ecr_repository_arn    = module.backend_api.ecr_repository_arn
  engine_task_definition_family = module.engine.task_definition_family
  engine_task_role_arn          = module.engine.task_role_arn
  backend_task_role_arn         = module.backend_api.task_role_arn
  task_execution_role_arn       = module.engine.task_execution_role_arn
  backend_service_arn           = module.backend_api.service_arn
  cluster_arn                   = aws_ecs_cluster.this.arn
}
