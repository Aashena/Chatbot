from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from QA_pipeline import QA_module
from mycrawler import crawl_domain_streaming, CrawlController
from indexer import index_pages_streaming
from widget_customizer import (
    ThemeExtractor, WidgetConfigGenerator, WidgetCodeRenderer,
    WidgetConfig, PromptGuard
)
from typing import List, Dict
import json
import asyncio
import uuid

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

# Store active crawl sessions
active_crawls = {}

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

class CrawlSessionResponse(BaseModel):
    session_id: str
    message: str

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

# New streaming crawl endpoint with session management
@app.post("/crawl/stream")
async def crawl_stream(request: CrawlRequest):
    """
    Stream crawl progress as Server-Sent Events (SSE).
    Returns a session_id in the first event that can be used to stop the crawl.
    
    Each event contains:
    - type: 'session' (session info), 'url' (new URL), 'progress' (status), 'complete' (finished), or 'error'
    - data: relevant information
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Create controller for this session
    controller = CrawlController()
    active_crawls[session_id] = {
        'controller': controller,
        'domain': request.domain,
        'urls': []
    }
    
    async def event_generator():
        try:
            logging.info(f"Starting streaming crawl for domain: {request.domain} (session: {session_id})")
            
            # Send session ID as first event
            session_event = {
                "type": "session",
                "session_id": session_id,
                "message": "Crawl session started"
            }
            yield f"data: {json.dumps(session_event)}\n\n"
            
            # Run the crawler and stream results
            async for event in crawl_domain_streaming(
                request.domain,
                controller=controller
            ):
                # Store discovered URLs in the session
                if event.get('type') == 'url':
                    active_crawls[session_id]['urls'].append(event['url'])
                
                # Format as Server-Sent Event
                yield f"data: {json.dumps(event)}\n\n"
                
                # Check if stopped
                if controller.is_stopped():
                    stopped_event = {
                        "type": "stopped",
                        "message": "Crawl stopped by user",
                        "total_discovered": len(active_crawls[session_id]['urls'])
                    }
                    yield f"data: {json.dumps(stopped_event)}\n\n"
                    break
            
            # Send completion event
            completion_event = {
                "type": "complete",
                "message": "Crawling completed",
                "total_discovered": len(active_crawls[session_id]['urls'])
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
        except Exception as e:
            logging.error(f"Error in streaming crawl: {str(e)}")
            error_event = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            # Keep the session data for a bit so user can retrieve URLs
            # In production, you'd want a cleanup task
            logging.info(f"Crawl session {session_id} completed")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )

# Stop a crawl session
@app.post("/crawl/stop/{session_id}", response_model=CrawlSessionResponse)
def stop_crawl(session_id: str):
    """
    Stop an active crawl session.
    Returns the session info including discovered URLs count.
    """
    if session_id not in active_crawls:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    
    session = active_crawls[session_id]
    controller = session['controller']
    
    if controller.is_stopped():
        return {
            "session_id": session_id,
            "message": "Crawl was already stopped"
        }
    
    controller.stop()
    logging.info(f"Stopping crawl session {session_id}")
    
    return {
        "session_id": session_id,
        "message": f"Crawl stopped. {len(session['urls'])} URLs discovered."
    }

# Get discovered URLs from a session
@app.get("/crawl/urls/{session_id}")
def get_session_urls(session_id: str):
    """
    Retrieve all discovered URLs from a crawl session.
    """
    if session_id not in active_crawls:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    
    session = active_crawls[session_id]
    return {
        "session_id": session_id,
        "domain": session['domain'],
        "urls": session['urls'],
        "total_count": len(session['urls']),
        "is_stopped": session['controller'].is_stopped()
    }

# Delete a crawl session
@app.delete("/crawl/session/{session_id}")
def delete_session(session_id: str):
    """
    Delete a crawl session and free up resources.
    """
    if session_id not in active_crawls:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    
    del active_crawls[session_id]
    logging.info(f"Deleted crawl session {session_id}")
    
    return {
        "session_id": session_id,
        "message": "Session deleted successfully"
    }

# Original non-streaming crawl endpoint (kept for backward compatibility)
@app.post("/crawl", response_model=CrawlResponse)
def crawl(request: CrawlRequest):
    try:
        from mycrawler import crawl_domain
        logging.info(f"Crawling domain: {request.domain}")
        urls_list, crawl_delay, max_workers = crawl_domain(request.domain)
        
        return {
            "urls": list(urls_list),
            "crawl_delay": crawl_delay,
            "max_workers": max_workers,
            "total_urls": len(urls_list)
        }
    except Exception as e:
        logging.error(f"Error in crawl endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Crawl error: {str(e)}")

# New streaming index endpoint
@app.post("/index/stream")
async def index_stream(request: IndexRequest):
    """
    Stream index progress as Server-Sent Events (SSE).
    
    Each event contains:
    - type: 'start', 'batch_start', 'batch_complete', 'progress', 'complete', or 'error'
    - data: relevant information
    """
    async def event_generator():
        try:
            logging.info(f"Starting streaming index for {len(request.urls)} URLs to namespace: {request.namespace}")
            
            # Stream progress updates from indexer
            async for event in index_pages_streaming(
                request.urls,
                request.namespace,
                request.delay,
                request.max_workers
            ):
                # Format as Server-Sent Event
                yield f"data: {json.dumps(event)}\n\n"
            
        except Exception as e:
            logging.error(f"Error in streaming index: {str(e)}")
            error_event = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Old non-streaming index endpoint (kept for backward compatibility)
@app.post("/index", response_model=IndexResponse)
def index(request: IndexRequest):
    try:
        from indexer import index_pages
        logging.info(f"Indexing {len(request.urls)} URLs to namespace: {request.namespace}")
        num_chunks = index_pages(request.urls, request.namespace, request.delay, request.max_workers)
        
        return {
            "status": "success",
            "message": f"Successfully indexed {len(request.urls)} URLs into {num_chunks} chunks and added to namespace '{request.namespace}'",
            "indexed_count": len(request.urls)
        }
    except Exception as e:
        logging.error(f"Error in index endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Index error: {str(e)}")

# ============================================================
# Widget Customizer Endpoints
# ============================================================

class WidgetGenerateRequest(BaseModel):
    url: str
    namespace: str
    api_base: str

class WidgetCustomizeRequest(BaseModel):
    config: Dict
    instruction: str
    namespace: str
    api_base: str

class WidgetRecolorRequest(BaseModel):
    config: Dict
    url: str
    namespace: str
    api_base: str

@app.post("/widget/generate/stream")
async def widget_generate_stream(request: WidgetGenerateRequest):
    """
    Stream widget generation progress as SSE.
    Steps: extract theme → generate config with Gemini → render code.
    """
    async def event_generator():
        try:
            # Step 1: Extract theme
            yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing website theme...'})}\n\n"
            await asyncio.sleep(0)  # yield control

            extractor = ThemeExtractor()
            theme_colors = await extractor.extract_theme(request.url)

            yield f"data: {json.dumps({'type': 'theme', 'colors': theme_colors, 'message': 'Theme colors extracted'})}\n\n"
            await asyncio.sleep(0)

            # Step 2: Generate config with Gemini
            yield f"data: {json.dumps({'type': 'status', 'message': 'Generating themed widget with AI...'})}\n\n"
            await asyncio.sleep(0)

            generator = WidgetConfigGenerator()
            config = generator.generate_theme_config(theme_colors)

            yield f"data: {json.dumps({'type': 'config', 'config': config.model_dump(), 'message': 'Widget theme generated'})}\n\n"
            await asyncio.sleep(0)

            # Step 3: Render code
            yield f"data: {json.dumps({'type': 'status', 'message': 'Rendering widget code...'})}\n\n"
            await asyncio.sleep(0)

            renderer = WidgetCodeRenderer()
            code = renderer.render(config, request.namespace, request.api_base)
            guide = renderer.get_integration_guide()

            yield f"data: {json.dumps({'type': 'complete', 'code': code, 'config': config.model_dump(), 'guide': guide, 'message': 'Widget ready!'})}\n\n"

        except Exception as e:
            logging.error(f"Error in widget generation: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/widget/customize")
def widget_customize(request: WidgetCustomizeRequest):
    """Customize an existing widget config based on user instruction."""
    # Validate instruction
    _, is_safe = PromptGuard.sanitize(request.instruction)
    if not is_safe:
        raise HTTPException(status_code=400, detail="Customization request blocked: unsafe or empty input")

    try:
        current_config = WidgetConfig(**request.config)
        generator = WidgetConfigGenerator()
        new_config = generator.customize_config(current_config, request.instruction)

        renderer = WidgetCodeRenderer()
        code = renderer.render(new_config, request.namespace, request.api_base)

        return {
            "code": code,
            "config": new_config.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error in widget customization: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Customization error: {str(e)}")

@app.post("/widget/recolor")
async def widget_recolor(request: WidgetRecolorRequest):
    """Generate a new color scheme for an existing widget, compatible with the website theme."""
    try:
        current_config = WidgetConfig(**request.config)

        extractor = ThemeExtractor()
        theme_colors = await extractor.extract_theme(request.url)

        generator = WidgetConfigGenerator()
        new_config = generator.recolor_config(current_config, theme_colors)

        renderer = WidgetCodeRenderer()
        code = renderer.render(new_config, request.namespace, request.api_base)

        return {
            "code": code,
            "config": new_config.model_dump(),
        }
    except Exception as e:
        logging.error(f"Error in widget recolor: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recolor error: {str(e)}")


# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}