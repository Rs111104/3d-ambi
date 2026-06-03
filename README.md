# 3D Ambi: Biometric Angle-Dependent Assessment

[![Security Hardened](https://img.shields.io/badge/Security-Hardened-success.svg)](#-security-architecture)
[![CI Pipeline](https://github.com/Rs111104/3d-ambigram/actions/workflows/ci.yml/badge.svg)](https://github.com/Rs111104/3d-ambigram/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**3D Ambi** is a high-integrity proctoring solution that uses computer vision to ensure test content is only visible to the authorized candidate. By tracking head orientation in real-time, it dynamically cross-fades real questions into plausible decoys for side-viewers or unauthorized captures.

---

## 🚀 The Excellence Pass

This project demonstrates a production-grade implementation of computer vision and browser-based security:
- **Smooth Mechanics:** WebGL shaders provide ultra-smooth, parallax transitions.
- **Robust Tracking:** MediaPipe Face Mesh handles low light and biometric baselining.
- **Airtight Security:** AES-GCM encrypted delivery + HMAC-SHA256 rendering proofs.
- **Proctoring Suite:** Real-time monitoring, session replay, and forensic timelines.

---

## 🛠️ System Architecture

The system is built with a decoupled, modular architecture designed for scalability and security.

```mermaid
graph TD
    subgraph Frontend (Vanilla JS + WebGL)
        C[Candidate Client] -->|Face Tracking| CV[MediaPipe]
        C -->|Secure Render| GL[WebGL Engine]
        C -->|Decrypt| WC[Web Crypto API]
    end
    
    subgraph Backend (Python)
        S[Threaded Server] -->|Middleware| A[Auth & CSRF]
        S -->|Business Logic| L[Logic & Crypto]
        L -->|Persistence| DB[(SQLite)]
        S -->|Real-time| SSE[SSE Stream]
    end
    
    C <-->|Encrypted JSON| S
```

---

## 🛡️ Security Architecture

1.  **Encrypted Data Pipeline:** Questions are encrypted on-the-fly using **AES-256-GCM**. The decryption key is derived from the session token using an HKDF-like construction and exists only in the client's volatile memory.
2.  **Cryptographic Proof of Rendering:** Every answer must be accompanied by an **HMAC-SHA256 signature**. This signature can only be generated if the client is currently rendering the correct question at the authorized viewing angle.
3.  **Proctoring Integrity:** Real-time behavioral signals (tab switches, face loss, inactivity) are streamed to the admin dashboard via **Server-Sent Events (SSE)**.

---

## 📱 Features & UX

### Candidate Interface
- **Biometric Checklist:** Pre-test verification of camera, lighting, and face detection.
- **Dark Mode Support:** Native OS theme detection for reduced eye strain.
- **Keyboard Accessible:** Full ARIA compliance and keyboard navigation support.

### Admin Command Center
- **Question Management:** Full CRUD interface for managing assessment content.
- **Angle Simulator:** Visual testing tool for simulating rendering mechanics without a camera.
- **Forensic Replay:** Scrub through a candidate's behavioral timeline with millisecond precision.

---

## 🏁 Quick Start

1.  **Clone & Install:**
    ```bash
    git clone https://github.com/Rs111104/3d-ambigram.git
    cd 3d-ambigram
    pip install cryptography python-dotenv
    ```
2.  **Setup & Seed:**
    ```bash
    python setup.py
    ```
3.  **Launch:**
    ```bash
    python backend/server.py
    ```

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for architectural guidelines and coding standards.

---
*Developed as a showcase of browser-based security and computer vision integration.*
