# The artifact buckets (prod and dev) were created manually with versioning
# on and public access blocked; terraform references prod, never manages it.
data "aws_s3_bucket" "artifacts" {
  bucket = var.bucket
}
