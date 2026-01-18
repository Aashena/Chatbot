import pytest
from mycrawler import crawl_domain, DEFAULT_DELAY
import time


class TestCrawlDomain:
    """Test suite for crawl_domain function with real HTTP requests."""
    
    def test_limited_number_of_urls(self):
        """
        Test that crawl_domain respects the max_num_urls limit.
        
        Input:
            - domain_input = "ualberta.ca"
            - max_num_urls = 5
        
        Verification:
            - Should return exactly 5 distinct URLs
        """
        domain_input = "ualberta.ca"
        max_num_urls = 5
        
        # Add a small delay to be polite to the server
        # time.sleep(1)
        
        result, delay, max_workers = crawl_domain(
            domain_input=domain_input,
            respect_robots=True,
            max_workers=5,
            max_num_urls=max_num_urls
        )
        
        # Verify max workers:
        assert max_workers==5

        # Verify delay
        assert delay==DEFAULT_DELAY

        # Verify results
        assert isinstance(result, set), "Result should be a set"
        assert len(result) == max_num_urls, f"Expected {max_num_urls} URLs, got {len(result)}"
        
        # Verify all URLs are distinct (set property ensures this, but explicit check)
        assert len(result) == len(list(result)), "All URLs should be distinct"
        
        # Verify all URLs belong to the domain
        for url in result:
            assert "ualberta.ca" in url, f"URL {url} does not belong to ualberta.ca domain"
    
    def test_sub_urls_single_page(self):
        """
        Test that crawl_domain returns only one URL when given a specific page URL.
        
        Input:
            - domain_input = "github.com/Aashena/Chatbot/blob/main/Dockerfile"
        
        Verification:
            - Should return only one URL (the page itself)
        """
        domain_input = "github.com/Aashena/Chatbot/blob/main/Dockerfile"
        
        # Add a small delay to be polite to the server
        # time.sleep(1)
        
        result, delay, max_workers = crawl_domain(
            domain_input=domain_input,
            respect_robots=True,
            max_workers=5,
            max_num_urls=100  # Set higher limit to ensure we're not hitting the limit
        )
        
        # Verify max workers
        assert max_workers==5

        # Verify delay
        assert delay==DEFAULT_DELAY
    
        # Verify results
        assert isinstance(result, set), "Result should be a set"
        assert len(result) == 1, f"Expected 1 URL, got {len(result)}"
        
        # Verify the URL is the one we started with (or normalized version)
        result_url = list(result)[0]
        assert "github.com" in result_url, "URL should belong to github.com domain"
        assert "/Aashena/Chatbot" in result_url, "URL should contain the repository path"

