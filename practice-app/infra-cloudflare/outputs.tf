output "fqdn" {
  value = var.hostname
}

output "proxied" {
  value = cloudflare_dns_record.app.proxied
}

output "public_url" {
  value = "https://${var.hostname}"
}
