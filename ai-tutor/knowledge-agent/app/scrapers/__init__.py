"""网页抓取"""
from .trafilatura_scraper import scrape_with_trafilatura
from .jina_scraper import scrape_with_jina

__all__ = ["scrape_with_trafilatura", "scrape_with_jina"]
