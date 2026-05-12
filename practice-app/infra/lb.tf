# Edge stack: global HTTPS load balancer + Cloud Armor + Google-managed TLS cert,
# fronting the Cloud Run service via a Serverless NEG.
#
# Provisioning order (chicken-and-egg with the cert):
#   1. tofu apply with -var enable_lb=true -var domain=levelup.next3k.com
#      → creates LB + reserved IP + cert (cert will be PROVISIONING)
#   2. point DNS A record `levelup.next3k.com` at the IP
#      (output: lb_ip_address)
#   3. wait ~10–60 min for cert to reach ACTIVE
#   4. tofu apply with -var restrict_ingress_to_lb=true
#      → cuts off the *.run.app URL; only the LB can reach Cloud Run

# ----- Cloud Armor: per-IP rate limit + OWASP preconfigured WAF rules -----
resource "google_compute_security_policy" "edge" {
  count = local.lb_enabled ? 1 : 0

  name        = "${var.service_name}-armor"
  description = "Edge protection for ${var.service_name}"

  # Default allow (lowest priority).
  rule {
    action      = "allow"
    priority    = 2147483647
    description = "default allow"
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
  }

  # Per-IP rate limit.
  rule {
    action      = "throttle"
    priority    = 1000
    description = "per-IP rate limit"
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.rate_limit_rpm
        interval_sec = 60
      }
    }
  }

  # Preconfigured WAF — XSS.
  rule {
    action      = "deny(403)"
    priority    = 900
    description = "block XSS"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})"
      }
    }
  }

  # Preconfigured WAF — SQLi.
  rule {
    action      = "deny(403)"
    priority    = 901
    description = "block SQLi"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})"
      }
    }
  }

  # Preconfigured WAF — local file inclusion.
  rule {
    action      = "deny(403)"
    priority    = 902
    description = "block LFI"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('lfi-v33-stable', {'sensitivity': 1})"
      }
    }
  }
}

# ----- Serverless NEG → Cloud Run -----
resource "google_compute_region_network_endpoint_group" "cr" {
  count = local.lb_enabled ? 1 : 0

  name                  = "${var.service_name}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.app.name
  }
}

resource "google_compute_backend_service" "app" {
  count = local.lb_enabled ? 1 : 0

  name                  = "${var.service_name}-bes"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"
  security_policy       = google_compute_security_policy.edge[0].id

  log_config {
    enable      = true
    sample_rate = 1.0
  }

  backend {
    group = google_compute_region_network_endpoint_group.cr[0].id
  }
}

# ----- HTTPS frontend -----
resource "google_compute_url_map" "app" {
  count           = local.lb_enabled ? 1 : 0
  name            = "${var.service_name}-urlmap"
  default_service = google_compute_backend_service.app[0].id
}

resource "google_compute_managed_ssl_certificate" "app" {
  count = local.lb_enabled ? 1 : 0
  name  = "${var.service_name}-cert"
  managed {
    domains = [var.domain]
  }
}

resource "google_compute_target_https_proxy" "app" {
  count            = local.lb_enabled ? 1 : 0
  name             = "${var.service_name}-https-proxy"
  url_map          = google_compute_url_map.app[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.app[0].id]
}

resource "google_compute_global_address" "app" {
  count = local.lb_enabled ? 1 : 0
  name  = "${var.service_name}-ip"
}

resource "google_compute_global_forwarding_rule" "https" {
  count = local.lb_enabled ? 1 : 0

  name                  = "${var.service_name}-fr-https"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "443"
  target                = google_compute_target_https_proxy.app[0].id
  ip_address            = google_compute_global_address.app[0].id
}

# ----- HTTP → HTTPS redirect -----
resource "google_compute_url_map" "redirect" {
  count = local.lb_enabled ? 1 : 0
  name  = "${var.service_name}-redirect"
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "redirect" {
  count   = local.lb_enabled ? 1 : 0
  name    = "${var.service_name}-http-proxy"
  url_map = google_compute_url_map.redirect[0].id
}

resource "google_compute_global_forwarding_rule" "http" {
  count = local.lb_enabled ? 1 : 0

  name                  = "${var.service_name}-fr-http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_target_http_proxy.redirect[0].id
  ip_address            = google_compute_global_address.app[0].id
}
