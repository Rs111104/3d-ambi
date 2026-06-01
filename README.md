# 3D Ambi Anti-Cheat Test

WebGL angle-dependent text rendering with MediaPipe face tracking for proctored assessment sessions.

## Features

- Real questions render only near the calibrated straight-ahead viewing angle.
- Left and right decoy questions render when the candidate moves outside the valid zone.
- Candidate name and timestamp watermark are drawn into the canvas texture.
- MediaPipe FaceMesh estimates yaw from the webcam.
- Mobile sessions can use device orientation when available.
- Missing face detection is logged after 2 seconds.
- Answer buttons disable immediately after first click.
- Answer submissions retry up to 3 times with a 500 ms delay before local queueing.
- The next question preloads while the candidate answers the current one.
- Camera-unavailable sessions fall back to straight-ahead rendering after 1 second.

## Run Locally

```bash
cd backend
python server.py
```

Open:

```text
http://127.0.0.1:8080/test
```

Admin:

```text
http://127.0.0.1:8080/admin
```

Default admin credentials are configured through `.env`:

```text
ADMIN_USER=admin
ADMIN_PASSWORD=admin123!
```

## Configuration

Client constants are grouped in `CONFIG` at the top of the session script:

- `maxAngle`
- `transition`
- `validZone`
- `maxQuestions`
- `cameraFallbackMs`
- `faceMissingMs`
- `submitRetries`
- `submitRetryDelayMs`

Server settings are available in the admin UI and persisted in SQLite.

## Backend Change List

- `/api/session/next` now returns plain JSON over HTTPS-compatible transport instead of an encrypted `payload` wrapper.
- Removed the server response call to `encrypt_payload`.
- Removed the unused `encrypt_payload` helper.
- Removed the unused `base64` import.
- Existing session, answer, event, result, invite, and admin endpoints remain unchanged.
