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
