from fastapi import FastAPI
from pydantic import BaseModel
from QA_pipeline import ask

#This line is for loggin in cloud env
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

#Escaping CORS errors
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TEMPORARY – see security notes below
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    answer = ask(request.question)
    return {"answer": answer}

@app.get("/health")
def health():
    return {"status": "ok"}
