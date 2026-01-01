#Cloud logger
import json
import logging
from datetime import datetime

logger = logging.getLogger("rag_logger")
logger.setLevel(logging.INFO)

def log_interaction(namespace, question, context, answer, conv_history):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "namespace": namespace,
        "question": question,
        "answer": answer,
        "conv_history": conv_history,
        "context": context,
        "type": "rag_interaction",
    }

    logger.info(json.dumps(record))
