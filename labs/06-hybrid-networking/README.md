# Lab 06 — Hybrid networking (HA VPN + Private Service Connect)

**Exam coverage:** PCA §1.3, §2.1
**Prereqs:** bootstrap/, lab 01 (VPC)
**Cost:** HA VPN: ~$0.05/hr per tunnel × 2 = ~$2.40/day. PSC endpoints: ~$0.01/hr. **Destroy after each session.**

## What you build

A *single-cloud* simulation of hybrid: two GCP VPCs in different regions connected via **HA VPN** with BGP, plus a **Private Service Connect** endpoint to a Google service. This gives you the same configuration steps without an actual on-prem device.

```
VPC-A (us-central1)  ===HA VPN tunnel pair===  VPC-B (us-east1)
       (BGP via Cloud Router)
       PSC endpoint → Cloud SQL admin API (private path)
```

## AWS / Azure analogs

| This lab does… | …in AWS | …in Azure |
|---|---|---|
| HA VPN | Site-to-Site VPN (2 tunnels) | VPN Gateway active-active |
| Cloud Router (BGP) | Virtual Private Gateway / Direct Connect Gateway | VPN Gateway BGP |
| Cloud Interconnect (not in this lab) | Direct Connect | ExpressRoute |
| Private Service Connect (consumer endpoint) | PrivateLink | Private Link |
| PSC service attachment (producer) | PrivateLink service | Private Link service |
| Network Connectivity Center | Transit Gateway | Virtual WAN |

## GCP twists worth memorizing

1. **HA VPN gives 99.99% SLA** but requires 2 tunnels with BGP. Classic VPN is deprecated for new use.
2. **Cloud Router is BGP-only** in GCP — no static routes between VPN/Interconnect endpoints in the modern path.
3. **Private Service Connect has 3 flavors:**
   - PSC for **Google APIs** (e.g. private endpoint for `storage.googleapis.com`)
   - PSC for **published services** (consumer-side endpoint)
   - PSC **interfaces** (producer side connects out)
4. **Private Google Access** ≠ PSC. Private Google Access lets a VM with no external IP reach Google APIs over the default service IPs. PSC creates a *new* internal IP in your VPC for that service.
5. **VPC peering is non-transitive** — same as AWS. For "transitive hub" use Network Connectivity Center or Shared VPC.
6. **Cloud DNS** integrates with on-prem via DNS forwarding zones; common pattern for hybrid name resolution.

## TODO

- [ ] Two VPCs + Cloud Routers
- [ ] HA VPN gateways + 2 tunnels each side
- [ ] BGP sessions
- [ ] PSC endpoint to a Google API (storage)
- [ ] Cloud DNS private zone + forwarding to a "fake on-prem" VPC
