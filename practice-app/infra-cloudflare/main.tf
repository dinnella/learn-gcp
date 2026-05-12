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

# ----- Worker: rewrite Host + inject X-Edge-Auth -----
# Cloudflare forwards the original Host (levelup.next3k.com) to the origin,
# but Cloud Run only knows its *.run.app hostname. Transform rules can't set
# the Host header (error 20087) and Origin Rules require a paid plan (error
# 'not entitled to use HostHeader override'). A Worker has full control over
# the upstream fetch and is free up to 100k req/day.
#
# The Worker also injects X-Edge-Auth so Cloud Run middleware can reject
# any traffic that doesn't come through Cloudflare.
resource "cloudflare_workers_script" "host_proxy" {
  account_id  = var.account_id
  script_name = "levelup-proxy"
  main_module = "worker.js"
  content     = <<-JS
    export default {
      async fetch(request, env) {
        const url = new URL(request.url);
        url.hostname = env.ORIGIN_HOSTNAME;
        const headers = new Headers(request.headers);
        headers.set('X-Edge-Auth', env.EDGE_SHARED_SECRET);
        return fetch(url.toString(), {
          method: request.method,
          headers,
          body: ['GET', 'HEAD'].includes(request.method) ? null : request.body,
          redirect: 'follow',
        });
      }
    };
  JS
  bindings = [
    {
      name = "ORIGIN_HOSTNAME"
      type = "plain_text"
      text = var.origin_hostname
    },
    {
      name = "EDGE_SHARED_SECRET"
      type = "secret_text"
      text = var.edge_shared_secret
    },
  ]
}

resource "cloudflare_workers_route" "app" {
  zone_id = local.zone_id
  pattern = "${var.hostname}/*"
  script  = cloudflare_workers_script.host_proxy.script_name
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
