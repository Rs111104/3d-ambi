import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
import auth
from config import Config

def debug_auth():
    print(f"Config Admin User: {Config.ADMIN_USER}")
    print(f"Config Admin Pass: {Config.ADMIN_PASS}")
    
    res = auth.authenticate_admin(Config.ADMIN_USER, Config.ADMIN_PASS)
    print(f"Auth result: {res}")

if __name__ == "__main__":
    debug_auth()
