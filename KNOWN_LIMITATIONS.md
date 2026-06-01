1. The anti-cheat renderer depends on WebGL, so very old browsers or locked-down corporate browsers may not load the candidate test.
2. Webcam head tracking quality depends on lighting, camera resolution, glasses glare, and whether the candidate keeps their face in frame.
3. Screen capture detection is limited because browsers do not expose a universal event when an operating system screenshot or external recording app is used.
4. The Screen Capture API wrapper can log attempts made through the browser API, but it cannot detect every native desktop capture tool.
5. Gyroscope support varies by mobile browser, and iOS requires a user permission prompt before motion data is available.
6. Android devices usually expose DeviceOrientation data more freely, but sensor calibration differs by hardware model.
7. Local-network phone access only works when the phone and computer are on the same WiFi and the computer firewall allows port 8080.
8. LLM decoy generation needs an API key; without one, the app uses deterministic fallback decoys suitable for local testing.
