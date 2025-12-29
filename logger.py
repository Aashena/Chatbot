#Cloud logger
import json
import logging
from datetime import datetime

logger = logging.getLogger("rag_logger")
logger.setLevel(logging.INFO)

def log_interaction(question, context, answer, conv_history):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "question": question,
        "answer": answer,
        "conv_history": conv_history,
        "context": context,
        "type": "rag_interaction",
    }

    logger.info(json.dumps(record))
