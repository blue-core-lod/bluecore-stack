resource "aws_iam_user" "edsu" {
  provider      = aws.users_root
  name          = "edsu"
  force_destroy = true
}

resource "aws_iam_user" "jduncan" {
  provider      = aws.users_root
  name          = "jduncan"
  force_destroy = true
}

resource "aws_iam_user" "jpnelson" {
  provider      = aws.users_root
  name          = "jpnelson"
  force_destroy = true
}

resource "aws_iam_group_membership" "developers" {
  provider = aws.users_root
  name     = "developer-membership"

  users = [
    "edsu",
    "jduncan",
    "jpnelson",
  ]

  group = "Developers"
}

# Define a group for developers.
resource "aws_iam_group" "developers" {
  provider = aws.users_root
  name     = "Developers"
}

resource "aws_iam_policy" "developers" {
  provider    = aws.users_root
  name        = "Developers"
  description = "Developer allowed operations"
  policy      = data.aws_iam_policy_document.developers.json
}

resource "aws_iam_policy_attachment" "attach_developers" {
  provider   = aws.users_root
  name       = "Developers"
  groups     = [aws_iam_group.developers.name]
  policy_arn = aws_iam_policy.developers.arn
}

# Policy document for our developer group, with multiple statements about what
# a member of the group can do listed below.
data "aws_iam_policy_document" "developers" {

  statement {
    sid = "AllowActionsForDevelopers"

    actions = [
      "acm:DescribeCertificate",
      "acm:ListTagsForCertificate",
      "acm:RequestCertificate",
      "application-autoscaling:*",
      "autoscaling:*",
      "backup:*",
      "backup-storage:*",
      "batch:*",
      "cloudfront:*",
      "cloudtrail:*",
      "cloudwatch:*",
      "events:*",
      "logs:*",
      "codebuild:*",
      "codecommit:*",
      "codedeploy:*",
      "codepipeline:*",
      "dynamodb:*",
      "ec2:*",
      "ecr:*",
      "ecs:*",
      "ec2messages:*",
      "eks:*",
      "elasticloadbalancing:*",
      "s3:*",
    ]

    resources = ["*"]
  }

  statement {
    sid = "AllowUsersAllActionsForCredentials"

    actions = [
      "iam:List*",
      "iam:GetAccountSummary",
      "iam:GenerateServiceLastAccessedDetails",
      "iam:*LoginProfile",
      "iam:*AccessKey*",
      "iam:*SigningCertificate*",
      "iam:ListAccessKeys",
      "iam:ChangePassword",
      "iam:CreateAccessKey",
      "iam:DeleteAccessKey",
      "iam:GetAccessKeyLastUsed",
    ]

    resources = [
      "arn:aws:iam::${var.users_account_id}:user/$${aws:username}",
      "arn:aws:iam::${var.users_account_id}:mfa/$${aws:username}",
    ]
  }

  statement {
    sid = "AllowUsersToSeeStatsOnIAMConsoleDashboard"

    actions = [
      "iam:GetAccount*",
      "iam:GetUser",
      "iam:ListUsers",
      "iam:ListAccount*",
      "iam:ListGroups",
      "iam:GetGroup",
      "iam:ListRole*",
      "iam:GetRole",
      "iam:ListAttachedRolePolicies",
      "iam:ListGroupPolicies",
      "iam:ListAttachedGroupPolicies",
      "iam:ListPolicies",
      "iam:ListPolicyVersions",
      "iam:ListEntities*",
      "iam:GetPolicy*",
      "iam:GetServiceLastAccessedDetails",
    ]

    resources = [
      "*",
    ]
  }

  statement {
    sid = "AllowIndividualUserToCreateOnlyTheirOwnMFA"

    actions = [
      "iam:CreateVirtualMFADevice",
      "iam:DeleteVirtualMFADevice",
      "iam:EnableMFADevice",
      "iam:ResyncMFADevice",
    ]

    resources = [
      "arn:aws:iam::${var.users_account_id}:mfa/$${aws:username}",
      "arn:aws:iam::${var.users_account_id}:user/$${aws:username}",
    ]
  }

  # Only let a user deactivate MFA by using MFA, to avoid escalation attacks.
  statement {
    sid = "AllowIndividualUserToDeactivateOnlyTheirOwnMFAOnlyWhenUsingMFA"

    actions = [
      "iam:DeactivateMFADevice",
    ]

    resources = [
      "arn:aws:iam::${var.users_account_id}:mfa/$${aws:username}",
      "arn:aws:iam::${var.users_account_id}:user/$${aws:username}",
    ]

    condition {
      test     = "Bool"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["true"]
    }
  }

}
