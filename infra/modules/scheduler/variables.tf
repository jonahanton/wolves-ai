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

variable "agent_schedule_windows" {
  description = "Agent schedules aligned to the operator's local timezone."
  type = list(object({
    name                = string
    schedule_expression = string
    state               = optional(string, "DISABLED")
    start               = optional(string)
    end                 = optional(string)
  }))

  validation {
    condition = alltrue([
      for window in var.agent_schedule_windows :
      contains(["ENABLED", "DISABLED"], window.state) &&
      (window.state == "DISABLED" || (window.start != null && window.end != null))
    ])
    error_message = "Agent schedule state must be ENABLED or DISABLED, and enabled schedules require start and end bounds."
  }
}
