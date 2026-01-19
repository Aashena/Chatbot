import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from protego import Protego
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import asyncio
from queue import Queue, Empty

# User-Agent for polite crawling
USER_AGENT = 'Mozilla/5.0 (compatible; MyChatBotIndexing/1.0)'
FROM = 'yadegari@ualberta.ca'
DEFAULT_DELAY = 1
MAX_NUM_URLS = 1000
MAX_WORKERS = 5

def is_valid_url(url):
    """Check if URL is valid and not a fragment or mailto link."""
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme) and parsed.scheme in ['http', 'https']

def get_domain(url):
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc

def get_base_path(url):
    """Extract the base path from URL (domain + path without query/fragment)."""
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip('/')

def is_under_base_path(url, base_path):
    """Check if URL is under the base path."""
    url_path = get_base_path(url)
    return url_path.startswith(base_path)

def is_pdf_url(url):
    """Check if URL points to a PDF file."""
    return url.lower().endswith('.pdf')

def is_image_url(url):
    """Check if URL points to an image file."""
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.ico', '.tiff', '.tif')
    return url.lower().endswith(image_extensions)

def get_robots_parser(domain_url):
    """
    Get and parse robots.txt for the domain using Protego.
    Returns None if robots.txt doesn't exist (which means crawling is allowed).
    """
    parsed = urlparse(domain_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    try:
        headers = {'User-Agent': USER_AGENT,
        "From": FROM}
        response = requests.get(robots_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse robots.txt content with Protego
        rp = Protego.parse(response.text)
        print(f"✓ Found robots.txt at {robots_url}")
        
        # Try to get crawl delay
        crawl_delay = rp.crawl_delay(USER_AGENT.split('/')[0])
        if not crawl_delay:
            crawl_delay = rp.crawl_delay("*")
        if crawl_delay:
            print(f"  Crawl delay specified: {crawl_delay} seconds")
        
        return rp, crawl_delay
    except requests.exceptions.RequestException as e:
        print('exception while checking robots.txt:', e)
        print(f"✓ No robots.txt found (crawling allowed)")
        return None, None
    except Exception as e:
        print(f"⚠ Error parsing robots.txt: {e}")
        return None, None

def extract_urls(url, domain, base_path=None):
    """Extract all URLs from a page that belong to the same domain and optionally under base_path."""
    urls = set()
    
    # Skip URL extraction for PDF and image files
    if is_pdf_url(url) or is_image_url(url):
        print(f"  Skipping URL extraction (PDF or image file)")
        return urls
    
    try:
        headers = {'User-Agent': USER_AGENT,
        "From": FROM}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all anchor tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert relative URLs to absolute
            absolute_url = urljoin(url, href)
            
            # Remove fragments (e.g., #section)
            absolute_url = absolute_url.split('#')[0]
            
            # Check if URL is valid and belongs to the same domain
            # Also exclude image URLs
            if (is_valid_url(absolute_url) and 
                get_domain(absolute_url) == domain and 
                not is_image_url(absolute_url)):
                # If base_path is specified, only include URLs under that path
                if base_path is None or is_under_base_path(absolute_url, base_path):
                    urls.add(absolute_url)
                
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
    except Exception as e:
        print(f"Error parsing {url}: {e}")
    
    return urls

def crawl_url(url, domain, base_path, robots_parser, visited_lock, visited, all_urls_lock, all_urls, event_queue=None, controller=None):
    """
    Crawl a single URL and return discovered URLs.
    Thread-safe function for concurrent crawling.
    Optionally sends events to a queue for streaming.
    """
    # Check if we should stop
    if controller and controller.is_stopped():
        return set()
    
    # Check if already visited
    with visited_lock:
        if url in visited:
            return set()
        visited.add(url)
    
    # Skip image URLs entirely
    if is_image_url(url):
        print(f"⊘ Skipping image URL: {url}")
        return set()
    
    # Check if URL is allowed by robots.txt
    if robots_parser and not robots_parser.can_fetch(url, USER_AGENT.split('/')[0]):
        print(f"⊘ Blocked by robots.txt: {url}")
        return set()
    
    print(f"Crawling: {url}")
    
    # Try to fetch the URL and check for 404
    try:
        headers = {'User-Agent': USER_AGENT, "From": FROM}
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        
        # Check for 404 or other error status codes
        if response.status_code == 404:
            print(f"  ⚠ 404 Not Found - skipping: {url}")
            return set()
        elif response.status_code >= 400:
            print(f"  ⚠ HTTP {response.status_code} - skipping: {url}")
            return set()
            
    except requests.exceptions.RequestException as e:
        print(f"  Error checking URL {url}: {e}")
        return set()
    
    # Add to all_urls only if it's valid and not a 404
    with all_urls_lock:
        all_urls.add(url)
        total_count = len(all_urls)
        
        # Send URL event if event_queue is provided
        if event_queue is not None:
            event_queue.put({
                "type": "url",
                "url": url,
                "total_discovered": total_count
            })
    
    # Extract URLs from current page
    found_urls = extract_urls(url, domain, base_path)
    
    print(f"  Found {len(found_urls)} URLs on this page")
    
    return found_urls

class CrawlController:
    """Controller to manage crawl state and allow stopping."""
    def __init__(self):
        self.should_stop = False
        self.lock = threading.Lock()
    
    def stop(self):
        with self.lock:
            self.should_stop = True
    
    def is_stopped(self):
        with self.lock:
            return self.should_stop

async def crawl_domain_streaming(domain_input, respect_robots=True, max_workers=MAX_WORKERS, max_num_urls=MAX_NUM_URLS, controller=None):
    """
    Crawl domain and yield events as URLs are discovered.
    
    Args:
        domain_input: Domain to crawl
        respect_robots: Whether to respect robots.txt
        max_workers: Number of concurrent workers
        max_num_urls: Maximum URLs to discover
        controller: CrawlController instance for stopping the crawl
    
    Yields events with structure:
    {
        "type": "url" | "progress" | "config" | "error",
        "url": str (for type="url"),
        "total_discovered": int,
        "to_visit": int (for type="progress"),
        "visited": int (for type="progress"),
        "crawl_delay": float (for type="config"),
        "max_workers": int (for type="config")
    }
    """
    start_url = 'https://' + domain_input
    start_url = start_url.split('#')[0]
    
    if not is_valid_url(start_url):
        yield {
            "type": "error",
            "message": f"Invalid URL: {start_url}"
        }
        return
    
    domain = get_domain(start_url)
    base_path = get_base_path(start_url)
    
    print(f"Crawling domain: {domain}")
    print(f"Base path restriction: {base_path}")
    print(f"Starting from: {start_url}")
    
    # Check robots.txt
    robots_parser = None
    crawl_delay = DEFAULT_DELAY
    
    if respect_robots:
        print("\nChecking robots.txt...")
        robots_parser, robots_delay = get_robots_parser(start_url)
        if robots_delay:
            crawl_delay = robots_delay
            if crawl_delay > 1:
                adjusted_workers = max(1, min(max_workers, int(5 / crawl_delay)))
                print(f"  Adjusting workers to {adjusted_workers} due to crawl delay")
                max_workers = adjusted_workers
    
    # Send initial configuration
    yield {
        "type": "config",
        "crawl_delay": crawl_delay,
        "max_workers": max_workers,
        "domain": domain,
        "base_path": base_path
    }
    
    # Create controller if not provided
    if controller is None:
        controller = CrawlController()
    
    # Thread-safe data structures
    visited = set()
    visited_lock = threading.Lock()
    all_urls = set()
    all_urls_lock = threading.Lock()
    to_visit = {start_url}
    
    # Queue for streaming events from threads
    event_queue = Queue()
    
    def run_crawl():
        """Run the crawl in a separate thread."""
        last_progress_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while to_visit and len(all_urls) < max_num_urls and not controller.is_stopped():
                futures = {}
                batch = set()
                
                remaining_slots = max_num_urls - len(all_urls)
                batch_size = min(max_workers, remaining_slots, len(to_visit))
                
                for _ in range(batch_size):
                    if to_visit and not controller.is_stopped():
                        url = to_visit.pop()
                        batch.add(url)
                        future = executor.submit(
                            crawl_url, url, domain, base_path, robots_parser,
                            visited_lock, visited, all_urls_lock, all_urls, event_queue, controller
                        )
                        futures[future] = url
                
                if not futures:
                    break
                
                new_urls = set()
                for future in as_completed(futures):
                    if controller.is_stopped():
                        break
                    try:
                        found_urls = future.result()
                        new_urls.update(found_urls)
                    except Exception as e:
                        url = futures[future]
                        print(f"Error processing {url}: {e}")
                        event_queue.put({
                            "type": "error",
                            "url": url,
                            "message": str(e)
                        })
                    
                    if len(all_urls) >= max_num_urls:
                        break
                
                if len(all_urls) < max_num_urls and not controller.is_stopped():
                    with visited_lock:
                        to_add = new_urls - visited
                        to_visit.update(to_add)
                
                # Send progress update
                with all_urls_lock:
                    event_queue.put({
                        "type": "progress",
                        "total_discovered": len(all_urls),
                        "to_visit": len(to_visit),
                        "visited": len(visited)
                    })
                    last_progress_time = time.time()
                
                print(f"  Total discovered: {len(all_urls)}, To visit: {len(to_visit)}\n")
                
                # Send heartbeat if no progress for 15 seconds
                current_time = time.time()
                if current_time - last_progress_time > 15:
                    with all_urls_lock:
                        event_queue.put({
                            "type": "heartbeat",
                            "total_discovered": len(all_urls),
                            "to_visit": len(to_visit),
                            "visited": len(visited)
                        })
                    last_progress_time = current_time
                
                if len(all_urls) >= max_num_urls:
                    print(f"Reached maximum URL limit of {max_num_urls}")
                    break
                
                if controller.is_stopped():
                    print("Crawl stopped by user")
                    break
                
                time.sleep(crawl_delay)
        
        # Signal completion
        event_queue.put(None)
    
    # Start crawling in a background thread
    crawl_thread = threading.Thread(target=run_crawl, daemon=True)
    crawl_thread.start()
    
    # Stream events as they come in
    while True:
        try:
            # Use get with timeout to allow checking thread status
            event = await asyncio.get_event_loop().run_in_executor(
                None, event_queue.get, True, 1.0  # 1 second timeout
            )
            
            if event is None:  # Completion signal
                break
            
            yield event
            
        except Empty:
            # Check if thread is still alive
            if not crawl_thread.is_alive():
                # Thread finished, drain remaining events
                try:
                    while True:
                        event = event_queue.get_nowait()
                        if event is None:
                            break
                        yield event
                except Empty:
                    pass
                break
            
            # Thread still running, check for stop condition
            if controller.is_stopped():
                # Drain any remaining events
                try:
                    while True:
                        event = event_queue.get_nowait()
                        if event is None:
                            break
                        yield event
                except Empty:
                    pass
                break
            continue
        except Exception as e:
            print(f"Error in event stream: {e}")
            break
    
    # Wait for thread to finish
    crawl_thread.join(timeout=5)

def crawl_domain(domain_input, respect_robots=True, max_workers=MAX_WORKERS, max_num_urls=MAX_NUM_URLS):
    """
    Original non-streaming crawl function (kept for backward compatibility).
    """
    start_url = 'https://' + domain_input
    # Normalize the starting URL
    start_url = start_url.split('#')[0]
    
    if not is_valid_url(start_url):
        print(f"Invalid URL: {start_url}")
        return set(), DEFAULT_DELAY, max_workers
    
    domain = get_domain(start_url)
    base_path = get_base_path(start_url)
    
    print(f"Crawling domain: {domain}")
    print(f"Base path restriction: {base_path}")
    print(f"Starting from: {start_url}")
    print(f"Using {max_workers} concurrent workers")
    print(f"Maximum URLs to retrieve: {max_num_urls}")
    
    # Check robots.txt
    robots_parser = None
    crawl_delay = DEFAULT_DELAY
    
    if respect_robots:
        print("\nChecking robots.txt...")
        robots_parser, robots_delay = get_robots_parser(start_url)
        if robots_delay:
            crawl_delay = robots_delay
            # Adjust workers based on crawl delay to respect rate limits
            if crawl_delay > 1:
                adjusted_workers = max(1, min(max_workers, int(5 / crawl_delay)))
                print(f"  Adjusting workers to {adjusted_workers} due to crawl delay")
                max_workers = adjusted_workers
        print(f"Using crawl delay: {crawl_delay} seconds per worker\n")
    
    # Thread-safe data structures
    visited = set()
    visited_lock = threading.Lock()
    all_urls = set()
    all_urls_lock = threading.Lock()
    to_visit = {start_url}
    
    # Use ThreadPoolExecutor for concurrent crawling
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while to_visit and len(all_urls) < max_num_urls:
            # Submit batch of URLs to workers
            futures = {}
            batch = set()
            
            # Get up to max_workers URLs to process, but don't exceed max_num_urls
            remaining_slots = max_num_urls - len(all_urls)
            batch_size = min(max_workers, remaining_slots, len(to_visit))
            
            for _ in range(batch_size):
                if to_visit:
                    url = to_visit.pop()
                    batch.add(url)
                    future = executor.submit(
                        crawl_url, url, domain, base_path, robots_parser,
                        visited_lock, visited, all_urls_lock, all_urls
                    )
                    futures[future] = url
            
            if not futures:
                break
            
            # Wait for all futures to complete and collect new URLs
            new_urls = set()
            for future in as_completed(futures):
                try:
                    found_urls = future.result()
                    new_urls.update(found_urls)
                except Exception as e:
                    url = futures[future]
                    print(f"Error processing {url}: {e}")
                
                # Check if we've reached the limit
                if len(all_urls) >= max_num_urls:
                    break
            
            # Add newly discovered URLs to the queue (only if we haven't reached the limit)
            if len(all_urls) < max_num_urls:
                with visited_lock:
                    to_add = new_urls - visited
                    to_visit.update(to_add)
            
            print(f"  Total discovered: {len(all_urls)}, To visit: {len(to_visit)}\n")
            
            # Stop if we've reached the maximum
            if len(all_urls) >= max_num_urls:
                print(f"Reached maximum URL limit of {max_num_urls}")
                break
            
            # Be polite - respect crawl delay between batches
            time.sleep(crawl_delay)
    
    return all_urls, crawl_delay, max_workers