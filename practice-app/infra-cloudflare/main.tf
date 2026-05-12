# Cloudflare edge for Next3k LevelUp.
# DNS (proxied) → Transform Rule injecting X-Edge-Auth → Cloud Run origin.
# WAF (managed ruleset) + per-IP rate limit + zone TLS settings, all on Free plan.

# ----- DNS: proxied CNAME so Cloudflare actually fronts the traffic -----
resource "cloudflare_record" "app" {
  zone_id = var.zone_id
  name    = var.hostname
  type    = "CNAME"
  content = var.origin_hostname
  proxied = true
  ttl     = 1 # 'auto' when proxied
  comment = "Next3k LevelUp → Cloud Run origin"
}

# ----- Zone-wide TLS hardening -----
resource "cloudflare_zone_settings_override" "tls" {
  zone_id = var.zone_id
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
  zone_id     = var.zone_id
  name        = "edge-auth-injector"
  description = "Inject shared-secret header so Cloud Run accepts only Cloudflare-proxied traffic."
  kind        = "zone"
  phase       = "http_request_late_transform"

  rules = [
    {
      enabled     = true
      description = "Inject X-Edge-Auth for ${var.hostname}"
      expression  = "(http.host eq \"${var.hostname}\")"
      action      = "rewrite"
      action_parameters = {
        headers = {
          "X-Edge-Auth" = {
            operation = "set"
            value     = var.edge_shared_secret
          }
        }
      }
    },
  ]
}

# ----- WAF: enable Cloudflare Managed Ruleset (free) -----
resource "cloudflare_ruleset" "waf_managed" {
  zone_id     = var.zone_id
  name        = "waf-managed"
  description = "Enable Cloudflare Managed Ruleset on ${var.hostname}."
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  rules = [
    {
      enabled     = true
      description = "Cloudflare Managed Ruleset"
      expression  = "(http.host eq \"${var.hostname}\")"
      action      = "execute"
      action_parameters = {
        id = "efb7b8c949ac4650a09736fc376e9aee" # Cloudflare Managed Ruleset (stable global ID)
      }
    },
  ]
}

# ----- Per-IP rate limit (Free plan: 1 rule allowed per zone) -----
resource "cloudflare_ruleset" "rate_limit" {
  zone_id     = var.zone_id
  name        = "rate-limit-${replace(var.hostname, ".", "-")}"
  description = "Per-IP rate limit for ${var.hostname}."
  kind        = "zone"
  phase       = "http_ratelimit"

  rules = [
    {
      enabled     = true
      description = "${var.rate_limit_rpm} req/min/IP"
      expression  = "(http.host eq \"${var.hostname}\")"
      action      = "block"
      ratelimit = {
        characteristics     = ["ip.src"]
        period              = 60
        requests_per_period = var.rate_limit_rpm
        mitigation_timeout  = 60
      }
    },
  ]
}
