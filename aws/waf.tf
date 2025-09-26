resource "aws_wafv2_web_acl" "bcld_waf" {
  name  = "bcld-waf-acl"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 10

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        rule_action_override {
          action_to_use {
            count {}
          }

          name = "GenericLFI_BODY"
        }

        rule_action_override {
          action_to_use {
            count {}
          }

          name = "SizeRestrictions_BODY"
        }

        rule_action_override {
          action_to_use {
            count {}
          }

          name = "CrossSiteScripting_BODY"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 20

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesAmazonIpReputationListMetric"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesLinuxRuleSet"
    priority = 30

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesLinuxRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesLinuxRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  #this rule has dollar cost
#  rule {
#    name     = "AWSManagedRulesBotControlRuleSet"
#    priority = 5
#
#    override_action {
#      none {}
#    }
#
#    statement {
#      managed_rule_group_statement {
#        name        = "AWSManagedRulesBotControlRuleSet"
#        vendor_name = "AWS"
#
#        rule_action_override {
#          action_to_use {
#            count {}
#          }
#
#          name = "SignalNonBrowserUserAgent"
#        }
#      }
#    }
#
#    visibility_config {
#      cloudwatch_metrics_enabled = true
#      metric_name                = "AWSManagedRulesBotControlRuleSetMetric"
#      sampled_requests_enabled   = true
#    }
#  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "bcld-waf-metric"
    sampled_requests_enabled   = true
  }
}
