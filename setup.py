import os
import sqlite3
import time
import json

def setup():
    print("💎 Initializing 3D Ambi - Excellence Edition...")
    
    try:
        import cryptography
        import dotenv
    except ImportError:
        print("❌ Missing dependencies. Run: pip install cryptography python-dotenv")
        return

    # Ensure backend folder exists
    os.makedirs("backend", exist_ok=True)

    from backend.db import init_db, db_connect
    init_db()
    
    conn = db_connect()
    count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    if count == 0:
        print("🌱 Seeding high-quality sample questions...")
        samples = [
            ("Computer Science", "Medium", "Which complexity class represents problems solvable in polynomial time?", ["P", "NP", "NP-Hard", "PSPACE"], 0, "What is the primary function of an OS?", ["Gaming", "Resource Management", "Web Browsing", "Spreadsheets"]),
            ("Web Security", "Hard", "Which mechanism prevents Cross-Site Request Forgery?", ["CORS", "CSRF Tokens", "HSTS", "CSP"], 1, "What does HTTPS stand for?", ["Secure Text", "Hypertext Transfer Protocol Secure", "High Tech", "None of these"])
        ]
        for s in samples:
            conn.execute("""
                INSERT INTO questions (subject, difficulty, question_text, options_json, correct_index, decoy_left_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (s[0], s[1], s[2], json.dumps(s[3]), s[4], s[5], int(time.time())))
        conn.commit()
    conn.close()

    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("PORT=8080\nADMIN_USER=admin\nADMIN_PASS=admin123\n")
        print("📝 Created default .env file")

    print("\n✅ Ready for review! Launch the system:")
    print("   python backend/server.py")
    print("\n🔗 Dashboard: http://localhost:8080/admin.html (admin/admin123)")

if __name__ == "__main__":
    setup()
