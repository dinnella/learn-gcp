# Cloudflare edge for Next3k LevelUp.
# DNS (proxied) → Transform Rule injecting X-Edge-Auth → Cloud Run origin.
# Per-IP rate limit + zone TLS settings, all on Free plan.
# Note: Cloudflare Managed Ruleset (WAF) requires a paid plan — not included.

# ----- Zone lookup by name (avoids hardcoding the zone ID) -----
# The token only needs to be able to list zones (read) + write to the target zone.
# Use zones[0].id (not .id) per https://developers.cloudflare.com/terraform/troubleshooting/authentication-error-dns-records/
data "cloudflare_zones" "this" {
  filter {
    name = var.zone_name
  }
}

locals {
  zone_id = data.cloudflare_zones.this.zones[0].id
}

# ----- DNS: proxied CNAME so Cloudflare actually fronts the traffic -----
resource "cloudflare_record" "app" {
  zone_id = local.zone_id
  name    = var.hostname
  type    = "CNAME"
  content = var.origin_hostname
  proxied = true
  ttl     = 1 # 'auto' when proxied
  comment = "Next3k LevelUp → Cloud Run origin"
}

# ----- Zone-wide TLS hardening -----
resource "cloudflare_zone_settings_override" "tls" {
  zone_id = local.zone_id
  settings {
    ssl                      = "strict" # Full (strict): origin must present a valid cert (Cloud Run does)
    always_use_https         = "on"
    automatic_https_rewrites = "on"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    opportunistic_encryption = "on"
    browser_check            = "on"
  }
}

# ----- Transform Rule: inject X-Edge-Auth on every request to our hostname -----
# This is what gates Cloud Run: the origin's middleware rejects any request
# that doesn't carry this exact header value.
resource "cloudflare_ruleset" "edge_auth" {
  zone_id     = local.zone_id
  name        = "edge-auth-injector"
  description = "Inject shared-secret header so Cloud Run accepts only Cloudflare-proxied traffic."
  kind        = "zone"
  phase       = "http_request_late_transform"

  rules {
    enabled     = true
    description = "Inject X-Edge-Auth for ${var.hostname}"
    expression  = "(http.host eq \"${var.hostname}\")"
    action      = "rewrite"
    action_parameters {
      headers {
        name      = "X-Edge-Auth"
        operation = "set"
        value     = var.edge_shared_secret
      }
    }
  }
}

# ----- Per-IP rate limit (Free plan: 1 rule allowed per zone) -----
resource "cloudflare_ruleset" "rate_limit" {
  zone_id     = local.zone_id
  name        = "rate-limit-${replace(var.hostname, ".", "-")}"
  description = "Per-IP rate limit for ${var.hostname}."
  kind        = "zone"
  phase       = "http_ratelimit"

  rules {
    enabled     = true
      description = "${var.rate_limit_rp10s} req/10s/IP"
    expression  = "(http.host eq \"${var.hostname}\")"
    action      = "block"
    ratelimit {
      # cf.colo.id is required: Cloudflare counts requests per colo, not globally.
      characteristics     = ["cf.colo.id", "ip.src"]
      # Free plan only supports period=10 (10-second window).
      period              = 10
      requests_per_period = var.rate_limit_rp10s
      mitigation_timeout  = 60
    }
  }
}
