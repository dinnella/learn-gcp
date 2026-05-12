# Security policy

## Supported versions

Only the latest `main` branch is supported. Production runs the latest commit on
`main` deployed to Cloud Run.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report privately by emailing **security@next3k.com** with:

- a description of the issue,
- steps to reproduce (or a proof-of-concept),
- the impact you believe it has,
- any suggested remediation.

You can expect an acknowledgement within 5 business days. We will work with you
on a coordinated disclosure timeline.

## Scope

In scope:

- The deployed application at `https://levelup.next3k.com`
- Source under `practice-app/` in this repository
- Terraform / OpenTofu infra under `practice-app/infra/`
- GitHub Actions workflows under `.github/workflows/`

Out of scope:

- Denial of service via brute-force traffic (Cloud Armor handles this; report
  bypasses, not raw volume).
- Findings only reproducible against the local emulator (`docker-compose`).
- Social engineering, physical attacks, or third-party services.

## Things that are *intentionally* public

- Source code, including the question bank, seed data, and infrastructure.
- The `next3k.com` brand and `levelup.next3k.com` hostname.
- The internal codename `practice-app` (directory, container, image name).

None of these constitute a finding by themselves.
