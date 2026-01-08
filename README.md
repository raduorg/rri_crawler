# RRI Aromanian Section Crawler

A web crawler for extracting articles from the Radio Romania International (RRI) Aromanian language section (https://www.rri.ro/ro_ar).

## Features

- **Complete Coverage**: Crawls all categories and subcategories of the Aromanian section
- **Article Extraction**: Extracts title, content, author, date, images, and audio links
- **Audio Support**: Captures both direct audio URLs and SoundCloud embed links
- **Pagination Handling**: Automatically follows pagination to get all articles
- **Resumable Crawling**: Saves progress and can resume from where it left off
- **Rate Limiting**: Respects the website by adding delays between requests
- **JSON Output**: Saves articles in a structured JSON format

## Categories Crawled

- **Actualitati** (News)
  - Hăbărli (News)
  - Eveniment Top (Top Events)
  - Focus
- **Teatru armânescu** (Aromanian Theater)
  - Colinde armâneşti (Aromanian Carols)
  - Umor armânesc (Aromanian Humor)
- **Rubriţi di cafi stâmână** (Weekly Columns)
  - Pro Memoria
  - Carnet cultural (Cultural Notes)
  - Radio-Priimnare (Radio Reception)
- **Cultură şi adeţ armâneşti** (Aromanian Culture and Customs)
  - Scriitori armân'i (Aromanian Writers)
  - Pirmithi (Stories)
  - Portreti (Portraits)
  - Oaspiţ la microfonlu RRI (RRI Microphone Guests)
  - Grai (Language)
  - Agenda armânească (Aromanian Agenda)
- **Informaţii ti noi** (Information About Us)
  - Istoric RRI (RRI History)
  - Secția Aromână (Aromanian Section)
  - Premii (Awards)
- **ASCULTAŢ LA CĂFTARI** (Listen On Demand)

## Installation

1. Make sure you have Python 3.8+ installed
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Crawl all categories:

```bash
python rri_crawler.py
```

### Options

```bash
# Specify output directory
python rri_crawler.py --output /path/to/output

# Limit pages per category
python rri_crawler.py --max-pages 50

# Crawl specific category only
python rri_crawler.py --category /ro_ar/ascultat-la-caftari

# Show statistics only (no crawling)
python rri_crawler.py --stats
```

## Output Format

Articles are saved to `output/articles.json` with the following structure:

```json
[
  {
    "url": "https://www.rri.ro/ro_ar/...",
    "title": "Article Title",
    "content": "Full article text...",
    "summary": "Article summary or first 500 chars...",
    "date": "2025-12-16",
    "author": "Author Name",
    "category": "category-slug",
    "image_url": "https://www.rri.ro/wp-content/...",
    "audio_url": null,
    "soundcloud_url": "https://soundcloud.com/...",
    "crawled_at": "2025-12-17T10:30:00"
  }
]
```

### Progress Tracking

Progress is saved to `output/progress.json`:

```json
{
  "visited_urls": ["url1", "url2", ...],
  "failed_urls": ["url3", ...],
  "last_saved": "2025-12-17T10:30:00"
}
```

## Configuration

Edit the following constants in `rri_crawler.py` to customize:

- `REQUEST_DELAY`: Delay between requests (default: 1.0 seconds)
- `OUTPUT_DIR`: Default output directory (default: "output")
- `CATEGORIES`: List of categories to crawl

## Logging

Logs are written to both console and `crawler.log` file.

## Notes

- The crawler respects rate limits with a 1-second delay between requests
- Progress is saved every 10 articles and after each category
- Failed URLs are tracked and can be retried later
- Existing articles are not re-downloaded on subsequent runs

## License

MIT License
