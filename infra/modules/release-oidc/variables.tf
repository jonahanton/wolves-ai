variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "github_repo" {
  description = "GitHub owner/name trusted by the OIDC roles."
  type        = string
}

variable "engine_ecr_repository_arn" {
  type = string
}

variable "backend_ecr_repository_arn" {
  type = string
}

variable "engine_task_definition_family" {
  type = string
}

variable "engine_task_role_arn" {
  type = string
}

variable "backend_task_role_arn" {
  type = string
}

variable "task_execution_role_arn" {
  type = string
}

variable "backend_service_arn" {
  type = string
}

variable "cluster_arn" {
  type = string
}
