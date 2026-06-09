import os
import sys
from dotenv import load_dotenv
from waitress import serve

# Load env variables
load_dotenv()

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import db
from server import app

if __name__ == "__main__":
    # Initialize DB
    with app.app_context():
        db.init_db()
    
    port = int(os.environ.get("PORT", 8080))
    print(f"[*] 3D Ambi Engine starting on http://localhost:{port}")
    print(f"Admin Username: {os.environ.get('ADMIN_USER')}")
    print("Note: Admin password must be set via the ADMIN_PASSWORD_HASH environment variable.")
    
    serve(app, host="0.0.0.0", port=port)
