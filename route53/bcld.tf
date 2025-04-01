data "aws_route53_zone" "selected" {
  name         = var.domain
  private_zone = false
}

resource "aws_route53_record" "dev_bcld_a_rec" {
  zone_id = data.aws_route53_zone.selected.id
  name    = "dev.bcld.info"
  type    = "A"

  alias {
    name                   = "bluecore-dev-alb-2095725723.us-west-2.elb.amazonaws.com."
    zone_id                = var.dev_bcld_alb_zone_id
    evaluate_target_health = true
  }
}

data "vault_generic_secret" "dev_bcld_cname" {
  path = var.dev_bcld_cname_value_vault
}

resource "aws_route53_record" "dev_bcld_cname" {
  zone_id = data.aws_route53_zone.selected.id
  name    = var.dev_bcld_cname_name
  type    = "CNAME"
  ttl     = 300
  records = [data.vault_generic_secret.dev_bcld_cname.data["content"]]
}

# Not used but shows certificates but not cname info
data "aws_acm_certificate" "dev_bcld_info" {
  provider = aws.cert
  domain   = "dev.bcld.info"
}
