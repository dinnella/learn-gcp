# Lab 05 — Streaming data pipeline (Pub/Sub → Dataflow → BigQuery)

**Exam coverage:** PCA §1.3, §2.2; some DevOps §4 overlap
**Prereqs:** bootstrap/
**Cost:** Dataflow is the expensive part (~$0.15–0.30/hr per worker). **Destroy after each session.** Use the streaming Pub/Sub-to-BigQuery template.

## What you build

```
synthetic publisher → Pub/Sub topic → Dataflow streaming job (Google template)
                                              ↓
                                       BigQuery table (partitioned by ingestion time)
```

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| Pub/Sub topic | Kinesis Data Stream | Event Hub |
| Pub/Sub subscription (pull) | Kinesis consumer / SQS | Event Hub consumer group |
| Dataflow streaming | Kinesis Data Analytics / Flink-on-EMR | Stream Analytics |
| BigQuery sink | Redshift / S3 + Athena | Synapse / ADX |
| Pub/Sub schemas | Glue Schema Registry | Schema Registry |

## GCP twists worth memorizing

1. **Pub/Sub topics are global**, no shard count to manage. Subscribers control parallelism.
2. **Pub/Sub delivery is at-least-once**; use **exactly-once** subscription mode for dedup'd consumption (newer feature).
3. **Push vs. Pull subscriptions:**
   - Push delivers via HTTPS to a public endpoint (must auth) — natural fit for Cloud Run.
   - Pull is the default; subscribers ack messages.
4. **Dataflow runs Apache Beam.** Same code runs streaming or batch. Autoscaling and update-in-place are built in.
5. **BigQuery streaming inserts** vs. **Storage Write API** — Storage Write API is the modern, cheaper, exactly-once path. Dataflow uses it by default in newer versions.
6. **Pub/Sub-to-BigQuery direct subscription** (no Dataflow) exists for simple passthrough — cheaper. Use Dataflow when you need transformation/enrichment.
7. **Dataflow SQL** + **BigQuery scheduled queries** are competing patterns for simple ETL — exam may ask which is most cost-effective.

## TODO

- [ ] Pub/Sub topic + schema (Avro)
- [ ] BigQuery dataset + partitioned table
- [ ] Dataflow Flex Template launch via OpenTofu (`google_dataflow_flex_template_job`)
- [ ] Compare: Pub/Sub direct → BQ subscription vs. Dataflow path
- [ ] Generator script in `tools/` to publish synthetic events
