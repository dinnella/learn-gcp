variable "zone_id" {
  description = "Cloudflare zone ID for next3k.com."
  type        = string
}

variable "hostname" {
  description = "Public hostname (FQDN) to expose, e.g. levelup.next3k.com."
  type        = string
}

variable "origin_hostname" {
  description = "Cloud Run hostname to CNAME to (no scheme), e.g. practice-app-XXXX-uc.a.run.app."
  type        = string
}

variable "edge_shared_secret" {
  description = "Value Cloudflare injects as X-Edge-Auth on every origin request. Must match the secret stored in GCP Secret Manager and exposed to Cloud Run as EDGE_SHARED_SECRET."
  type        = string
  sensitive   = true
}

variable "rate_limit_rpm" {
  description = "Requests per IP per minute before the rate limiter blocks for 60s."
  type        = number
  default     = 60
}
