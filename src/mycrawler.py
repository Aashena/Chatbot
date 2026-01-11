import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from protego import Protego
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# User-Agent for polite crawling
USER_AGENT = 'Mozilla/5.0 (compatible; MyChatBotIndexing/1.0)'
FROM = 'yadegari@ualberta.ca'
DEFAULT_DELAY = 0.1

def is_valid_url(url):
    """Check if URL is valid and not a fragment or mailto link."""
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme) and parsed.scheme in ['http', 'https']

def get_domain(url):
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc

def is_pdf_url(url):
    """Check if URL points to a PDF file."""
    return url.lower().endswith('.pdf')

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

def extract_urls(url, domain):
    """Extract all URLs from a page that belong to the same domain."""
    urls = set()
    
    # Skip URL extraction for PDF files
    if is_pdf_url(url):
        print(f"  Skipping URL extraction (PDF file)")
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
            if is_valid_url(absolute_url) and get_domain(absolute_url) == domain:
                urls.add(absolute_url)
                
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
    except Exception as e:
        print(f"Error parsing {url}: {e}")
    
    return urls

def crawl_url(url, domain, robots_parser, visited_lock, visited, all_urls_lock, all_urls):
    """
    Crawl a single URL and return discovered URLs.
    Thread-safe function for concurrent crawling.
    """
    # Check if already visited
    with visited_lock:
        if url in visited:
            return set()
        visited.add(url)
    
    # Check if URL is allowed by robots.txt
    if robots_parser and not robots_parser.can_fetch(url, USER_AGENT.split('/')[0]):
        print(f"⊘ Blocked by robots.txt: {url}")
        return set()
    
    print(f"Crawling: {url}")
    
    # Add to all_urls
    with all_urls_lock:
        all_urls.add(url)
    
    # Extract URLs from current page
    found_urls = extract_urls(url, domain)
    
    print(f"  Found {len(found_urls)} URLs on this page")
    
    return found_urls

def crawl_domain(domain_input, respect_robots=True, max_workers=15, max_num_urls=100):
    """
    Crawl all URLs under a domain starting from start_url using concurrent workers.
    Args:
        domain_input: The domain to crawl
        respect_robots: Whether to check and respect robots.txt (default: True)
        max_workers: Number of concurrent workers (default: 15)
        max_num_urls: Maximum number of URLs to retrieve (default: 100)
    Returns:
        set: All discovered URLs under the domain (up to max_num_urls)
    """
    start_url = 'https://' + domain_input
    # Normalize the starting URL
    start_url = start_url.split('#')[0]
    
    if not is_valid_url(start_url):
        print(f"Invalid URL: {start_url}")
        return set()
    
    domain = get_domain(start_url)
    print(f"Crawling domain: {domain}")
    print(f"Starting from: {start_url}")
    print(f"Using {max_workers} concurrent workers")
    print(f"Maximum URLs to retrieve: {max_num_urls}")
    
    # Check robots.txt
    robots_parser = None
    crawl_delay = DEFAULT_DELAY  # Default delay
    
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
                        crawl_url, url, domain, robots_parser, 
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