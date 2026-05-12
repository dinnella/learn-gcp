terraform {
  required_version = ">= 1.6.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
  }
  backend "gcs" {}
}

provider "cloudflare" {
  # Reads CLOUDFLARE_API_TOKEN from env. Mint a zone-scoped token with:
  #   Zone:DNS:Edit, Zone:Zone Settings:Edit, Zone:Zone WAF:Edit, Zone:Transform Rules:Edit
}
