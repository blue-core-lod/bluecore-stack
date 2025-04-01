output "aws_acm_certificate_dev_name" {
  value     = aws_acm_certificate.dev_cert.domain_validation_options.*.resource_record_name
}

output "aws_acm_certificate_dev_value" {
  value     = aws_acm_certificate.dev_cert.domain_validation_options.*.resource_record_value
  sensitive = true
}
