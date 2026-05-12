# Lab 04 — Observability + SLOs

**Exam coverage:** PCA §1.1, §6.x; DevOps §3.1, §4.x (25% of DevOps exam!)
**Prereqs:** bootstrap/, lab 02 (something to monitor)
**Cost:** ~$0–1/day; first 50 GiB Cloud Logging ingest free, Monitoring metrics mostly free.

## What you build

End-to-end observability for the lab 02 Cloud Run service:

- **OpenTelemetry**: instrument the app to emit traces + metrics
- **Cloud Logging**: structured logs + a **log-based metric** for HTTP 5xx
- **Cloud Monitoring**: latency + error-rate dashboard via TF
- **SLOs**: 99.5% availability + p95 latency <300ms over a 28-day window
- **Alerting policies**: fast-burn (1h) + slow-burn (6h) error-budget-burn alerts
- **Synthetic monitor**: probes the public URL every minute

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| Cloud Logging | CloudWatch Logs | Log Analytics |
| Cloud Monitoring metrics | CloudWatch Metrics | Monitor Metrics |
| SLO objects | (none — built ad hoc with composite alarms) | (none) |
| Burn-rate alerts | (manual w/ math expressions) | (manual) |
| Cloud Trace | X-Ray | App Insights |
| Synthetic monitors | Synthetics canaries | App Insights availability tests |
| Managed Prometheus | AMP | Azure Monitor for Prometheus |

## GCP twists worth memorizing

1. **Service-level objects (Services + SLOs)** are first-class resources. Use them — the exam tests this pattern explicitly. No need to build SLOs from raw metrics.
2. **Burn-rate alerting** has built-in multi-window support: alert on a fast burn (e.g. 14.4× over 1h) AND a slow burn (6× over 6h). Reduces alert fatigue.
3. **Log-based metrics** are counters (`COUNTER`) or distributions (`DISTRIBUTION`) computed at ingest. Cheap; great for "alert if pattern X appears in logs".
4. **Cloud Logging Data Access logs are off by default** and cost extra. Common cost-optimization question.
5. **Logs Router** routes via sinks to GCS / BigQuery / Pub/Sub / other Logging buckets. Use exclusion filters to drop noisy logs *before* ingest billing.
6. **Ops Agent** (single agent for logs + metrics) replaces the older Logging + Monitoring agents.
7. **Managed Service for Prometheus** is the GCP-native way to scrape Prometheus metrics — no node-local Prometheus server needed.

## IAM prerequisites

Local runs use your own gcloud identity (Owner is sufficient). For CI runs via `labs-apply.yml`, the deployer SA needs:

```bash
PROJECT=your-project-id
SA="serviceAccount:gh-deployer@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/logging.admin"                 # create log-based metrics and sinks

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/monitoring.admin"              # create SLOs, alert policies, dashboards

gcloud projects add-iam-policy-binding "$PROJECT" --member="$SA" --condition=None \
  --role="roles/serviceusage.serviceUsageAdmin" # enable GCP APIs via google_project_service
```

## TODO

- [ ] Sample app w/ OpenTelemetry SDK (Python or Go)
- [ ] Log-based metric for `severity=ERROR`
- [ ] `google_monitoring_service` + `google_monitoring_slo` (availability + latency)
- [ ] `google_monitoring_alert_policy` with burn-rate condition
- [ ] `google_monitoring_dashboard` JSON
- [ ] Synthetic monitor (`google_monitoring_uptime_check_config` or `google_monitoring_monitored_project`)
- [ ] Alert → Pub/Sub → Cloud Run function → fake PagerDuty webhook
