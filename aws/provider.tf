terraform {
  required_version = "~> 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.89.0"
    }
  }
}

# need unaliased provider as default
provider "aws" {
  region  = var.region
  profile = var.profile
}

provider "aws" {
  alias   = "users_root"
  region  = var.region
  profile = var.profile
}
