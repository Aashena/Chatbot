import nest_asyncio
import re
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from langchain_core.documents import Document
import asyncio
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import UpstashVectorStore
import time

# User-Agent for polite crawling
FROM = 'yadegari@ualberta.ca'
USER_AGENT = f'Mozilla/5.0 (compatible; MyChatBotIndexing/1.0-{FROM})'
MIN_DELAY = 0.1
MAX_WORKERS = 15
BATCH_SIZE = 50

async def load_web_docs_parallel(urls, delay, max_workers):
    browser_config = BrowserConfig(headless=True, verbose=False, 
    extra_args=[f'--User-Agent={USER_AGENT}'] )
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        delay_before_return_html=delay,
        semaphore_count=max_workers,
        excluded_tags=['nav'], # <nav>
        excluded_selector='.nav, .menu, [class^="menu"], [class^="nav"]', #<div class="menu">, starts with nav or starts with menu
        remove_overlay_elements=True
    )

    documents = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Use arun_many for parallel execution
        results = await crawler.arun_many(urls=urls, config=run_config)

        for result in results:
            if result.success:
                # Get the raw markdown
                content = result.markdown.raw_markdown 

                doc = Document(
                    page_content=content,
                    metadata={"source": result.url}
                )
                documents.append(doc)
            else:
                print(f"Error at {result.url}: {result.error_message}")

    return documents

def make_batches(lst , batch_size):
    for i in range(0, len(lst), batch_size):
           yield lst[i:i + batch_size]

def index_pages(urls, namespace, delay=0.1,  max_workers=15):
    #The main function
    delay = max(delay , MIN_DELAY)
    max_workers = min(max_workers, MAX_WORKERS)
    for batch in make_batches(urls, BATCH_SIZE):
        docs = asyncio.run(load_web_docs_parallel(batch, delay, max_workers))
        # Chunk the text (VERY important for RAG)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
        )

        chunks = text_splitter.split_documents(docs)

        vectorstore = UpstashVectorStore(
            embedding=True, # Whether the embedding should be calculated in cloud
            namespace = namespace # Your first namespace
        )

        # Add your existing 'chunks' from your previous code
        vectorstore.add_documents(chunks)
        time.sleep(delay*10)
        
    return True