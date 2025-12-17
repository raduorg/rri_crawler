#!/usr/bin/env python3
"""
RRI Web Crawler

Crawls articles from Radio Romania International's language sections.

Supported sections:
    - ro_ar: Aromanian language section
    - actualitate: Romanian news section

Output structure:
    output_{section}/
    ├── index.json          # Lightweight metadata (url, title, date, filename)
    ├── stats.json          # Crawl statistics
    ├── progress.json       # Resumable crawl state
    └── articles/
        ├── category_12345.json
        └── ...

Usage:
    python rri_crawler.py --section ro_ar
    python rri_crawler.py --section actualitate
    python rri_crawler.py --list-sections
"""

import json
import os
import re
import time
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://www.rri.ro"
ARTICLES_DIR = "articles"
INDEX_FILE = "index.json"
STATS_FILE = "stats.json"
PROGRESS_FILE = "progress.json"
REQUEST_DELAY = 1.0

# Section configurations
SECTIONS = {
    "ro_ar": {
        "name": "Aromanian",
        "path_prefix": "/ro_ar/",
        "category_pattern": r'/ro_ar/([^/]+)',
        "categories": [
            "/ro_ar/actualitati",
            "/ro_ar/actualitati/habarli",
            "/ro_ar/actualitati/eveniment-top-ro_ar",
            "/ro_ar/actualitati/focus",
            "/ro_ar/teatru-armanescu",
            "/ro_ar/teatru-armanescu/colinde-armanesti",
            "/ro_ar/teatru-armanescu/umor-armanesc",
            "/ro_ar/rubriti-di-cafi-stamana",
            "/ro_ar/rubriti-di-cafi-stamana/pro-memoria-ro_ar",
            "/ro_ar/rubriti-di-cafi-stamana/carnet-cultural",
            "/ro_ar/rubriti-di-cafi-stamana/radio-priimnare",
            "/ro_ar/cultura-si-adet-armanesti",
            "/ro_ar/cultura-si-adet-armanesti/scriitori-armani",
            "/ro_ar/cultura-si-adet-armanesti/pirmithi",
            "/ro_ar/cultura-si-adet-armanesti/portreti",
            "/ro_ar/cultura-si-adet-armanesti/oaspit-la-microfonlu-rri",
            "/ro_ar/cultura-si-adet-armanesti/grai",
            "/ro_ar/cultura-si-adet-armanesti/agenda-armaneasca",
            "/ro_ar/informatii-ti-noi",
            "/ro_ar/informatii-ti-noi/istoric-rri",
            "/ro_ar/informatii-ti-noi/sectia-aromana",
            "/ro_ar/informatii-ti-noi/premii",
            "/ro_ar/ascultat-la-caftari",
        ],
    },
    "actualitate": {
        "name": "Romanian News",
        "path_prefix": "/actualitate/",
        "category_pattern": r'/actualitate/([^/]+)',
        "categories": [
            "/actualitate",
            "/actualitate/stiri",
            "/actualitate/alte-stiri",
            "/actualitate/jurnal-romanesc",
            "/actualitate/in-actualitate",
            "/actualitate/alegeri-2024",
            "/actualitate/alerte-si-sfaturi-de-calatorie",
            "/actualitate/anti-fake-news",
            "/actualitate/sport-la-rri",
            "/actualitate/eveniment-top",
            "/actualitate/focus",
        ],
    },
}


@dataclass
class IndexEntry:
    """Lightweight metadata for index.json."""
    url: str
    title: str
    date: Optional[str]
    category: str
    filename: str


@dataclass
class Article:
    """Full article data saved to individual JSON files."""
    url: str
    title: str
    date: Optional[str]
    category: str
    content: str
    audio_url: Optional[str]
    image_urls: list[str] = field(default_factory=list)
    crawled_at: str = ""


class RRICrawler:
    """Crawler for RRI language sections."""

    def __init__(self, section: str = "ro_ar", output_dir: Optional[str] = None):
        # Validate section
        if section not in SECTIONS:
            available = ", ".join(SECTIONS.keys())
            raise ValueError(f"Unknown section '{section}'. Available: {available}")
        
        self.section = section
        self.section_config = SECTIONS[section]
        self.path_prefix = self.section_config["path_prefix"]
        self.category_pattern = self.section_config["category_pattern"]
        self.categories = self.section_config["categories"]
        
        # Output directory
        self.output_dir = output_dir or f"output_{section}"
        self.articles_dir = os.path.join(self.output_dir, ARTICLES_DIR)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        self.index: dict[str, IndexEntry] = {}  # url -> IndexEntry
        self.failed_urls: set[str] = set()
        
        os.makedirs(self.articles_dir, exist_ok=True)
        self._load_state()

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to filename."""
        match = re.search(r'-id(\d+)\.html$', url)
        article_id = match.group(1) if match else url.split('/')[-1].replace('.html', '')
        
        path = urlparse(url).path
        cat_match = re.search(self.category_pattern, path)
        category = cat_match.group(1) if cat_match else "unknown"
        
        return f"{category}_{article_id}.json"

    def _load_state(self):
        """Load index and progress."""
        # Load index
        index_path = os.path.join(self.output_dir, INDEX_FILE)
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    for item in json.load(f):
                        self.index[item['url']] = IndexEntry(**item)
                logger.info(f"Loaded index: {len(self.index)} articles")
            except Exception as e:
                logger.warning(f"Could not load index: {e}")

        # Load progress (failed URLs)
        progress_path = os.path.join(self.output_dir, PROGRESS_FILE)
        if os.path.exists(progress_path):
            try:
                with open(progress_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.failed_urls = set(data.get('failed_urls', []))
                logger.info(f"Loaded progress: {len(self.failed_urls)} failed")
            except Exception as e:
                logger.warning(f"Could not load progress: {e}")

    def _save_index(self):
        """Save lightweight index."""
        index_path = os.path.join(self.output_dir, INDEX_FILE)
        data = [asdict(entry) for entry in self.index.values()]
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_progress(self):
        """Save failed URLs for retry."""
        progress_path = os.path.join(self.output_dir, PROGRESS_FILE)
        with open(progress_path, 'w', encoding='utf-8') as f:
            json.dump({
                'failed_urls': list(self.failed_urls),
                'last_saved': datetime.now().isoformat()
            }, f, ensure_ascii=False)

    def _save_stats(self):
        """Save crawl statistics."""
        stats_path = os.path.join(self.output_dir, STATS_FILE)
        categories = {}
        for entry in self.index.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1
        
        stats = {
            'total_articles': len(self.index),
            'failed_urls': len(self.failed_urls),
            'articles_by_category': categories,
            'last_updated': datetime.now().isoformat()
        }
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def _save_article(self, article: Article) -> str:
        """Save article to individual JSON file."""
        filename = self._url_to_filename(article.url)
        filepath = os.path.join(self.articles_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(article), f, indent=2, ensure_ascii=False)
        return filename

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page."""
        try:
            time.sleep(REQUEST_DELAY)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            self.failed_urls.add(url)
            return None

    def _extract_article(self, soup: BeautifulSoup, url: str) -> Article:
        """Extract article content."""
        # Title
        title_elem = soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "Untitled"

        # Date
        date = None
        date_elem = soup.find('time', datetime=True)
        if date_elem:
            date = date_elem.get('datetime')
        else:
            for selector in ['.date', '.post-date', '.article-date']:
                elem = soup.select_one(selector)
                if elem:
                    date = elem.get_text(strip=True)
                    break

        # Category
        path = urlparse(url).path
        cat_match = re.search(self.category_pattern, path)
        category = cat_match.group(1) if cat_match else "unknown"

        # Content
        content = ""
        for selector in ['article .content', '.article-content', '.article-body', 
                         '.post-content', 'article p', '.entry-content']:
            elems = soup.select(selector)
            if elems:
                content = '\n\n'.join(e.get_text(strip=True) for e in elems if e.get_text(strip=True))
                if content:
                    break
        
        if not content:
            main = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main:
                paragraphs = main.find_all('p')
                content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Audio URL
        audio_url = None
        audio_elem = soup.find('audio', src=True) or soup.find('source', src=True)
        if audio_elem:
            audio_url = urljoin(url, audio_elem.get('src'))
        if not audio_url:
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if '.mp3' in href or '/audio/' in href:
                    audio_url = urljoin(url, href)
                    break

        # Image URLs
        image_urls = []
        article_elem = soup.find('article') or soup.find('main')
        if article_elem:
            for img in article_elem.find_all('img', src=True):
                src = img.get('src')
                if src and not any(x in src.lower() for x in ['logo', 'icon', 'avatar', 'banner']):
                    image_urls.append(urljoin(url, src))

        return Article(
            url=url,
            title=title,
            date=date,
            category=category,
            content=content,
            audio_url=audio_url,
            image_urls=image_urls[:5],
            crawled_at=datetime.now().isoformat()
        )

    def _is_article_url(self, url: str) -> bool:
        return bool(re.search(r'-id\d+\.html$', url))

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> tuple[list[str], list[str]]:
        """Extract article and pagination links."""
        articles, pages = [], []
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            # Check if URL belongs to this section
            if self.path_prefix not in full_url:
                continue
            if self._is_article_url(full_url):
                articles.append(full_url)
            elif 'page=' in href or '/page/' in href:
                pages.append(full_url)
        return list(set(articles)), list(set(pages))

    def crawl_category(self, category_url: str, max_pages: int = 100):
        """Crawl a category."""
        full_url = urljoin(BASE_URL, category_url)
        logger.info(f"Crawling: {full_url}")
        
        pages_to_visit = [full_url]
        visited_pages = set()
        new_articles = 0
        
        while pages_to_visit and len(visited_pages) < max_pages:
            page_url = pages_to_visit.pop(0)
            if page_url in visited_pages:
                continue
            
            visited_pages.add(page_url)
            soup = self._fetch_page(page_url)
            if not soup:
                continue
            
            article_links, page_links = self._extract_links(soup, page_url)
            logger.info(f"Found {len(article_links)} articles on {page_url}")
            
            for article_url in article_links:
                # Skip if already indexed
                if article_url in self.index:
                    continue
                
                logger.info(f"Crawling: {article_url}")
                article_soup = self._fetch_page(article_url)
                if not article_soup:
                    continue
                
                # Extract and save article
                article = self._extract_article(article_soup, article_url)
                filename = self._save_article(article)
                
                # Add to index
                self.index[article_url] = IndexEntry(
                    url=article_url,
                    title=article.title,
                    date=article.date,
                    category=article.category,
                    filename=filename
                )
                new_articles += 1
                logger.info(f"Saved: {article.title[:50]}...")
                
                # Periodic save (index only, articles already saved)
                if new_articles % 10 == 0:
                    self._save_index()
                    self._save_progress()
            
            for link in page_links:
                if link not in visited_pages:
                    pages_to_visit.append(link)
        
        return new_articles

    def crawl_all(self, max_pages_per_category: int = 100):
        """Crawl all categories for this section."""
        logger.info(f"Starting full crawl of {self.section} ({self.section_config['name']})")
        total_new = 0
        
        for category in self.categories:
            try:
                new = self.crawl_category(category, max_pages_per_category)
                total_new += new
            except Exception as e:
                logger.error(f"Error in {category}: {e}")
            
            # Save after each category
            self._save_index()
            self._save_progress()
            self._save_stats()
        
        logger.info(f"Done. New: {total_new}, Total: {len(self.index)}")
        return self.index

    def get_stats(self) -> dict:
        """Get current statistics."""
        categories = {}
        for entry in self.index.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1
        return {
            'section': self.section,
            'section_name': self.section_config['name'],
            'total': len(self.index),
            'failed': len(self.failed_urls),
            'by_category': categories,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='RRI Web Crawler')
    parser.add_argument('--section', '-S', default='ro_ar',
                        choices=list(SECTIONS.keys()),
                        help='Language section to crawl')
    parser.add_argument('--output', '-o', help='Output directory (default: output_{section})')
    parser.add_argument('--max-pages', '-m', type=int, default=100)
    parser.add_argument('--category', '-c', help='Crawl specific category only')
    parser.add_argument('--stats', '-s', action='store_true', help='Show stats only')
    parser.add_argument('--list-sections', '-l', action='store_true', help='List available sections')
    args = parser.parse_args()
    
    if args.list_sections:
        print("Available sections:")
        for key, config in SECTIONS.items():
            print(f"  {key}: {config['name']}")
            print(f"    Categories: {len(config['categories'])}")
        return
    
    crawler = RRICrawler(section=args.section, output_dir=args.output)
    
    if args.stats:
        print(json.dumps(crawler.get_stats(), indent=2))
        return
    
    if args.category:
        crawler.crawl_category(args.category, args.max_pages)
        crawler._save_index()
        crawler._save_progress()
        crawler._save_stats()
    else:
        crawler.crawl_all(args.max_pages)
    
    print(json.dumps(crawler.get_stats(), indent=2))


if __name__ == '__main__':
    main()
