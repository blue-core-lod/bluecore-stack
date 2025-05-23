output "dev_cname_value" {
  value     = data.vault_generic_secret.dev_bcld_cname.data["content"]
  sensitive = true
}
