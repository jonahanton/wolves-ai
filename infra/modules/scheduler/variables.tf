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

variable "state" {
  description = "Desired schedule state."
  type        = string
}

variable "schedule_expression" {
  description = "Desired daily schedule expression."
  type        = string
}

variable "agent_state" {
  description = "Desired agent schedule state."
  type        = string
  default     = "DISABLED"
}

variable "agent_schedule_windows" {
  description = "Agent schedules aligned to the operator's local timezone."
  type = list(object({
    name                = string
    schedule_expression = string
    start               = optional(string)
    end                 = optional(string)
  }))
}
