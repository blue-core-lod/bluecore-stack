# Create role to allow ec2 instance to perform ses functions
data "aws_iam_policy_document" "bcld_ses_ec2_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "bcld_ses_ec2_role" {
  name               = "bcld-ses-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.bcld_ses_ec2_assume_role.json
}

resource "aws_iam_instance_profile" "bcld_ses_ec2_role" {
  name = "bcld-ses-ec2-profile"
  role = aws_iam_role.bcld_ses_ec2_role.name
}

resource "aws_iam_policy" "bcld_ses_ec2_policy" {
  name = "bcld-ses-ec2-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "SESEmailSend"
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = [
          "arn:aws:ses:${var.region}:${var.users_account_id}:*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bcld_ses_ec2_policy_attach" {
  role       = aws_iam_role.bcld_ses_ec2_role.name
  policy_arn = aws_iam_policy.bcld_ses_ec2_policy.arn
}
