# Cloudflare edge for Next3k LevelUp.
# DNS (proxied) → Transform Rule injecting X-Edge-Auth → Cloud Run origin.
# Per-IP rate limit + zone TLS settings, all on Free plan.
# Note: Cloudflare Managed Ruleset (WAF) requires a paid plan — not included.

# ----- Zone lookup by name (avoids hardcoding the zone ID) -----
# The token only needs to be able to list zones (read) + write to the target zone.
data "cloudflare_zones" "this" {
  name = var.zone_name
}

locals {
  zone_id = data.cloudflare_zones.this.result[0].id
}

# ----- DNS: proxied CNAME so Cloudflare actually fronts the traffic -----
resource "cloudflare_dns_record" "app" {
  zone_id = local.zone_id
  name    = var.hostname
  type    = "CNAME"
  content = var.origin_hostname
  proxied = true
  ttl     = 1 # 'auto' when proxied
  comment = "Next3k LevelUp → Cloud Run origin"
}

# ----- Zone-wide TLS hardening -----
# Use individual cloudflare_zone_setting resources rather than
# cloudflare_zone_settings_override. The override captures ALL initial_settings
# on first apply and tries to restore every one on destroy — including read-only
# settings (prefetch_preload, origin_error_page_pass_thru, etc.) that error out
# on Free plan. Individual resources only touch their own setting on destroy.
resource "cloudflare_zone_setting" "ssl" {
  zone_id    = local.zone_id
  setting_id = "ssl"
  value      = "strict" # Full (strict): Cloud Run presents a valid cert
}
resource "cloudflare_zone_setting" "always_use_https" {
  zone_id    = local.zone_id
  setting_id = "always_use_https"
  value      = "on"
}
resource "cloudflare_zone_setting" "automatic_https_rewrites" {
  zone_id    = local.zone_id
  setting_id = "automatic_https_rewrites"
  value      = "on"
}
resource "cloudflare_zone_setting" "min_tls_version" {
  zone_id    = local.zone_id
  setting_id = "min_tls_version"
  value      = "1.2"
}
resource "cloudflare_zone_setting" "tls_1_3" {
  zone_id    = local.zone_id
  setting_id = "tls_1_3"
  value      = "zrt" # 0-RTT + TLS 1.3
}
resource "cloudflare_zone_setting" "opportunistic_encryption" {
  zone_id    = local.zone_id
  setting_id = "opportunistic_encryption"
  value      = "on"
}
resource "cloudflare_zone_setting" "browser_check" {
  zone_id    = local.zone_id
  setting_id = "browser_check"
  value      = "on"
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

  rules = [{
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
  }]
}

# ----- Origin Rule: override Host header so Cloud Run routes the request -----
# Cloudflare forwards the original Host (levelup.next3k.com) to the origin by
# default. Cloud Run only knows its *.run.app hostname and returns 404 for
# anything else. Origin Rules (http_request_origin / route action) are the
# only Cloudflare mechanism that can override the Host sent to the origin;
# transform rules explicitly block 'set' on the Host header (error 20087).
resource "cloudflare_ruleset" "origin_override" {
  zone_id     = local.zone_id
  name        = "origin-host-override"
  description = "Route ${var.hostname} requests to Cloud Run with correct Host header."
  kind        = "zone"
  phase       = "http_request_origin"

  rules = [{
    enabled     = true
    description = "Override Host → ${var.origin_hostname}"
    expression  = "(http.host eq \"${var.hostname}\")"
    action      = "route"
    action_parameters = {
      host_header = var.origin_hostname
    }
  }]
}

# ----- Per-IP rate limit (Free plan: 1 rule allowed per zone) -----
resource "cloudflare_ruleset" "rate_limit" {
  zone_id     = local.zone_id
  name        = "rate-limit-${replace(var.hostname, ".", "-")}"
  description = "Per-IP rate limit for ${var.hostname}."
  kind        = "zone"
  phase       = "http_ratelimit"

  rules = [{
    enabled     = true
    description = "${var.rate_limit_rp10s} req/10s/IP"
    expression  = "(http.host eq \"${var.hostname}\")"
    action      = "block"
    ratelimit = {
      # cf.colo.id is required: Cloudflare counts requests per colo, not globally.
      characteristics     = ["cf.colo.id", "ip.src"]
      # Free plan: period=10 and mitigation_timeout=10 are the only valid values.
      period              = 10
      requests_per_period = var.rate_limit_rp10s
      mitigation_timeout  = 10
    }
  }]
}
