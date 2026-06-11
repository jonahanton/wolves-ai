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
