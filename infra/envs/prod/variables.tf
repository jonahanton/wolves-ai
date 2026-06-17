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

variable "agent_schedule_state" {
  description = "Creation-time agent schedule state. Disabled by default for the same first-apply reason as schedule_state; enabling is an explicit operational act (see infra/RUNBOOK.md)."
  type        = string
  default     = "DISABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.agent_schedule_state)
    error_message = "agent_schedule_state must be ENABLED or DISABLED."
  }
}

variable "agent_schedule_windows" {
  description = "Date-windowed agent run crons matching the operator's travel: 06:30 UTC reads as UK morning; 10:00 UTC clears every night game (extra time included) and reads as US morning during the 24 Jun to 13 Jul trip."
  type = list(object({
    name  = string
    cron  = string
    start = optional(string)
    end   = optional(string)
  }))
  default = [
    { name = "uk-opening", cron = "cron(30 6 * * ? *)", end = "2026-06-23T23:59:59Z" },
    { name = "us-trip", cron = "cron(0 10 * * ? *)", start = "2026-06-24T00:00:00Z", end = "2026-07-13T23:59:59Z" },
    { name = "uk-finals", cron = "cron(30 6 * * ? *)", start = "2026-07-14T00:00:00Z" },
  ]
}

variable "run_policy" {
  description = "The operator-facing spend-policy and live-cadence configuration surface; rendered into the engine task environment. `python -m wolves.run_policy` prints the calendar derived from these values."
  type = object({
    agent_ceiling_opening_usd              = number
    agent_ceiling_big_group_usd            = number
    agent_ceiling_group_usd                = number
    agent_ceiling_rest_usd                 = number
    agent_ceiling_r32_r16_usd              = number
    agent_ceiling_qf_final_usd             = number
    agent_ceiling_single_game_discount_usd = number
    agent_big_team_count                   = number
    live_poll_interval_s                   = number
    live_stale_after_s                     = number
    live_idle_interval_s                   = number
    live_idle_grace_hours                  = number
  })
  default = {
    agent_ceiling_opening_usd              = 5.00
    agent_ceiling_big_group_usd            = 3.00
    agent_ceiling_group_usd                = 2.00
    agent_ceiling_rest_usd                 = 2.00
    agent_ceiling_r32_r16_usd              = 3.50
    agent_ceiling_qf_final_usd             = 5.00
    agent_ceiling_single_game_discount_usd = 1.00
    agent_big_team_count                   = 8
    live_poll_interval_s                   = 60
    live_stale_after_s                     = 150
    live_idle_interval_s                   = 900
    live_idle_grace_hours                  = 6
  }
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

# 1 vCPU / 2GB: the backend hosts the fitted engine, interactive sims and the
# in-process live and archive loops.
variable "backend_cpu" {
  type    = number
  default = 1024
}

variable "backend_memory" {
  type    = number
  default = 2048
}

variable "backend_desired_count" {
  description = "Backend API task count; 0 parks the service without destroying it, and the module refuses anything above 1 (single-writer pin for the in-process loops)."
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

variable "enable_tunnel" {
  description = "Front the backend with a cloudflared sidecar over an outbound tunnel and close the public app port."
  type        = bool
  default     = false
}
