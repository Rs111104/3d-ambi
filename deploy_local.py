import os
import sys
from waitress import serve

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from server import app, db

if __name__ == "__main__":
    # Initialize DB
    with app.app_context():
        db.init_db()
    
    port = int(os.environ.get("PORT", 8080))
    print(f"💎 3D Ambi Engine starting on http://localhost:{port}")
    print(f"Admin Username: {os.environ.get('ADMIN_USER')}")
    print("Admin Password: admin123")
    
    serve(app, host="0.0.0.0", port=port)
