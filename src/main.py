from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from QA_pipeline import QA_module
from mycrawler import crawl_domain
from indexer import index_pages
from typing import List

# This line is for logging in cloud env
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(message)s",  # JSON-only
)

app = FastAPI(
    title="Website RAG Chatbot API",
    version="1.0.0",
)

# Escaping CORS errors
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TEMPORARY — see security notes below
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing models
class ChatRequest(BaseModel):
    question: str
    conv_history: str
    namespace: str

class ChatResponse(BaseModel):
    answer: str

# New models for crawler endpoint
class CrawlRequest(BaseModel):
    domain: str

class CrawlResponse(BaseModel):
    urls: List[str]
    crawl_delay: float
    max_workers: int
    total_urls: int

# New models for indexer endpoint
class IndexRequest(BaseModel):
    urls: List[str]
    namespace: str
    delay: float
    max_workers: int

class IndexResponse(BaseModel):
    status: str
    message: str
    indexed_count: int

# Existing chat endpoint
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        qa_module = QA_module(request.namespace)
        response = qa_module.ask(request.question, request.conv_history)
        return {"answer": response.answer}
    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

# New crawl endpoint
@app.post("/crawl", response_model=CrawlResponse)
def crawl(request: CrawlRequest):
    try:
        logging.info(f"Crawling domain: {request.domain}")
        urls_list, crawl_delay, max_workers = crawl_domain(request.domain)
        
        return {
            "urls": urls_list,
            "crawl_delay": crawl_delay,
            "max_workers": max_workers,
            "total_urls": len(urls_list)
        }
    except Exception as e:
        logging.error(f"Error in crawl endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Crawl error: {str(e)}")

# New index endpoint
@app.post("/index", response_model=IndexResponse)
def index(request: IndexRequest):
    try:
        logging.info(f"Indexing {len(request.urls)} URLs to namespace: {request.namespace}")
        index_pages(request.urls, request.namespace, request.delay, request.max_workers)
        
        return {
            "status": "success",
            "message": f"Successfully indexed {len(request.urls)} URLs to namespace '{request.namespace}'",
            "indexed_count": len(request.urls)
        }
    except Exception as e:
        logging.error(f"Error in index endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Index error: {str(e)}")

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}