variable "users_account_id" {
  description = "Account ID for current environment"
  default     = "038462753403"
}

variable "ses_domain" {
  default = "bcld.info"
}

variable "region" {
  default = "us-west-2"
}

variable "profile" {
  description = "User profile to use when running"
}
