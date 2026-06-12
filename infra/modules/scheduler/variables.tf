variable "project" {
  type = string
}

variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "cluster_arn" {
  type = string
}

variable "task_definition_arn" {
  type = string
}

variable "task_definition_family" {
  type = string
}

variable "agent_task_definition_arn" {
  type = string
}

variable "agent_task_definition_family" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "task_execution_role_arn" {
  type = string
}

variable "subnets" {
  type = list(string)
}

variable "security_group_id" {
  type = string
}

variable "initial_state" {
  description = "Creation-time schedule state; runtime flips go through UpdateSchedule and are never reconciled."
  type        = string
}

variable "initial_cron" {
  description = "Creation-time cron; runtime edits go through UpdateSchedule and are never reconciled."
  type        = string
}

variable "agent_initial_state" {
  description = "Creation-time agent schedule state."
  type        = string
  default     = "DISABLED"
}

variable "agent_schedule_windows" {
  description = "Date-windowed agent run crons so the morning run lands in the operator's local timezone."
  type = list(object({
    name  = string
    cron  = string
    start = optional(string)
    end   = optional(string)
  }))
}
