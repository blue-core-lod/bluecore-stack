#
# Allows sul_dlss root account to query certs if needed
#
resource "aws_iam_role" "validate_cert_dlss" {
  name               = "validate_cert_dlss"
  assume_role_policy = data.aws_iam_policy_document.validate_cert_dlss.json
  provider           = aws.users_root
}

resource "aws_iam_role_policy_attachment" "validate_cert_access" {
  policy_arn = aws_iam_policy.validate_cert_access.arn
  role       = aws_iam_role.validate_cert_dlss.name
  provider   = aws.users_root
}

# allow sul-dlss account to assume this role
data "aws_iam_policy_document" "validate_cert_dlss" {
  statement {
    sid     = "1"
    actions = ["sts:AssumeRole"]

    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::253708211841:root",
      ]
    }
  }
}

resource "aws_iam_policy" "validate_cert_access" {
  name     = "validate_cert_access"
  policy   = data.aws_iam_policy_document.validate_cert_access.json
  provider = aws.users_root
}

data "aws_iam_policy_document" "validate_cert_access" {
  statement {
    sid = "ListACMValidation"
    actions = [
      "acm:DescribeCertificate",
      "acm:ListCertificates",
      "acm:GetCertificate",
      "acm:ListTagsForCertificate",
    ]
    resources = ["*"]
  }
}
