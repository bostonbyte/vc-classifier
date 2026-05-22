import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
from vc_vetter.config import Settings
from typing import Tuple, List, Set

logger = logging.getLogger(__name__)

class VCWebScraper:
    """A crawler and text extractor for venture capital websites.
    
    Crawls internal links that match investment-related keywords up to a set limit.
    """
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.headers = {"User-Agent": self.settings.user_agent}

    def _fetch_page(self, url: str) -> Tuple[str, List[str]]:
        """Fetches page content, extracting clean text and internal absolute links.
        
        Performs request and parses links in a single pass for optimal performance.
        
        Args:
            url: The absolute URL of the page to fetch.
            
        Returns:
            A tuple of (clean_text, internal_links_list).
        """
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.settings.scrape_timeout_seconds
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract internal links before stripping structure
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                text_content = a_tag.get_text()
                links.append((href, text_content))
                
            # Decompose boilerplate layout elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
                element.decompose()
                
            text = soup.get_text(separator=' ', strip=True)
            clean_text = ' '.join(text.split())
            
            # Resolve relative links and filter for same-domain relevance
            resolved_links = []
            parsed_base = urlparse(url)
            base_domain = parsed_base.netloc
            
            for href, text_content in links:
                full_url = urljoin(url, href)
                parsed_full = urlparse(full_url)
                
                if parsed_full.netloc == base_domain:
                    # Filter internal links using keywords
                    if any(keyword in full_url.lower() or keyword in text_content.lower() 
                           for keyword in self.settings.relevant_keywords):
                        # Remove fragment identifiers to prevent duplicate pages
                        full_url_clean = full_url.split('#')[0]
                        resolved_links.append(full_url_clean)
                        
            return clean_text, resolved_links
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request failed for {url}: {e}")
            return "", []

    def crawl_and_scrape(self, base_url: str) -> str:
        """Crawls a VC site starting from base_url, gathering up to max_pages_per_site.
        
        Consolidates text contents for analysis.
        
        Args:
            base_url: Root website URL for the venture capital fund.
            
        Returns:
            Consolidated text string from crawled pages, truncated to max_content_length.
        """
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url

        visited_urls: Set[str] = set()
        urls_to_scrape: List[str] = [base_url]
        consolidated_chunks: List[str] = []
        
        while urls_to_scrape and len(visited_urls) < self.settings.max_pages_per_site:
            url = urls_to_scrape.pop(0)
            if url in visited_urls:
                continue
                
            visited_urls.add(url)
            logger.info(f"Crawling URL: {url}")
            
            clean_text, internal_links = self._fetch_page(url)
            if clean_text:
                consolidated_chunks.append(f"--- CONTENT FROM {url} ---\n{clean_text}")
                
            for link in internal_links:
                if link not in visited_urls:
                    urls_to_scrape.append(link)
                    
        consolidated = "\n\n".join(consolidated_chunks)
        return consolidated[:self.settings.max_content_length]
