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
  description = "GitHub owner/name trusted by the release OIDC role."
  type        = string
  default     = "jonahanton/wolves-ai"
}

variable "schedule_state" {
  description = "Kill switch for the daily run schedule."
  type        = string
  default     = "ENABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.schedule_state)
    error_message = "schedule_state must be ENABLED or DISABLED."
  }
}

variable "schedule_cron" {
  description = "Daily run cron, UTC."
  type        = string
  default     = "cron(0 11 * * ? *)"
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
  description = "Backend API task count; 0 parks the service without destroying it."
  type        = number
  default     = 1
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
