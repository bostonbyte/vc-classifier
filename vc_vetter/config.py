import os
from dataclasses import dataclass, field
from typing import List

@dataclass
class Settings:
    """Configuration settings for the VC Vetting Agent.
    
    Loads configuration from environment variables if present, otherwise uses defaults.
    """
    local_llm_model: str = os.getenv("VC_LLM_MODEL", "llama3")
    max_workers: int = int(os.getenv("VC_MAX_WORKERS", "10"))
    max_pages_per_site: int = int(os.getenv("VC_MAX_PAGES", "5"))
    scrape_timeout_seconds: float = float(os.getenv("VC_SCRAPE_TIMEOUT", "15.0"))
    max_content_length: int = int(os.getenv("VC_MAX_CONTENT_LENGTH", "15000"))
    user_agent: str = os.getenv(
        "VC_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    relevant_keywords: List[str] = field(default_factory=lambda: [
        'portfolio', 'investment', 'focus', 'thesis', 'team', 'about', 'approach', 'strategy'
    ])
