terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  backend "s3" {
    bucket       = "wolves-terraform-state"
    key          = "prod/terraform.tfstate"
    region       = "eu-west-2"
    use_lockfile = true
  }
}
