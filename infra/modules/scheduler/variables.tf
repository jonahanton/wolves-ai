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
