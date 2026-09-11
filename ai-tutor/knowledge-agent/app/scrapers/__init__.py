"""网页抓取"""

from .jina_scraper import scrape_with_jina
from .trafilatura_scraper import scrape_with_trafilatura

__all__ = ["scrape_with_trafilatura", "scrape_with_jina"]
