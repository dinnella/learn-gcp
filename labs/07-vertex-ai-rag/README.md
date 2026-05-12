# Lab 07 — Vertex AI RAG sample

**Exam coverage:** PCA §1.3, §2.4, §2.5, §3.1 (Securing AI / Model Armor)
**Prereqs:** bootstrap/
**Cost:** Vertex AI Search free tier is small; **Gemini API calls are billed per 1k tokens**. Estimate ~$1–5 for a study session if you ask thousands of queries.

## What you build

A minimal Retrieval-Augmented Generation app:

```
PDFs in GCS → Vertex AI Search data store → search API
                                                ↓
                  Cloud Run app ←──→ Gemini 2.5 Flash (Vertex AI)
                                                ↑
                                          Model Armor policy (prompt + response filtering)
```

This is the canonical "Gemini Enterprise" pattern called out in PCA 2.5.

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| Vertex AI Search data store | Bedrock Knowledge Bases | AI Search + AI Foundry |
| Gemini API call | Bedrock InvokeModel (Claude/Llama) | OpenAI / AI Foundry chat completion |
| Model Armor | Bedrock Guardrails | AI Content Safety |
| Vertex AI Vector Search (alt) | OpenSearch k-NN / Aurora pgvector | AI Search vector |
| Vertex AI Pipelines | SageMaker Pipelines | Azure ML Pipelines |

## GCP twists worth memorizing

1. **Vertex AI is the umbrella** for all ML/GenAI: Pipelines, Workbench, Model Garden, endpoints, Feature Store, Search.
2. **Model Garden** is the catalog (Gemini + Anthropic + Llama + Mistral + open-source) — model selection question favorite.
3. **Model Armor** is the security layer for prompts + responses (PII redaction, jailbreak detection, malicious URL filtering). Newer; explicitly listed in PCA 3.1.
4. **Sensitive Data Protection (SDP)** (formerly DLP) is the broader inspect/redact API for any text/data — pairs with Model Armor.
5. **AI Hypercomputer** = the bundled compute stack (TPUs/GPUs + topology-aware schedulers + Cluster Director + Dynamic Workload Scheduler). Listed in PCA 1.3 and 2.4.
6. **Vertex AI Search vs. Vector Search:**
   - Search = managed retrieval (chunking + embeddings + ranking handled for you).
   - Vector Search = bring-your-own embeddings, ANN index.
   - Default exam answer: **Search** unless the question demands custom embeddings.

## TODO

- [ ] GCS bucket w/ sample PDFs
- [ ] Vertex AI Search data store + index OpenTofu (note: provider coverage of this is partial — may need `gcloud` glue)
- [ ] Cloud Run app calling Gemini via Vertex AI SDK
- [ ] Model Armor template applied
- [ ] IAM hardening: app SA only has Vertex AI invoke + Search query, nothing else
