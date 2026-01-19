import re
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from langchain_core.documents import Document
import asyncio
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import UpstashVectorStore
from upstash_vector import Index
import time
import hashlib

# User-Agent for polite crawling
FROM = 'yadegari@ualberta.ca'
USER_AGENT = f'Mozilla/5.0 (compatible; MyChatBotIndexing/1.0-{FROM})'
MIN_DELAY = 1
MAX_WORKERS = 2
BATCH_SIZE = 50
CHUNK_SIZE=1000
CHUNK_OVERLAP=100

def get_existing_urls(namespace):
    """Get all existing URLs from the vector database for a given namespace."""
    try:
        index = Index.from_env()
        #index.reset(namespace=namespace) #This line should be deleted for production.
        stats = index.info()
        
        # Check if namespace exists
        if namespace not in stats.namespaces:
            return set()
        
        vector_count = stats.namespaces[namespace].vector_count
        
        if vector_count == 0:
            return set()
        
        existing_urls = set()
        cursor = "0"
        batch_size = 1000  # Fetch in batches of 1000
        
        while True:
            res = index.range(
                cursor=cursor,
                limit=batch_size,
                include_metadata=True,
                include_vectors=False,
                namespace=namespace
            )
            
            # Extract URLs from metadata
            for vector in res.vectors:
                if vector.metadata and 'source' in vector.metadata:
                    existing_urls.add(vector.metadata['source'])
            
            # Check if we've fetched all vectors
            if res.next_cursor == "":
                break
            
            cursor = res.next_cursor
        
        return existing_urls
    
    except Exception as e:
        print(f"Error fetching existing URLs: {e}")
        return set()

def compute_chunk_hash(content):
    """Compute a hash of the chunk content for deduplication."""
    # Normalize the content: strip whitespace and convert to lowercase
    normalized = content.strip().lower()
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()

def remove_duplicate_chunks(chunks):
    """Remove duplicate chunks based on content hash."""
    seen_hashes = set()
    unique_chunks = []
    duplicates_removed = 0
    
    for chunk in chunks:
        chunk_hash = compute_chunk_hash(chunk.page_content)
        
        if chunk_hash not in seen_hashes:
            seen_hashes.add(chunk_hash)
            unique_chunks.append(chunk)
        else:
            duplicates_removed += 1
    
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicate chunks")
    
    return unique_chunks

async def load_web_docs_parallel(urls, delay, max_workers):
    browser_config = BrowserConfig(headless=True, verbose=False, 
    extra_args=[f'--user-agent={USER_AGENT}'] )
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        delay_before_return_html=delay,
        semaphore_count=max_workers,
        excluded_tags=['nav'], # <nav>
        excluded_selector='.nav, .menu, [class^="menu"], [class^="nav"]', #<div class="menu">, starts with nav or starts with menu
        #remove_overlay_elements=True
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

# New streaming version
async def index_pages_streaming(urls, namespace, delay=MIN_DELAY, max_workers=MAX_WORKERS):
    """Async generator that yields progress events during indexing."""
    delay = max(delay, MIN_DELAY)
    max_workers = min(max_workers, MAX_WORKERS)
    
    # Send start event
    yield {
        "type": "start",
        "message": "Starting indexing process",
        "total_urls": len(urls)
    }
    
    # Get existing URLs from the vector database
    print(f"Checking for existing URLs in namespace '{namespace}'...")
    existing_urls = get_existing_urls(namespace)
    print(f"Found {len(existing_urls)} existing URLs in the database")
    
    yield {
        "type": "existing_check",
        "message": f"Found {len(existing_urls)} existing URLs",
        "existing_count": len(existing_urls)
    }
    
    # Filter out URLs that already exist
    urls_to_index = [url for url in urls if url not in existing_urls]
    
    if len(urls_to_index) == 0:
        yield {
            "type": "complete",
            "message": "All URLs are already indexed",
            "total_chunks": 0,
            "urls_processed": 0,
            "urls_skipped": len(urls)
        }
        return
    
    skipped_count = len(urls) - len(urls_to_index)
    print(f"Skipping {skipped_count} duplicate URLs")
    print(f"Indexing {len(urls_to_index)} new URLs")
    
    yield {
        "type": "filter_complete",
        "message": f"Processing {len(urls_to_index)} new URLs (skipped {skipped_count} duplicates)",
        "urls_to_process": len(urls_to_index),
        "urls_skipped": skipped_count
    }
    
    total_num_chunks = 0
    batches = list(make_batches(urls_to_index, BATCH_SIZE))
    total_batches = len(batches)
    
    for batch_idx, batch in enumerate(batches, 1):
        yield {
            "type": "batch_start",
            "message": f"Processing batch {batch_idx} of {total_batches}",
            "batch_number": batch_idx,
            "total_batches": total_batches,
            "batch_size": len(batch)
        }
        
        # Load documents
        docs = await load_web_docs_parallel(batch, delay, max_workers)
        
        if not docs:
            yield {
                "type": "batch_error",
                "message": f"No documents loaded from batch {batch_idx}",
                "batch_number": batch_idx
            }
            continue
        
        yield {
            "type": "docs_loaded",
            "message": f"Loaded {len(docs)} documents from batch {batch_idx}",
            "docs_count": len(docs),
            "batch_number": batch_idx
        }
        
        # Chunk the text (VERY important for RAG)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        chunks = text_splitter.split_documents(docs)
        
        yield {
            "type": "chunking_complete",
            "message": f"Created {len(chunks)} chunks from {len(docs)} documents",
            "chunks_before_dedup": len(chunks),
            "batch_number": batch_idx
        }
        
        # Remove duplicate chunks
        print(f"Total chunks before deduplication: {len(chunks)}")
        chunks = remove_duplicate_chunks(chunks)
        print(f"Unique chunks after deduplication: {len(chunks)}")
        
        yield {
            "type": "deduplication_complete",
            "message": f"Removed duplicates, {len(chunks)} unique chunks remain",
            "unique_chunks": len(chunks),
            "batch_number": batch_idx
        }

        # Add to vector store
        vectorstore = UpstashVectorStore(
            embedding=True, # Whether the embedding should be calculated in cloud
            namespace=namespace # Your first namespace
        )

        # Add your existing 'chunks' from your previous code
        vectorstore.add_documents(chunks)
        await asyncio.sleep(delay*5)
        total_num_chunks += len(chunks)
        
        yield {
            "type": "batch_complete",
            "message": f"Batch {batch_idx}/{total_batches} indexed: {len(chunks)} chunks from {len(docs)} documents",
            "batch_number": batch_idx,
            "total_batches": total_batches,
            "batch_chunks": len(chunks),
            "batch_docs": len(docs),
            "total_chunks_so_far": total_num_chunks
        }
        
        print(f"Indexed batch {batch_idx}/{total_batches}: {len(chunks)} chunks from {len(docs)} documents")
    
    # Send completion event
    yield {
        "type": "complete",
        "message": f"Indexing complete! Total: {total_num_chunks} chunks from {len(urls_to_index)} URLs",
        "total_chunks": total_num_chunks,
        "urls_processed": len(urls_to_index),
        "urls_skipped": skipped_count
    }
    
    print(f"Total chunks indexed: {total_num_chunks}")

# Original synchronous version (kept for backward compatibility)
def index_pages(urls, namespace, delay=MIN_DELAY, max_workers=MAX_WORKERS):
    """Main function to index pages, avoiding duplicates."""
    delay = max(delay, MIN_DELAY)
    max_workers = min(max_workers, MAX_WORKERS)
    
    # Get existing URLs from the vector database
    print(f"Checking for existing URLs in namespace '{namespace}'...")
    existing_urls = get_existing_urls(namespace)
    print(f"Found {len(existing_urls)} existing URLs in the database")
    
    # Filter out URLs that already exist
    urls_to_index = [url for url in urls if url not in existing_urls]
    
    if len(urls_to_index) == 0:
        print("All URLs are already indexed. Nothing to do.")
        return 0
    
    print(f"Skipping {len(urls) - len(urls_to_index)} duplicate URLs")
    print(f"Indexing {len(urls_to_index)} new URLs")
    
    total_num_chunks = 0
    for batch in make_batches(urls_to_index, BATCH_SIZE):
        docs = asyncio.run(load_web_docs_parallel(batch, delay, max_workers))
        
        if not docs:
            continue
        
        # Chunk the text (VERY important for RAG)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        chunks = text_splitter.split_documents(docs)
        
        # Remove duplicate chunks
        print(f"Total chunks before deduplication: {len(chunks)}")
        chunks = remove_duplicate_chunks(chunks)
        print(f"Unique chunks after deduplication: {len(chunks)}")

        vectorstore = UpstashVectorStore(
            embedding=True, # Whether the embedding should be calculated in cloud
            namespace=namespace # Your first namespace
        )

        # Add your existing 'chunks' from your previous code
        vectorstore.add_documents(chunks)
        time.sleep(delay*5)
        total_num_chunks += len(chunks)
        print(f"Indexed batch: {len(chunks)} chunks from {len(docs)} documents")
        
    print(f"Total chunks indexed: {total_num_chunks}")
    return total_num_chunks