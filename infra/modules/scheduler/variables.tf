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

variable "archive_task_definition_arn" {
  type = string
}

variable "archive_task_definition_family" {
  type = string
}

variable "agent_task_definition_arn" {
  type = string
}

variable "agent_task_definition_family" {
  type = string
}

variable "live_task_definition_arn" {
  type = string
}

variable "live_task_definition_family" {
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

variable "archive_initial_state" {
  description = "Creation-time archive schedule state."
  type        = string
}

variable "archive_initial_cron" {
  description = "Creation-time odds archive cron."
  type        = string
}

variable "agent_initial_state" {
  description = "Creation-time agent schedule state."
  type        = string
  default     = "DISABLED"
}

variable "agent_initial_cron" {
  description = "Creation-time agent run cron; 06:30 UTC sits before any kickoff."
  type        = string
  default     = "cron(30 6 * * ? *)"
}

variable "live_initial_state" {
  description = "Creation-time live window schedule state."
  type        = string
  default     = "DISABLED"
}

variable "live_initial_cron" {
  description = "Creation-time live window cron; 15:00 UTC precedes the earliest 16:00 UTC kickoff and the task exits itself when no kickoff falls within the idle grace."
  type        = string
  default     = "cron(0 15 * * ? *)"
}
