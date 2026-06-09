# Changelog

All notable changes to **3D Ambi** will be documented in this file.

## [1.1.0] - 2026-06-03
### Added
- **Core Mechanic:** Ultra-smooth WebGL transition and parallax decoy rendering.
- **Core Mechanic:** Directional decoys — left-side and right-side viewers see different questions.
- **Admin Dashboard:** Full question management UI (Create/Edit/Delete) with per-question decoy fields.
- **Admin Dashboard:** Question preview simulator with angle-switch preview.
- **Admin Dashboard:** Session replay mode for granular behavioral auditing.
- **Visuals:** Dark mode support for both candidate and proctor interfaces.
- **Accessibility:** Full keyboard navigation support and ARIA labels.
- **Reliability:** Pre-test biometric checklist (Lighting, Face, Camera).
- **Tests:** Integration tests for API contracts, session management, and decoy fields.
- **CI/CD:** GitHub Actions workflow for automated testing with pytest.

### Security
- **AES-256-GCM encryption** for question and decoy payloads in transit (per-session key).
- **Content Security Policy** header with strict script/style/font directives.
- **Rate limiting** on question and decoy endpoints (60/min).
- **Inactivity timeout enforcement** with configurable duration via admin settings.
- **HTTPS enforcement warning** when running in production without `SECURE_COOKIES=true`.

## [1.0.0] - 2026-06-02
### Added
- **Architecture:** Modular Python backend with Flask routing, auth, and SQLite persistence.
- **Proctoring:** Real-time flag event logging for behavioral anomalies (tab switch, no face, multi-face, no blink).
- **Persistence:** SQLite WAL-mode storage for sessions, questions, flag events, and admin sessions.
- **Security:** bcrypt password hashing, CSRF header validation, admin session tokens with 1-hour expiry.
- **Documentation:** Technical README with architecture overview and security model.

## [0.1.0] - Initial Prototype
- Basic WebGL rendering and MediaPipe face tracking integration.
