#!/usr/bin/env bash
# Section 2 of todo.md — set GH variables, secrets, branch protection, code-security
# settings, and Actions permissions via gh CLI.
#
# Prereqs: gh auth login   (with scopes: repo, workflow, admin:org NOT needed for personal repo)
# Usage:   bash scripts/setup-github.sh
#
# Idempotent — re-run safely.

set -euo pipefail

REPO="dinnella/learn-gcp"
PROJECT="next3k-levelup"

# Look up project number from gcloud (falls back to a prompt if unset).
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)' 2>/dev/null || true)
if [[ -z "${PROJECT_NUMBER}" ]]; then
  read -rp "Couldn't auto-detect project number. Enter GCP project number: " PROJECT_NUMBER
fi

DEPLOYER_SA="gh-deployer@${PROJECT}.iam.gserviceaccount.com"
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/providers/github-provider"
TFSTATE_BUCKET="${PROJECT}-tfstate"

echo "==> Setting repo variables on ${REPO}"
gh variable set GCP_PROJECT_ID                 --repo "${REPO}" --body "${PROJECT}"
gh variable set GCP_PROJECT_NUMBER             --repo "${REPO}" --body "${PROJECT_NUMBER}"
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "${REPO}" --body "${WIF_PROVIDER}"
gh variable set GCP_DEPLOYER_SA                --repo "${REPO}" --body "${DEPLOYER_SA}"
gh variable set GCP_TFSTATE_BUCKET             --repo "${REPO}" --body "${TFSTATE_BUCKET}"
gh variable set PUBLIC_DOMAIN                  --repo "${REPO}" --body "levelup.next3k.com"
gh variable set ENABLE_LB                      --repo "${REPO}" --body "false"
gh variable set RESTRICT_INGRESS_TO_LB         --repo "${REPO}" --body "false"
gh variable set ENABLE_CLOUDFLARE              --repo "${REPO}" --body "false"   # flip to true after minting Cloudflare token

# Note: CLOUDFLARE_ZONE_ID is no longer needed — the tofu data source looks up
# the zone ID by name (var.zone_name defaults to next3k.com), avoiding the need
# to pass the zone ID manually.

echo "==> Setting EDGE_SHARED_SECRET (auto-generated 32-byte hex)"
# Generated in-memory and pushed straight to GH Secrets. Never echoed.
# Tofu (both infra/ and infra-cloudflare/) reads it from TF_VAR_edge_shared_secret
# in CI and writes it to GCP Secret Manager + Cloudflare Transform Rule, so the
# value never has to leave CI. To rotate later:
#   gh secret set EDGE_SHARED_SECRET --repo "${REPO}" --body "$(openssl rand -hex 32)"
#   gh workflow run "practice-app — build, deploy, seed"
gh secret set EDGE_SHARED_SECRET --repo "${REPO}" --body "$(openssl rand -hex 32)" >/dev/null
echo "  ✓ EDGE_SHARED_SECRET set (value not printed; tofu wires it to both GCP and Cloudflare)"
echo

echo "==> Branch protection on main"
# Solo-repo posture: protect against accidents (force-push, deletion, broken
# CI on PRs from forks) but let the owner push directly. Reviews are NOT
# required (would deadlock a solo repo). Status checks block PR merges only —
# admin direct pushes bypass them since enforce_admins=false.
gh api -X PUT "repos/${REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["CodeQL", "gitleaks", "build-deploy"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

echo "==> Enabling Dependabot security updates + vulnerability alerts"
gh api -X PUT "repos/${REPO}/vulnerability-alerts" -H "Accept: application/vnd.github+json" >/dev/null
gh api -X PUT "repos/${REPO}/automated-security-fixes" -H "Accept: application/vnd.github+json" >/dev/null

echo "==> Enabling secret scanning + push protection + private vuln reporting"
gh api -X PATCH "repos/${REPO}" -H "Accept: application/vnd.github+json" \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled' >/dev/null
gh api -X PUT "repos/${REPO}/private-vulnerability-reporting" \
  -H "Accept: application/vnd.github+json" >/dev/null

echo "==> Restricting Actions to read-only default + allow-list"
gh api -X PUT "repos/${REPO}/actions/permissions/workflow" \
  -H "Accept: application/vnd.github+json" \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false >/dev/null

# Limit to verified-creator + our explicit allow-list
# Note: -F sends typed values (booleans), -f always stringifies — `enabled` must be a real bool.
gh api -X PUT "repos/${REPO}/actions/permissions" \
  -H "Accept: application/vnd.github+json" \
  -F enabled=true -f allowed_actions=selected >/dev/null

gh api -X PUT "repos/${REPO}/actions/permissions/selected-actions" \
  -H "Accept: application/vnd.github+json" \
  -F github_owned_allowed=true \
  -F verified_allowed=true \
  -f 'patterns_allowed[]=google-github-actions/*' \
  -f 'patterns_allowed[]=opentofu/*' \
  -f 'patterns_allowed[]=gitleaks/*' \
  -f 'patterns_allowed[]=github/codeql-action/*' \
  -f 'patterns_allowed[]=actions/*' >/dev/null

echo
echo "==> Done. Verify in the GitHub UI:"
echo "  https://github.com/${REPO}/settings/variables/actions"
echo "  https://github.com/${REPO}/settings/secrets/actions"
echo "  https://github.com/${REPO}/settings/branches"
echo "  https://github.com/${REPO}/settings/security_analysis"
echo "  https://github.com/${REPO}/settings/actions"
