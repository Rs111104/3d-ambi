# Contributing to 3D Ambi

Thank you for your interest in improving 3D Ambi! This project aims to be the gold standard for browser-based proctoring.

## How to Add New Proctoring Signals

1.  **Client-side:**
    *   In `frontend/index.html`, add a listener for the browser event (e.g., `visibilitychange`).
    *   Call `await fetch('/api/session/event', { ... })` with the event type and details.
2.  **Server-side:**
    *   Add the new event type to the `flagged_types` set in `backend/logic.py`'s `compute_integrity` function if it should impact the integrity score.
    *   Define the penalty weight for the new signal.

## How to Add New Question Types

The current system supports Multiple Choice Questions (MCQs). To add a new type (e.g., Free Text):

1.  **Database:** Update `db.py` to include any necessary columns in the `questions` table.
2.  **Backend:** Update `logic.py`'s `record_answer` to handle the new format.
3.  **Frontend:** Update `index.html`'s `startQ` function to render the appropriate input UI based on the question type.

## Development Setup

1.  Install Python 3.10+
2.  Run `python setup.py` to initialize the database and seed sample data.
3.  Run `python backend/server.py` to start the server.
