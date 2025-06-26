resource "aws_sns_topic" "bcld_email_sns" {
  name = "bcld_receive_mail"
}

# Subscription endpoint will receive bounce and complaint emails
resource "aws_sns_topic_subscription" "bcld_sns_topic_subscription" {
  topic_arn = aws_sns_topic.bcld_email_sns.arn
  protocol  = "email"
  endpoint  = "kamchan@stanford.edu"
}
