output "aws_region" {
  value = var.region
}

output "bucket" {
  value = data.aws_s3_bucket.artifacts.bucket
}
