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
