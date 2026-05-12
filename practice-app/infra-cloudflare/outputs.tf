output "fqdn" {
  value = cloudflare_record.app.hostname
}

output "proxied" {
  value = cloudflare_record.app.proxied
}

output "public_url" {
  value = "https://${var.hostname}"
}
