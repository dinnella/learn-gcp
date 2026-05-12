# AWS / Azure → GCP service & concept cheat sheet

Optimized for an engineer fluent in AWS + Azure. **"GCP twist"** column is the testable difference, not the marketing pitch.

## Resource hierarchy & identity

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Top container | Organization (Organizations) | Tenant / Management Group | **Organization** | Org is bound to a Workspace/Cloud Identity domain — you can't have two orgs on one domain |
| Grouping | OUs | Management Groups → Subscriptions | **Folders → Projects** | Folders nest 10 deep; **Projects** are the billing & API boundary (closer to AWS account than to subscription) |
| Workload boundary | Account | Subscription | **Project** | Almost every resource lives in a project; quotas + IAM are project-scoped |
| Identity | IAM users + roles | Entra ID users + groups | **Cloud Identity / Workspace users + Google Groups** | No "IAM users" concept; humans are Google identities, workloads are **service accounts** |
| Workload identity | IAM Role for service / IRSA | Managed Identity | **Service Account** + **Workload Identity Federation** | SAs are *resources you can grant access TO* and *identities that grant access FROM* |
| Federation for CI | OIDC → assume IAM Role | OIDC → federated credential | **Workload Identity Federation** (WIF) | Direct WIF (no SA proxy) is preferred; gives `principalSet://...` identities |
| Permission model | Allow + explicit deny | Allow + deny assignments | **Allow-only** + **IAM Conditions** + **Org Policies** for guardrails | No deny statements in IAM (deny exists separately as IAM Deny policies, newer & rarely tested) |
| Policy types | SCP (deny), permission boundary | Azure Policy | **Org Policies** (constraints), **IAM Conditions**, **VPC Service Controls** | VPC-SC = data exfiltration perimeter, no AWS analog (closest: SCPs + RAM + endpoint policies combined) |
| Tags | Tags | Tags | **Labels** + **Tags** | "Tags" in GCP are conditional IAM tags (different from labels which are key/value metadata) |

## Networking

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Virtual network | VPC (regional) | VNet (regional) | **VPC** (**global**) | One VPC spans all regions; subnets are regional. Huge architectural difference. |
| Subnet | Subnet (AZ-scoped) | Subnet | **Subnet** (regional, spans all zones) | Subnets are regional, not zonal — no "one subnet per AZ" pattern |
| Cross-account network share | RAM + Transit Gateway | VNet peering / Hub-spoke | **Shared VPC** (host/service projects) | Native and free; the canonical landing-zone pattern |
| Peering | VPC Peering | VNet Peering | **VPC Network Peering** | Non-transitive, like AWS |
| Hub-spoke / transit | Transit Gateway | vWAN / Hub-spoke | **Network Connectivity Center** | Newer; for big topologies still common to use Shared VPC |
| Private service access | PrivateLink | Private Link | **Private Service Connect** + **Private Service Access** | PSC consumer endpoints look like internal IPs — same UX as PrivateLink |
| Hybrid VPN | Site-to-Site VPN | VPN Gateway | **Cloud VPN** (HA VPN: 99.99% SLA, requires 2 tunnels) | HA VPN needs BGP and 2 tunnels; classic VPN deprecated |
| Dedicated connection | Direct Connect | ExpressRoute | **Cloud Interconnect** (Dedicated, Partner) | |
| DNS | Route 53 | Azure DNS | **Cloud DNS** | Private zones bound to networks (similar to private hosted zones) |
| Firewall | Security Groups + NACLs | NSGs | **VPC firewall rules** + **Hierarchical firewall policies** | Stateful, applied to VMs by network tags or SAs (not attached to ENIs); hierarchical FW = org/folder enforced |
| L7 load balancer | ALB | Application Gateway | **Global External Application Load Balancer** | One global anycast IP; Cloud CDN integrated; backends can be multi-region |
| L4 load balancer | NLB | Standard LB | **Global/Regional Network LB** (Proxy or Passthrough) | Naming changed in 2023; old "TCP/SSL/HTTP(S) LB" terminology still in some docs |
| WAF | AWS WAF | Front Door WAF | **Cloud Armor** | Rules language is similar to AWS WAF; preconfigured OWASP rules built-in |
| API gateway | API Gateway | API Management | **API Gateway** (lightweight) or **Apigee** (full API management) | Apigee is testable on PCA (5.1) — full lifecycle product |
| NAT | NAT Gateway | NAT Gateway | **Cloud NAT** | Regional, no per-AZ duplication needed; charged per VM-hour + GB |

## Compute

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| VMs | EC2 | VM | **Compute Engine** | Live migration on host failure (no AZ-equivalent stop) |
| Spot/preemptible | Spot Instances | Spot VMs | **Spot VMs** | 24h max for legacy preemptible; Spot VMs have no duration limit but can be reclaimed any time |
| Auto-scaling group | ASG | VMSS | **Managed Instance Group (MIG)** | Regional MIG spans 3 zones automatically |
| Reserved capacity | RIs / Savings Plans | Reservations | **CUDs** (1y/3y) + **Sustained-Use Discounts** (auto) | SUDs are automatic — no commitment; CUDs apply per region |
| Containers | ECS / EKS | ACI / AKS | **GKE** (Standard / **Autopilot**) | Autopilot = fully managed nodes, billed per pod CPU/RAM (closer to Fargate UX, but uses real Kubernetes) |
| Serverless containers | Fargate / App Runner | Container Apps / ACI | **Cloud Run** | Scales to zero, request-based billing, supports any container; **Cloud Run Jobs** for batch |
| Functions | Lambda | Functions | **Cloud Run functions** (formerly Cloud Functions 2nd gen) | Runs on Cloud Run under the hood — same scaling model |
| Batch | AWS Batch | Batch | **Batch** + **Dynamic Workload Scheduler** | DWS is for AI/HPC; gives time-bound capacity reservations |
| Bare-metal / VMware | Outposts / VMware Cloud on AWS | Azure VMware Solution | **Google Cloud VMware Engine** + **Bare Metal Solution** | |
| HPC | ParallelCluster | CycleCloud | **AI Hypercomputer** (TPUs/GPUs with topology-aware scheduling) | Exam-relevant for new PCA content (Vertex AI / Gemini training) |

## Storage

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Object storage | S3 | Blob Storage | **Cloud Storage** | Buckets are global names, but data is regional/dual-region/multi-region |
| Storage classes | Standard/IA/Glacier | Hot/Cool/Cold/Archive | **Standard / Nearline / Coldline / Archive** | Min storage durations: 30/90/365 days. Lifecycle rules transition like S3. |
| Block storage | EBS | Managed Disks | **Persistent Disk** + **Hyperdisk** | Disks are zonal (or **regional PD** for sync replication across 2 zones in same region) |
| File storage | EFS / FSx | Files / NetApp Files | **Filestore** + **NetApp Volumes** | Filestore tiers: Basic/Zonal/Enterprise/Regional |
| Backup | AWS Backup | Backup vaults | **Backup and DR Service** + GCS lifecycle | |
| Relational DB | RDS / Aurora | SQL Database / SQL MI | **Cloud SQL** (MySQL/Postgres/SQLServer) + **AlloyDB** (Postgres) | AlloyDB ≈ Aurora-equivalent for Postgres |
| Globally distributed SQL | (no equivalent — Aurora Global is async) | Cosmos DB SQL API | **Spanner** | Externally consistent, horizontally scalable SQL — no AWS/Azure equivalent. Heavily tested. |
| Wide-column NoSQL | DynamoDB | Cosmos DB Cassandra/Table | **Bigtable** | HBase-compatible; for >1TB/heavy throughput. Use **Firestore** for document/serverless NoSQL. |
| Document NoSQL | DynamoDB | Cosmos DB SQL/Mongo | **Firestore** (in Native or Datastore mode) | |
| In-memory | ElastiCache | Cache for Redis | **Memorystore** (Redis/Valkey/Memcached) | |
| Data warehouse | Redshift | Synapse / Fabric | **BigQuery** | Serverless, separation of storage + compute, SQL with ML built in. Flagship product — heavily tested. |
| Search | OpenSearch | Cognitive Search | **Vertex AI Search** (formerly Gen App Builder) | |

## Data processing

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Streaming ingest | Kinesis | Event Hubs | **Pub/Sub** | At-least-once, global topics, no shard management |
| Stream + batch processing | Kinesis Data Analytics / EMR Flink / Glue | Stream Analytics / HDInsight | **Dataflow** (managed Apache Beam) | Unified batch+stream model; autoscaling |
| Hadoop/Spark | EMR | HDInsight / Synapse Spark | **Dataproc** + **Dataproc Serverless** | Use serverless for new workloads |
| ETL service | Glue | Data Factory | **Cloud Data Fusion** + **Dataform** + **Dataflow** | Dataform = SQL-based transformations in BigQuery (dbt-like) |
| Workflow orchestration | Step Functions / MWAA | Logic Apps / Data Factory | **Workflows** + **Cloud Composer** (managed Airflow) | |
| Eventing | EventBridge | Event Grid | **Eventarc** | CloudEvents standard; routes to Cloud Run, Workflows, etc. |

## Security

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Secrets | Secrets Manager / SSM Parameter Store | Key Vault secrets | **Secret Manager** + **Parameter Manager** (newer) | Versioning + automatic rotation; native CSI driver for GKE |
| KMS | KMS | Key Vault keys | **Cloud KMS** + **Cloud HSM** + **Cloud External Key Manager** | EKM = bring keys hosted outside Google (Equinix, Thales). HYOK pattern. |
| Default encryption | SSE-S3 (AES) | SSE | **Google-managed encryption (default)** | All data at rest encrypted by default with Google keys; CMEK is opt-in |
| Cert management | ACM | Key Vault certs | **Certificate Manager** + **CA Service** | CAS = private CA hierarchy |
| Bastion / remote access | SSM Session Manager | Bastion / JIT | **IAP TCP tunneling** + **OS Login** | IAP front-ends app + SSH/RDP without exposing public IPs |
| Zero-trust SaaS | (no native) | Entra ID / Conditional Access | **Chrome Enterprise Premium** (formerly BeyondCorp Enterprise) | Context-aware access enforced at IAP, not app |
| WAF + DDoS | WAF + Shield | Front Door | **Cloud Armor** + **Cloud Armor Adaptive Protection** | |
| Posture / Findings | Security Hub + GuardDuty + Inspector | Defender for Cloud | **Security Command Center** (Standard / Premium / Enterprise) | SCC Premium adds Event Threat Detection, Container Threat Detection, etc. |
| Data perimeter | SCPs + endpoint policies + RAM | (limited equivalent) | **VPC Service Controls** | Service-level perimeter against data exfil; **the** uniquely-GCP control |
| Audit | CloudTrail | Activity Log | **Cloud Audit Logs** (Admin Activity = always on; Data Access = opt-in) | Admin Activity logs free; Data Access logs cost money — common cost trap |
| Software supply chain | Inspector + Signer | Defender for Cloud + Notation | **Binary Authorization** + **Artifact Analysis** + **SLSA** | Binary Authorization = admission control on signed images (GKE/Cloud Run) |
| AI security | Bedrock Guardrails | AI Content Safety | **Model Armor** + **Sensitive Data Protection (DLP)** | New on PCA 3.1 |

## Observability

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Logs | CloudWatch Logs | Log Analytics | **Cloud Logging** | Logs Router → buckets/BigQuery/Pub/Sub/GCS sinks. Log-based metrics built-in. |
| Metrics | CloudWatch Metrics | Monitor Metrics | **Cloud Monitoring** | Native PromQL via **Managed Service for Prometheus** |
| Traces | X-Ray | Application Insights | **Cloud Trace** | OpenTelemetry-first |
| APM | X-Ray + CloudWatch RUM | Application Insights | **Cloud Profiler** + **Cloud Trace** + **Error Reporting** | |
| Synthetics | Synthetics canaries | Application Insights | **Synthetic Monitors** | |
| SLO management | (CloudWatch composite alarms — limited) | (no native) | **Service Monitoring + SLOs** | First-class SLO objects with burn-rate alerting — the canonical SRE workflow |
| Alerting | CloudWatch Alarms | Monitor Alerts | **Alerting Policies** | Conditions + notification channels; webhooks, PagerDuty native |
| Agent | CloudWatch agent | Azure Monitor Agent | **Ops Agent** (replaces Logging + Monitoring agents) | One agent, OpenTelemetry-based |

## CI/CD & developer tools

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Container registry | ECR | ACR | **Artifact Registry** | Replaces deprecated Container Registry; supports Docker, Maven, npm, Python, Apt/Yum, Helm |
| Build | CodeBuild | Pipelines/Build | **Cloud Build** | Triggers from GitHub/GitLab/CSR; Buildpacks support |
| Deploy | CodeDeploy | Pipelines/Release | **Cloud Deploy** | Native canary/rolling for GKE/Cloud Run; uses Skaffold + Kustomize/Helm |
| Source repo | CodeCommit | Repos | **Cloud Source Repositories** + **Secure Source Manager** | CSR is being de-emphasized; SSM is newer enterprise option |
| IDE-in-cloud | Cloud9 (deprecated) | (no first-party) | **Cloud Workstations** + **Cloud Shell** | Workstations = managed dev VMs, IDE-agnostic |
| AI assistant | CodeWhisperer / Q | Copilot | **Gemini Code Assist** + **Gemini Cloud Assist** + **Gemini CLI** | All three appear in PCA + DevOps exam guides |
| IaC native | CloudFormation / CDK | ARM / Bicep | **Infrastructure Manager** (managed Terraform) + **Config Connector** (TF resources via k8s CRDs) | Plain Terraform/OpenTofu is the dominant pattern; Infra Manager runs Terraform server-side. The exam guides say "Terraform" — OpenTofu is fully compatible. |

## Migration

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Discovery & assessment | Migration Hub | Migrate | **Migration Center** (formerly StratoZone) | First stop for any migration question on PCA 1.4 |
| Server migration | MGN / SMS | Migrate | **Migrate to Virtual Machines** (formerly Migrate for Compute Engine) | |
| Container modernization | App2Container | Migrate to AKS | **Migrate to Containers** | |
| Database migration | DMS | DMS | **Database Migration Service** | |
| Bulk transfer | Snow family / DataSync | Data Box / Migrate | **Transfer Appliance** + **Storage Transfer Service** | STS for online (S3/Azure/GCS), Transfer Appliance for offline |

## AI / ML (newer exam content)

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Unified ML platform | SageMaker | Azure ML | **Vertex AI** | Pipelines, Workbench, Model Registry, endpoints, Feature Store all under one product |
| Foundation models | Bedrock | OpenAI Service / AI Foundry | **Vertex AI Model Garden** (Gemini, Llama, Anthropic, etc.) | |
| LLM | Bedrock (Claude/Llama/etc.) | OpenAI / AI Foundry | **Gemini** (1.5/2.x Pro & Flash) | First-party + multi-modal natively |
| Vector search | OpenSearch / Aurora pgvector | AI Search | **Vertex AI Vector Search** | |
| Agent platform | Bedrock Agents | AI Foundry Agents | **Agent Builder** + **NotebookLM Enterprise** | |
| ML pipelines | SageMaker Pipelines | Azure ML Pipelines | **Vertex AI Pipelines** (KFP) | |

## FinOps & cost

| Concept | AWS | Azure | GCP | GCP twist |
|---|---|---|---|---|
| Cost reports | Cost Explorer / CUR | Cost Management | **Cloud Billing reports** + export to BigQuery | BigQuery export is the universal pattern for custom analysis |
| Budgets | Budgets | Budgets | **Budgets + alerts** + Pub/Sub trigger | Pub/Sub trigger lets you script auto-shutdown |
| Recommendations | Compute Optimizer / Trusted Advisor | Advisor | **Active Assist Recommender** | Programmatic API; recommenders for cost, security, perf, reliability, manageability |
| Discount programs | RIs / Savings Plans / Spot | Reservations / Savings / Spot | **CUDs** (resource/spend-based), **SUDs** (auto), **Spot VMs** | SUDs apply automatically to GCE/GKE — unique to GCP |

## Concept differences worth memorizing

1. **Project = primary boundary.** All quotas, billing, IAM, APIs, networking are project-scoped. There is no AWS-account-level "shared resource" concept; you bridge projects with Shared VPC, IAM grants, and VPC-SC.
2. **Global VPC.** A single VPC spans all regions. Subnets are regional. This eliminates AWS's "VPC per region" sprawl but requires care with subnet IP planning.
3. **Service accounts are first-class IAM principals.** You grant a *service account* roles, then either attach it to a workload or impersonate it.
4. **No deny statements in plain IAM.** Guardrails come from **Org Policies** (resource-level constraints), **VPC Service Controls** (perimeters), and **IAM Deny policies** (newer, less commonly tested).
5. **VPC Service Controls** is the canonical answer for any "prevent data exfiltration" question.
6. **Workload Identity Federation** is the canonical answer for any "external workload should authenticate without keys" question (GitHub Actions, GitLab, AWS, on-prem).
7. **Shared VPC** is the canonical landing-zone networking pattern, not Network Connectivity Center.
8. **Spanner** is the canonical answer for "globally consistent transactional SQL".
9. **BigQuery** is the canonical analytics answer (and increasingly an OLTP-adjacent choice for analytical workloads).
10. **Cloud Run** is the answer for stateless containers in most architecture questions unless the question explicitly requires Kubernetes APIs (then GKE Autopilot).
11. **GKE Autopilot vs. Standard:** Autopilot = Google manages nodes, you pay per pod resources, opinionated security. Standard = you manage node pools.
12. **Cloud Logging Data Access logs are off by default** and cost extra — common cost-optimization question.
13. **`gcloud` ≠ `gsutil`.** `gsutil` is deprecated for new work; use `gcloud storage`.
14. **Regions vs. zones:** every region has 3+ zones. Regional resources (Spanner, regional MIGs, regional PD, multi-region GCS) replicate automatically across zones.
