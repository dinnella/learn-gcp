# Practice-test app — *Next3k LevelUp*

Interactive PCA + DevOps practice exam, with **full local emulation** of GCP services so you can develop and run questions without spending money. Production deploys to Cloud Run + Firestore (Native) via GitHub Actions + OpenTofu.

- **Brand:** Next3k LevelUp
- **Production URL:** https://levelup.next3k.com (Cloud Run service behind a custom domain mapping)
- **Local URL:** http://localhost:8080

> The directory, container, and image names stay `practice-app` — that's the internal codename. The user-facing brand is *Next3k LevelUp*.

## Architecture

```
            ┌─────────────────────────────────────────────────────┐
            │  practice-app (FastAPI, Python)                     │
            │  ┌────────────────┐    ┌──────────────────────────┐ │
            │  │ Vanilla JS SPA │───▶│ /api/...   (REST)        │ │
            │  └────────────────┘    └──────────┬───────────────┘ │
            └───────────────────────────────────┼─────────────────┘
                                                │
                              ┌─────────────────┴─────────────────┐
                              ▼                                   ▼
                     ┌─────────────────┐              ┌─────────────────┐
                     │ Firestore       │              │ GCS bucket      │
                     │ (sessions,      │              │ (question bank  │
                     │  questions)     │              │  loaded at boot)│
                     └─────────────────┘              └─────────────────┘
```

| Layer | Local (`make up`) | Production (`tofu apply`) |
|---|---|---|
| App | Container on `localhost:8080` | Cloud Run service (us-central1) |
| Firestore | [Official emulator](https://cloud.google.com/firestore/native/docs/emulator) (no GCP creds needed) | Firestore in Native mode |
| GCS | [`fsouza/fake-gcs-server`](https://github.com/fsouza/fake-gcs-server) | Real Cloud Storage bucket |
| Auth | None (dev mode) | Optional: IAP or `--allow-unauthenticated` (configurable) |

The same Python code runs in both. The client libraries auto-detect the emulators via standard env vars (`FIRESTORE_EMULATOR_HOST`, `STORAGE_EMULATOR_HOST`).

## Repo layout

```
practice-app/
  backend/
    app/                FastAPI app + static SPA
      static/           index.html, app.js, styles.css
    seed/questions.json Question bank (committed source of truth)
    Dockerfile          Multi-stage build, distroless final
    requirements.txt
  infra/                OpenTofu for Cloud Run + Firestore + Artifact Registry
  docker-compose.yml    Firestore + fake-gcs + app, all wired
  Makefile              up / down / seed / logs / test / build / push
  README.md             you are here
```

## Quickstart (local, no GCP account required)

```bash
cd practice-app
make up        # starts firestore emulator, fake-gcs, app
make seed      # loads question bank into the emulator
open http://localhost:8080
```

`make down` stops everything; data is **not** persisted between sessions (emulator is in-memory by design).

## Game modes

**Classic** — 10 scenario questions on a single exam, fixed difficulty. Per-section report card with study recommendations. Per-exam leaderboard.

**Progressive** — adaptive difficulty across all loaded exams. First question is medium; each correct answer steps up (medium → hard); each wrong answer steps down. **3 strikes ends the run.** Scoring: easy = 1 pt, medium = 2 pts, hard = 4 pts. Final results show your **percentile** vs all saved progressive runs and a per-exam breakdown. Single shared leaderboard.

**Arcade** — 2-minute sprint, rapid-fire (no Lock-it-in button — first click locks the answer). Each correct answer adds points (500 / 1000 / 2000) and adds time (10 / 15 / 20 s). Wrong answers only debit time. **Level up every 10 correct** — the difficulty mix gets harder and the timer resets to 110 → 100 → 90s. Single shared leaderboard sorted by score, then level, then correct-count.

The mode picker is on the home screen. Quit any in-progress run with the `Quit run` button — abandoned runs do **not** get saved to the leaderboard.

## Quickstart (deploy to your real GCP project)

After completing repo bootstrap and pushing to GitHub:

```bash
# Either: manual one-shot
cd practice-app/infra
tofu init -backend-config="bucket=$GCP_TFSTATE_BUCKET" -backend-config="prefix=practice-app"
tofu apply -var "project_id=$GCP_PROJECT_ID"

# Or: via GitHub Actions
git push origin main   # workflow .github/workflows/practice-app.yml runs
```

The first apply creates Firestore + Artifact Registry + Cloud Run. Subsequent pushes rebuild the container and roll Cloud Run forward.

## Why this design (translation for AWS/Azure folks)

| Concern | What we do here | AWS analog | Azure analog |
|---|---|---|---|
| Local emulation of cloud DB | Firestore emulator | DynamoDB Local | Cosmos DB emulator |
| Local emulation of object storage | fake-gcs-server | LocalStack S3 / MinIO | Azurite |
| Auth in container deploys | Workload Identity (Cloud Run runs as a SA) | Task Role on Fargate | Managed Identity on Container Apps |
| Container registry | Artifact Registry | ECR | ACR |
| Build & deploy | Cloud Build (image) → Cloud Run (rev) | CodeBuild + ECS Service | Pipelines + Container Apps |

## Adding questions

Edit [backend/seed/questions.json](backend/seed/questions.json) and re-run `make seed` (local) or trigger the seed workflow (prod, idempotent — see `make seed-prod`).
