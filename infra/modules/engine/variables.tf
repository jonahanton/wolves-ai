variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "bucket_name" {
  type = string
}

variable "bucket_arn" {
  type = string
}

variable "dynamo_table_name" {
  type = string
}

variable "dynamo_table_arn" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "cpu" {
  type = number
}

variable "memory" {
  type = number
}

variable "log_retention_days" {
  type = number
}

variable "run_policy" {
  description = "Agent spend ceilings and live polling cadence rendered into the engine environment."
  type = object({
    agent_ceiling_base_usd           = number
    agent_ceiling_rest_day_usd       = number
    agent_ceiling_per_result_usd     = number
    agent_ceiling_knockout_today_usd = number
    agent_ceiling_focus_bonus_usd    = number
    agent_ceiling_policy_max_usd     = number
    live_poll_interval_s             = number
    live_stale_after_s               = number
    live_idle_interval_s             = number
    live_idle_grace_hours            = number
  })
  default = {
    agent_ceiling_base_usd           = 0.75
    agent_ceiling_rest_day_usd       = 0.50
    agent_ceiling_per_result_usd     = 0.10
    agent_ceiling_knockout_today_usd = 0.40
    agent_ceiling_focus_bonus_usd    = 0.50
    agent_ceiling_policy_max_usd     = 4.00
    live_poll_interval_s             = 60
    live_stale_after_s               = 150
    live_idle_interval_s             = 900
    live_idle_grace_hours            = 6
  }
}
