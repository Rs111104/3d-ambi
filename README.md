# 3d-ambi

Anti-cheat online test system that uses face tracking and angle-dependent WebGL rendering to show real questions only to the candidate sitting straight.

## How It Works

The candidate's webcam estimates whether they are facing the screen directly. When they sit straight, the canvas shows the real question. When someone views from the side, the canvas blends into a decoy question. The page also records review signals such as tab switches, missing face detection, right-click attempts, screen-capture attempts, and suspicious stillness. Webcam analysis runs in the browser and video is not uploaded.

## Folder Structure

```text
3d-ambi/
├── frontend/
│   ├── index.html
│   ├── admin.html
│   └── styles.css
├── backend/
│   ├── server.py
│   └── requirements.txt
├── .gitignore
└── README.md
```

## Setup

```bash
git clone <your-repo-url>
cd 3d-ambi/backend
pip install -r requirements.txt
python server.py
```

Candidate page:

```text
http://127.0.0.1:8080/test
```

Admin page:

```text
http://127.0.0.1:8080/admin
```

## Environment Variables

| Variable | Required | Description |
|---|---:|---|
| `LLM_API_KEY` | No | API key used for generated decoy questions when enabled. |
| `ADMIN_USER` | Yes | Admin dashboard username. |
| `ADMIN_PASSWORD` | Yes | Admin dashboard password. |
| `PORT` | No | Server port. Defaults to `8080`. |

Warning: set `ADMIN_USER` and `ADMIN_PASSWORD` before going live.

## Deployment On Render

1. Create a free account on Render.
2. Click New Web Service.
3. Connect your GitHub account and pick this repository.
4. Set the start command to `python backend/server.py`.
5. Set the region closest to your candidates.
6. Add a service name and click Create Web Service.
7. When the service is live, open the public Render URL and confirm the candidate page loads.
8. Open the same URL with `/admin` at the end to reach the admin page.
9. Add `LLM_API_KEY` if you want generated decoys.
10. Set `ADMIN_USER` and `ADMIN_PASSWORD` before sharing the admin page.

## Security Notes

Question text is delivered as plain JSON over HTTPS and rendered into a canvas rather than normal page text. The system blocks embedding, rate-limits session endpoints, records suspicious behavior, and keeps webcam analysis on the candidate device. No video is uploaded. Review signals are stored as events so administrators can audit sessions after completion.

## Self-Directed Excellence (process templates)

We use a compact improvement and decision workflow to run biweekly experiments, capture decisions, and keep changes reversible.

- Framework checklist: [SELF-DIRECTED-EXCELLENCE.md](SELF-DIRECTED-EXCELLENCE.md)
- Two-week sprint template: [TWO-WEEK-IMPROVEMENT.md](TWO-WEEK-IMPROVEMENT.md)
- Decision log & ADR: [DECISION-LOG-ADR.md](DECISION-LOG-ADR.md)
- PR template: [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)

Create a new sprint file from the template:

```bash
python scripts/new_sprint.py --title "Sprint name"
```

Sprint files are stored under the `sprints/` folder.

## Deployment

The project includes a Dockerfile and a `docker-compose.yml` for local deployment, and a GitHub Actions workflow that builds and pushes a Docker image to GitHub Container Registry (GHCR).

Local run with Docker Compose:

```bash
docker compose build
docker compose up -d
```

Build and run locally without Docker Compose:

```bash
docker build -t 3d-ambi:local .
docker run -p 8080:8080 3d-ambi:local
```

CI: The workflow `.github/workflows/ci-build-push.yml` builds and pushes the image to `ghcr.io/<org>/3d-ambi:latest` on pushes to `main`. To enable pushing to GHCR, the workflow uses the `GITHUB_TOKEN` with `packages: write` permission.

Optional: Deploy to Render

- Create a Render web service and point it at the repository, or configure Render to pull your container image from GHCR.
- To enable CI-triggered Render deployments, add a deploy step to the workflow and set `RENDER_API_KEY` and `RENDER_SERVICE_ID` as repository secrets.

