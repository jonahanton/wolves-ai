variable "project" {
  description = "Resource name prefix."
  type        = string
  default     = "wolves"
}

variable "region" {
  description = "Primary region. Billing-scoped services (Budgets, billing alarms) are us-east-1 endpoints the provider routes to automatically."
  type        = string
  default     = "eu-west-2"
}

variable "github_repo" {
  description = "GitHub owner/name trusted by the OIDC roles."
  type        = string
  default     = "jonahanton/wolves-ai"
}

variable "schedule_state" {
  description = "Creation-time schedule state only; runtime flips go through the backend admin API. Disabled by default so a first apply against an empty ECR cannot crash-loop; enabling is an explicit operational act (see infra/RUNBOOK.md)."
  type        = string
  default     = "DISABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.schedule_state)
    error_message = "schedule_state must be ENABLED or DISABLED."
  }
}

variable "schedule_cron" {
  description = "Creation-time daily run cron (UTC) only; runtime edits go through the backend admin API."
  type        = string
  default     = "cron(0 11 * * ? *)"
}

variable "archive_schedule_state" {
  description = "Creation-time archive schedule state. Disabled by default for the same first-apply reason as schedule_state."
  type        = string
  default     = "DISABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.archive_schedule_state)
    error_message = "archive_schedule_state must be ENABLED or DISABLED."
  }
}

variable "archive_schedule_cron" {
  description = "Creation-time odds archive cron (UTC)."
  type        = string
  default     = "cron(0 8,14,18,22 * * ? *)"
}

variable "engine_image_tag" {
  description = "Engine image tag the task definition points at."
  type        = string
  default     = "latest"
}

variable "engine_cpu" {
  type    = number
  default = 1024
}

variable "engine_memory" {
  type    = number
  default = 2048
}

variable "backend_image_tag" {
  description = "Backend image tag the task definition points at."
  type        = string
  default     = "latest"
}

variable "backend_cpu" {
  type    = number
  default = 256
}

variable "backend_memory" {
  type    = number
  default = 512
}

variable "backend_desired_count" {
  description = "Backend API task count; 0 parks the service without destroying it. Zero by default so a first apply against an empty ECR and versionless secrets cannot crash-loop."
  type        = number
  default     = 0
}

variable "monthly_budget_usd" {
  description = "Hard monthly cap; the budget action disables the daily run at 100 percent."
  type        = number
  default     = 40
}

variable "alert_email" {
  description = "Email for budget and kill-switch SNS alerts; empty skips the subscription."
  type        = string
  default     = ""
}

variable "ses_sender_email" {
  description = "Sender identity for magic-link sign-in emails; empty skips creation."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "bucket" {
  description = "Artifact bucket the production stack reads and writes."
  type        = string
  default     = "wolves-superforecaster-prod"
}
