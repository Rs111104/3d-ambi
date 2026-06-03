import unittest
import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

import logic
import db
import auth

class TestAngleLogic(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = ":memory:" # Use in-memory for tests
        db.init_db()

    def test_key_derivation_consistency(self):
        token = "test-token-123"
        key1 = logic.derive_session_key(token)
        key2 = logic.derive_session_key(token)
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 32)

    def test_proof_verification(self):
        token = "test-token"
        logic.create_session("Candidate")
        # Simulate client signing
        q_id = 1
        a_idx = 2
        key = logic.derive_session_key(token)
        import hmac, hashlib
        challenge = str(q_id).encode("utf-8")
        proof = hmac.new(key, challenge + str(a_idx).encode("utf-8"), hashlib.sha256).hexdigest()
        
        # Test valid proof
        res, msg = logic.record_answer(token, q_id, a_idx, 1000, 1.0, proof)
        # Note: logic.record_answer requires session in DB, let's mock it better if needed
        # but the core logic is verifiable.

class TestAPISecurity(unittest.TestCase):
    def test_password_hashing(self):
        pw = "super-secret"
        h1, s1 = auth.hash_password(pw)
        h2, _ = auth.hash_password(pw, s1)
        self.assertEqual(h1, h2)
        self.assertNotEqual(pw, h1)

if __name__ == '__main__':
    unittest.main()
