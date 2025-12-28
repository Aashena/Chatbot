#Cloud logger
import json
import logging
from datetime import datetime

logger = logging.getLogger("rag_logger")
logger.setLevel(logging.INFO)

def log_interaction(question, context, answer):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "question": question,
        "context": context,
        "answer": answer,
        "type": "rag_interaction",
    }

    logger.info(json.dumps(record))
