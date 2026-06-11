output "release_role_arn" {
  value = aws_iam_role.github_release.arn
}

output "ops_role_arn" {
  value = aws_iam_role.github_ops.arn
}
