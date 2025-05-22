terraform {
  backend "s3" {
    bucket         = "bluecore-tfstate"
    key            = "root/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    profile        = "bluecore"
    dynamodb_table = "bluecore_tf_lockid"
  }
}
