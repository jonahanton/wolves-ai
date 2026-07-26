variable "region" {
  description = "Region containing the private archive."
  type        = string
  default     = "eu-west-2"
}

variable "bucket" {
  description = "Private source archive retained after runtime retirement."
  type        = string
  default     = "wolves-superforecaster-prod"
}
