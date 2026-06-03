# Changelog

All notable changes to **3D Ambi** will be documented in this file.

## [1.1.0] - 2026-06-03
### Added
- **Core Mechanic:** Ultra-smooth WebGL transition and parallax decoy rendering.
- **Admin Dashboard:** Full question management UI (Create/Edit/Delete).
- **Admin Dashboard:** Question preview simulator with angle-switch preview.
- **Admin Dashboard:** Session replay mode for granular behavioral auditing.
- **Visuals:** Dark mode support for both candidate and proctor interfaces.
- **Accessibility:** Full keyboard navigation support and ARIA labels.
- **Reliability:** Pre-test biometric checklist (Lighting, Face, Camera).
- **Tests:** Integration tests for angle-detection logic and API contracts.
- **CI/CD:** GitHub Actions workflow for automated testing.

## [1.0.0] - 2026-06-02
### Added
- **Security:** AES-GCM question encryption and HMAC-SHA256 response signing.
- **Architecture:** Refactored to modular Python backend (Routing, Logic, Auth, DB).
- **Proctoring:** Real-time event streaming via Server-Sent Events (SSE).
- **Persistence:** SQLite durable storage for sessions and events.
- **Documentation:** Technical README with architecture deep-dive.

## [0.1.0] - Initial Prototype
- Basic WebGL rendering and MediaPipe face tracking integration.
