terraform {
  backend "s3" {
    bucket         = "state.root.sul.stanford.edu"
    key            = "production/bluecore.tfstate"
    region         = "us-west-2"
    profile        = "users"
    dynamodb_table = "root"
    encrypt        = "true"
    assume_role = {
      role_arn       = "arn:aws:iam::975822730059:role/UsersAdminRole"
    }
    kms_key_id     = "arn:aws:kms:us-west-2:253708211841:alias/terraform-encryption-key"
  }
}
