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

variable "desired_count" {
  type = number
}

variable "log_retention_days" {
  type = number
}
