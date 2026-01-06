#Cloud logger
import json
import logging
from datetime import datetime

logger = logging.getLogger("rag_logger")
logger.setLevel(logging.INFO)

def log_interaction(namespace, question, context, response,  conv_history):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "namespace": namespace,
        "question": question,
        "answer": response.answer,
        "answer_source": response.source_type,
        "answer_validity": response.is_valid,
        "invalidity_reason": response.reason,
        "conv_history": conv_history,
        "context": context,
        "type": "rag_interaction",
    }

    logger.info(json.dumps(record))
