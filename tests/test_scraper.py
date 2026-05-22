from unittest.mock import MagicMock, patch
import pytest
import requests
from vc_vetter.config import Settings
from vc_vetter.scraper import VCWebScraper

def test_scraper_fetch_page_success():
    """Verifies that _fetch_page successfully extracts text, strips boilerplate, and gathers internal links."""
    scraper = VCWebScraper()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    # HTML containing boilerplate, internal relevant links, and external links
    mock_response.content = b"""
    <html>
        <head><style>body { color: red; }</style></head>
        <body>
            <header>Boilerplate Header</header>
            <nav>Boilerplate Navigation</nav>
            <main>
                <h1>Venture Fund Inc</h1>
                <p>We invest in Early stage B2B SaaS startups.</p>
                <a href="/thesis">Our Investment Thesis</a>
                <a href="https://externaldomain.com/portfolio">External Site</a>
            </main>
            <footer>Boilerplate Footer</footer>
            <script>console.log('noisy script');</script>
        </body>
    </html>
    """
    
    with patch('requests.get', return_value=mock_response) as mock_get:
        text, links = scraper._fetch_page("https://venturefund.com")
        
        mock_get.assert_called_once_with(
            "https://venturefund.com", 
            headers=scraper.headers, 
            timeout=scraper.settings.scrape_timeout_seconds
        )
        
        # Verify boilerplate elements are stripped
        assert "Boilerplate Header" not in text
        assert "Boilerplate Navigation" not in text
        assert "Boilerplate Footer" not in text
        assert "noisy script" not in text
        
        # Verify meaningful text is extracted
        assert "Venture Fund Inc" in text
        assert "We invest in Early stage B2B SaaS startups" in text
        
        # Verify link extraction logic
        # '/thesis' is internal and matches the 'thesis' keyword
        assert "https://venturefund.com/thesis" in links
        # 'externaldomain.com' is not on same domain, should be excluded
        assert "https://externaldomain.com/portfolio" not in links

def test_scraper_fetch_page_http_error():
    """Verifies that requests exceptions are caught and return empty values instead of crashing."""
    scraper = VCWebScraper()
    
    with patch('requests.get', side_effect=requests.exceptions.HTTPError("404 Not Found")):
        text, links = scraper._fetch_page("https://nonexistentvcfund.com")
        assert text == ""
        assert links == []

def test_scraper_crawl_and_scrape_limits():
    """Verifies that crawling stops when max_pages_per_site limit is reached."""
    scraper = VCWebScraper(Settings(max_pages_per_site=2))
    
    page1_text = "Welcome to our homepage."
    page1_links = ["https://venturefund.com/thesis"]
    
    page2_text = "Here is our thesis."
    page2_links = ["https://venturefund.com/portfolio"] # Link 3, shouldn't be crawled
    
    def mock_fetch(url):
        if url == "https://venturefund.com":
            return page1_text, page1_links
        elif url == "https://venturefund.com/thesis":
            return page2_text, page2_links
        return "", []
        
    scraper._fetch_page = MagicMock(side_effect=mock_fetch)
    
    consolidated = scraper.crawl_and_scrape("https://venturefund.com")
    
    # Assert both pages we crawled are present
    assert "Welcome to our homepage" in consolidated
    assert "Here is our thesis" in consolidated
    # Verify we visited exactly 2 pages (the limit)
    assert scraper._fetch_page.call_count == 2
