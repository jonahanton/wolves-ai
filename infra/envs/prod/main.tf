provider "aws" {
  region = var.region
}

data "aws_s3_bucket" "artifacts" {
  bucket = var.bucket
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = data.aws_s3_bucket.artifacts.id

  rule {
    id     = "archive-hygiene"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
