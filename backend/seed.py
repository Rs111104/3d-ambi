import sqlite3
import json
import time
import os

def seed():
    db_path = os.path.join(os.path.dirname(__file__), "data.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    questions = [
        ("Science", "What is H2O?", json.dumps(["Water", "Acid", "Salt", "Gas"]), 0, "Is it blue?", "Is it wet?"),
        ("History", "Who wrote the Great Gatsby?", json.dumps(["F. Scott Fitzgerald", "Ernest Hemingway", "Mark Twain", "Charles Dickens"]), 0, "When?", "Where?"),
        ("Tech", "Which architectural pattern decouples storage from logic?", json.dumps(["MVC", "Monolith", "Serverless", "Edge"]), 0, "Is it fast?", "Is it secure?"),
        ("Science", "What is the powerhouse of the cell?", json.dumps(["Mitochondria", "Nucleus", "Ribosome", "Cytoplasm"]), 0, "Is it big?", "Is it small?"),
        ("Geography", "What is the capital of France?", json.dumps(["Paris", "Lyon", "Marseille", "Nice"]), 0, "Is it rainy?", "Is it sunny?")
    ]
    
    cur.executemany("""
        INSERT INTO questions (subject, question_text, options_json, correct_index, decoy_left_text, decoy_right_text, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, [q + (int(time.time()),) for q in questions])
    
    conn.commit()
    conn.close()
    print("Database seeded with sample questions.")

if __name__ == "__main__":
    seed()
