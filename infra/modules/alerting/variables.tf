variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "monthly_budget_usd" {
  type = number
}

variable "alert_email" {
  description = "Email for budget and failure alerts; empty skips the subscription."
  type        = string
}

variable "scheduler_role_arn" {
  type = string
}

variable "scheduler_role_name" {
  type = string
}

variable "backend_run_role_arn" {
  type = string
}

variable "backend_run_role_name" {
  type = string
}

variable "github_ops_role_arn" {
  type = string
}

variable "github_ops_role_name" {
  type = string
}

variable "cluster_arn" {
  type = string
}

variable "engine_task_definition_family" {
  type = string
}

variable "archive_task_definition_family" {
  type = string
}
