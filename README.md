# AI-Powered Virtual Assistant for Your Website

**Set up an AI virtual assistant for your website in minutes — no coding required.**

Use the self-serve tool to crawl, index, and deploy a chatbot trained on your website's content:

**[Get Started — Launch the Setup Tool](https://aashena.github.io/Chatbot/)**

Simply enter your domain, let the system crawl your pages, and embed the chat widget on your site. Your visitors will get instant, context-aware answers drawn directly from your website's content.

---

## What Is This?

This project provides a complete **Retrieval-Augmented Generation (RAG)** chatbot system that turns any website into an interactive knowledge base. It crawls your site, indexes the content into a vector database, and serves intelligent answers through an embeddable chat widget — all deployed on **Google Cloud Run** for reliable, auto-scaling performance.

### How It Works

```
Your Website → Crawler → Content Indexer → Vector Database
                                                  ↓
                              Visitor Question → Retriever → LLM → Answer
```

1. **Crawl** — The system discovers all pages on your domain while respecting `robots.txt` rules
2. **Index** — Page content is extracted, cleaned, chunked, deduplicated, and stored as vector embeddings
3. **Answer** — When a visitor asks a question, the most relevant content chunks are retrieved and fed to a large language model to generate an accurate, grounded response

---

## Key Features

### Virtual Assistant Widget
- Embeddable chat widget that integrates into any website with a single script tag
- Dark-themed, responsive UI (works on desktop and mobile)
- Markdown rendering and code syntax highlighting in responses
- Conversation history for natural multi-turn dialogue
- Welcome message personalized to your website

### Intelligent Q&A Pipeline
- **RAG architecture** — answers are grounded in your actual website content, reducing hallucinations
- **Multi-model fallback** — automatically cycles through Google Gemini models (`gemini-2.5-pro`, `gemini-3-flash-preview`, `gemini-2.0-flash`, and more) if rate limits are hit
- **Structured response validation** — each answer is classified by source type (`website_content`, `general_knowledge`, or `none`) with validity checks
- **Namespace isolation** — run multiple independent chatbots from a single deployment, each scoped to a different website

### Polite Web Crawling
- Respects `robots.txt` directives and `Crawl-Delay` settings
- Configurable concurrency and delay between requests
- Filters out non-content resources (PDFs, images, navigation elements)
- Real-time streaming progress via Server-Sent Events (SSE)
- Session-based crawl management — start, monitor, and stop crawls at any time

### Content Indexing
- Extracts clean markdown from web pages using headless browser rendering (Playwright)
- Handles JavaScript-heavy and single-page applications
- Recursive text splitting (1000-char chunks with 100-char overlap)
- MD5-based deduplication at both URL and chunk level
- Batch processing for large sites (up to 1000 URLs)

### Monitoring & Alerts
- Structured JSON logging for Google Cloud Logging
- Telegram bot notifications when the assistant fails to answer a question
- Logs include full context: question, answer, source, validity, and conversation history

---

## Deployed on Google Cloud Run

The backend is fully containerized and deployed on **Google Cloud Run**, providing:

- **Serverless auto-scaling** — scales from zero to handle traffic spikes, scales back down when idle
- **CI/CD pipeline** — every push to `main` triggers automated testing, Docker image build, and deployment via GitHub Actions
- **Production-grade infrastructure** — managed TLS, health checks, and 600-second request timeout for long crawl/index operations

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (docs/)                   │
│  ┌──────────────┐  ┌─────────────────────────────┐  │
│  │  Chat Widget  │  │  Management UI (Crawl/Index) │  │
│  │  (Embeddable) │  │  (Self-Serve Setup Tool)     │  │
│  └──────┬───────┘  └──────────┬──────────────────┘  │
└─────────┼──────────────────────┼────────────────────┘
          │                      │
          ▼                      ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend (src/)                   │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │  /chat    │  │  /crawl   │  │  /index          │  │
│  │ endpoint  │  │  stream   │  │  stream           │  │
│  └─────┬────┘  └─────┬─────┘  └────────┬─────────┘  │
│        │              │                  │            │
│  ┌─────▼────┐  ┌──────▼──────┐  ┌───────▼────────┐  │
│  │ QA Chain  │  │  Crawler    │  │  Indexer        │  │
│  │ (LLM+RAG)│  │  (Polite)   │  │  (Playwright)   │  │
│  └─────┬────┘  └─────────────┘  └───────┬────────┘  │
└────────┼────────────────────────────────┼────────────┘
         │                                │
         ▼                                ▼
┌─────────────────┐            ┌──────────────────────┐
│  Google Gemini   │            │  Upstash Vector DB    │
│  (LLM Provider)  │            │  (Embeddings Store)   │
└──────────────────┘            └───────────────────────┘
```

---

## Tech Stack

| Layer         | Technology                                           |
|---------------|------------------------------------------------------|
| **Backend**   | Python, FastAPI, Uvicorn                             |
| **LLM**       | Google Gemini (via LangChain)                        |
| **Vector DB** | Upstash Vector (serverless, managed embeddings)      |
| **Crawling**  | Crawl4AI, Playwright (headless browser)              |
| **Frontend**  | Vanilla JavaScript, marked.js, DOMPurify             |
| **Infra**     | Docker, Google Cloud Run, GitHub Actions CI/CD       |
| **Monitoring**| Google Cloud Logging, Telegram Bot alerts            |

---

## API Endpoints

| Method | Endpoint               | Description                                  |
|--------|------------------------|----------------------------------------------|
| POST   | `/chat`                | Ask a question against an indexed namespace  |
| POST   | `/crawl/stream`        | Start a streaming crawl session              |
| POST   | `/crawl/stop/{id}`     | Stop an active crawl session                 |
| GET    | `/crawl/urls/{id}`     | Get discovered URLs for a session            |
| POST   | `/index/stream`        | Index URLs with real-time progress streaming |
| GET    | `/health`              | Health check                                 |

---

## Getting Started

### Prerequisites

- Python 3.10+
- A [Google AI API key](https://ai.google.dev/) (for Gemini)
- An [Upstash Vector](https://upstash.com/) database

### Local Development

```bash
# Clone the repository
git clone https://github.com/Aashena/Chatbot.git
cd Chatbot

# Create and activate environment
conda create --name chat_bot python=3.10
conda activate chat_bot

# Install dependencies
pip install -r requirements.txt
playwright install

# Set environment variables
export GOOGLE_API_KEY=<your-key>
export UPSTASH_VECTOR_REST_URL=<your-url>
export UPSTASH_VECTOR_REST_TOKEN=<your-token>
export TELEGRAM_BOT_TOKEN=<your-token>       # optional
export TELEGRAM_CHAT_ID=<your-chat-id>        # optional
export PYTHONPATH=src

# Run the API server
uvicorn main:app --reload
# API docs available at http://localhost:8000/docs

# In a separate terminal, serve the frontend
cd docs && python -m http.server 8001
# Management UI at http://localhost:8001/
```

### Docker

```bash
docker build --platform linux/amd64 -t chatbot .
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=<your-key> \
  -e UPSTASH_VECTOR_REST_URL=<your-url> \
  -e UPSTASH_VECTOR_REST_TOKEN=<your-token> \
  chatbot
```

---

## Embedding the Widget on Your Website

After indexing your site through the [setup tool](https://aashena.github.io/Chatbot/), add the chat widget to your website:

```html
<script src="https://aashena.github.io/Chatbot/widget-loader.js"></script>
<script>
  loadChatWidget("your-namespace", "https://your-cloudrun-url.run.app");
</script>
```

A floating chat button will appear in the bottom-right corner of your site, ready to answer visitor questions based on your indexed content.

---

## Project Structure

```
ChatBot/
├── src/
│   ├── main.py                  # FastAPI application and endpoints
│   ├── QA_pipeline.py           # RAG chain and LLM orchestration
│   ├── mycrawler.py             # Web crawler with streaming support
│   ├── indexer.py               # Content indexing pipeline
│   ├── logger.py                # Structured cloud logging
│   └── telegram_handler.py      # Telegram alert notifications
├── docs/
│   ├── index.html               # Self-serve management UI
│   ├── widget-loader.js         # Embeddable chat widget
│   ├── crawl.js                 # Crawl module (frontend)
│   └── index.js                 # Index module (frontend)
├── tests/                       # pytest test suite
├── Dockerfile                   # Container image definition
├── requirements.txt             # Python dependencies
└── .github/workflows/deploy.yml # CI/CD pipeline
```

---

## License

This project is open source. See the repository for license details.
