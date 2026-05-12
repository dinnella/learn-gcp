"""Human-readable section titles for exam objectives.

Single source of truth — used by the API so the SPA can show
"Compliance & business continuity" instead of `PCA-1.1`.

Codes follow the official Google Cloud certification exam guides.
If you add a new section to the seed, add it here too.
"""
from __future__ import annotations


SECTION_TITLES: dict[str, str] = {
    # ---- Professional Cloud Architect ----
    "PCA-1.1": "Compliance & business continuity",
    "PCA-1.2": "Choosing the right compute platform",
    "PCA-1.3": "Networking, storage & data architecture",
    "PCA-1.4": "Migration planning & strategy",
    "PCA-1.5": "Designing for future growth",
    "PCA-2.1": "Network topologies & connectivity",
    "PCA-2.2": "Storage system selection",
    "PCA-2.3": "Compute system configuration",
    "PCA-2.4": "Data lifecycle & locations",
    "PCA-3.1": "Identity & access management",
    "PCA-3.2": "Data security & encryption",
    "PCA-3.3": "Compliance controls",
    "PCA-4.1": "Technical processes & SDLC",
    "PCA-4.2": "Business processes & cost",
    "PCA-5.1": "Advising teams on cloud adoption",
    "PCA-5.2": "Interacting with Google Cloud",
    "PCA-6.1": "Monitoring, logging & alerting",
    "PCA-6.2": "Deployment & release management",
    # ---- Professional Cloud DevOps Engineer ----
    "DEVOPS-1.1": "SRE culture & principles",
    "DEVOPS-1.2": "Service-level objectives & error budgets",
    "DEVOPS-1.3": "Incident response & blameless postmortems",
    "DEVOPS-1.4": "Toil reduction & automation",
    "DEVOPS-2.1": "Building CI/CD pipelines",
    "DEVOPS-2.2": "Artifact management & supply chain security",
    "DEVOPS-2.3": "Deployment strategies",
    "DEVOPS-2.4": "Testing in production safely",
    "DEVOPS-3.1": "Infrastructure as code",
    "DEVOPS-3.2": "Configuration management",
    "DEVOPS-3.3": "Secrets & credential management",
    "DEVOPS-3.4": "Container & Kubernetes ops",
    "DEVOPS-4.1": "Logging & log-based metrics",
    "DEVOPS-4.2": "Monitoring & dashboards",
    "DEVOPS-4.3": "Tracing & profiling",
    "DEVOPS-4.4": "Alerting & on-call",
    "DEVOPS-5.1": "Capacity planning & scaling",
    "DEVOPS-5.2": "Cost optimization",
    "DEVOPS-5.3": "Reliability engineering practices",
}


def title_for(section_code: str) -> str:
    """Return a friendly title, falling back to the code itself."""
    return SECTION_TITLES.get(section_code, section_code)
