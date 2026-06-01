1. Install Python 3 from https://www.python.org/downloads/ if it is not already installed.
2. Download or clone this project from https://github.com/Rs111104/3d-ambi and open the project folder.
3. Get an LLM API key from https://platform.openai.com/api-keys if you want new decoy questions to be generated automatically.
4. On Windows, double-click run.bat the first time and it will create .env, create .venv, install dependencies, start the backend, and open the app.
5. On Mac, open Terminal in the project folder, run chmod +x run.sh once, then run ./run.sh.
6. On later Windows runs, double-click run.bat again.
7. On later Mac runs, run ./run.sh again.
8. Open http://localhost:8080 for the candidate test if the browser does not open automatically.
9. Open http://localhost:8080/admin for the admin dashboard.
10. Log in to the admin dashboard with username admin and password admin123!.
11. Use the Questions tab to add questions, regenerate decoys, and review decoy quality scores.
12. Use the Test Sets tab to create named assessments and candidate invite links.
13. Use Mobile access in the admin dashboard to show a QR code for phones on the same WiFi network.
14. During a candidate test, the platform checks viewing angle, liveness, tab changes, clipboard attempts, and other integrity signals.
