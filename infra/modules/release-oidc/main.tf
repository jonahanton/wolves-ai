resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_release_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/tags/prod-*"]
    }
  }
}

resource "aws_iam_role" "github_release" {
  name               = "${var.project}-github-release"
  assume_role_policy = data.aws_iam_policy_document.github_release_assume.json
}

data "aws_iam_policy_document" "github_release" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [var.engine_ecr_repository_arn, var.backend_ecr_repository_arn]
  }

  # RegisterTaskDefinition supports no resource scoping.
  statement {
    actions   = ["ecs:DescribeTaskDefinition", "ecs:RegisterTaskDefinition"]
    resources = ["*"]
  }

  statement {
    actions   = ["ecs:UpdateService", "ecs:DescribeServices"]
    resources = [var.backend_service_arn]
  }

  statement {
    actions   = ["iam:PassRole"]
    resources = [var.task_execution_role_arn, var.engine_task_role_arn, var.backend_task_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "github_release" {
  name   = "release"
  role   = aws_iam_role.github_release.id
  policy = data.aws_iam_policy_document.github_release.json
}

data "aws_iam_policy_document" "github_ops_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # workflow_dispatch on main presents the branch ref as the subject.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_ops" {
  name               = "${var.project}-github-ops"
  assume_role_policy = data.aws_iam_policy_document.github_ops_assume.json
}

data "aws_iam_policy_document" "github_ops" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = ["arn:aws:ecs:${var.region}:${var.account_id}:task-definition/${var.engine_task_definition_family}:*"]
  }

  statement {
    actions   = ["iam:PassRole"]
    resources = [var.task_execution_role_arn, var.engine_task_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "github_ops" {
  name   = "run-engine"
  role   = aws_iam_role.github_ops.id
  policy = data.aws_iam_policy_document.github_ops.json
}
