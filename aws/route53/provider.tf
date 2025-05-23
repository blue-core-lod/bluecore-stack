provider "aws" {
  region  = "us-west-2"
  profile = var.sul_dlss_profile

  default_tags {
    tags = {
      project     = "bluecore"
      terraform   = "true"
    }
  }
}

provider "aws" {
  alias   = "cert"
  region  = "us-west-2"
  profile = var.sul_dlss_profile

  assume_role {
    role_arn = "arn:aws:iam::038462753403:role/validate_cert_dlss"
  }
}

provider "vault" {
}
