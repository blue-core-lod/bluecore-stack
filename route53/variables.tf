variable "account_id" {
    default = "253708211841"
}

variable "sul_dlss_profile" {
  description = "sul_dlss profile to use when running"
}

variable "domain" {
    default = "bcld.info"
}

# Dev ALB, alias and CNAME records created in https://github.com/blue-core-lod/terraform
variable "dev_bcld_alb_zone_id" {
    default = "Z1H1FL5HABSF5"
}

variable "dev_bcld_cname_name" {
    default = "_424fde8dcf5033d0f42c8eca5460f80d.dev.bcld.info"
}

variable "dev_bcld_cname_value_vault" {
  default = "secret/data/aws/bluecore/dev_cname"
}
