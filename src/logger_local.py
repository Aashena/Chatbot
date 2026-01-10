import json
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("rag_logs.jsonl")

def log_interaction(question, context, answer):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "question": question,
        "context": context,
        "answer": answer,
    }

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")