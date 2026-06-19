variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnets" {
  type = list(string)
}

variable "cluster_id" {
  type = string
}

variable "cluster_arn" {
  type = string
}

variable "cluster_name" {
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

variable "schedule_name" {
  type = string
}

variable "schedule_arn" {
  type = string
}

variable "scheduler_role_arn" {
  type = string
}

variable "engine_task_definition_family" {
  type = string
}

variable "agent_task_definition_family" {
  type = string
}

variable "engine_task_role_arn" {
  type = string
}

variable "engine_security_group_id" {
  type = string
}

variable "task_execution_role_arn" {
  type = string
}

variable "task_execution_role_name" {
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

# Single-writer pin: the in-process loops must never run twice; 0 still parks the service.
variable "desired_count" {
  type = number

  validation {
    condition     = var.desired_count <= 1
    error_message = "The backend runs in-process polling loops and must never scale past one task."
  }
}

variable "alerts_topic_arn" {
  type = string
}

variable "live_data_secret_arns" {
  description = "Secrets Manager ARNs for API_FOOTBALL_KEY and ODDS_API_KEY; never the Anthropic key."
  type        = map(string)
}

variable "run_policy" {
  description = "Live-ops knobs mirrored into the backend so the in-process loops and the policy calendar match the engine's."
  type = object({
    agent_ceiling_opening_usd   = number
    agent_ceiling_big_group_usd = number
    agent_ceiling_group_usd     = number
    agent_ceiling_rest_usd      = number
    agent_ceiling_r32_r16_usd   = number
    agent_ceiling_qf_final_usd  = number
    agent_big_team_count        = number
    live_poll_interval_s        = number
    live_stale_after_s          = number
    live_idle_interval_s        = number
    live_idle_grace_hours       = number
  })
}

variable "log_retention_days" {
  type = number
}

variable "enable_tunnel" {
  description = "Run a cloudflared sidecar over an outbound tunnel and close the public app port."
  type        = bool
  default     = false
}

variable "cloudflared_image" {
  type    = string
  default = "cloudflare/cloudflared:2025.6.1"
}
