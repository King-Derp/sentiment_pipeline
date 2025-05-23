# Specialized Scrapers

## Overview

The Reddit Scraper project includes several specialized scrapers designed for targeted historical data collection. Unlike the default scraper which focuses on maintaining an up-to-date dataset, specialized scrapers use specific strategies to retrieve historical content from Reddit.

## Types of Specialized Scrapers

### 1. Targeted Historical Scraper

The `TargetedHistoricalScraper` focuses on collecting finance-related Reddit submissions by using specific search terms and year-based searches.

#### Key Features:

- **Specific Search Terms**: Uses over 200 finance-related search terms organized by categories like:
  - Market Conditions (recession, bear market, bull market, etc.)
  - Companies (Tesla, Apple, Microsoft, Palantir, etc.)
  - Financial Events (dotcom bubble, great recession, covid crash, etc.)
  - Reddit/Social Media Slang (yolo, tendies, stonks, lambos, etc.)
  - Trading & Investment Terms (options, calls, puts, theta gang, etc.)

- **Year-Based Search**: Searches each subreddit by specific years from 2008 to present

- **Pagination Support**: Retrieves up to 1000 submissions per search query (10 pages of 100 results) when available, maximizing data collection

#### Usage:

```bash
python -m reddit_scraper.cli scraper targeted
```

### 2. Deep Historical Scraper

The `DeepHistoricalScraper` employs a more granular approach by splitting the historical timeline into small windows, allowing for more thorough data collection.

#### Key Features:

- **Monthly Time Windows**: Breaks down years into monthly chunks
- **Comprehensive Coverage**: More likely to find submissions that might be missed by broader searches
- **Pagination Support**: Retrieves up to 1000 submissions per time window when available

#### Usage:

```bash
python -m reddit_scraper.cli scraper deep
```

### 3. Hybrid Historical Scraper

The `HybridHistoricalScraper` combines both targeted and deep approaches for maximum coverage.

#### Key Features:

- **Combined Strategies**: Uses both specific search terms and granular time windows
- **Maximum Coverage**: Offers the most comprehensive historical data collection
- **Pagination Support**: Retrieves up to 1000 submissions per search when available

#### Usage:

```bash
python -m reddit_scraper.cli scraper hybrid
```

## Pagination Implementation

All specialized scrapers now feature pagination support to retrieve more submissions than the default Reddit API limit of 100 results per query:

- Implements batched retrieval using the `after` parameter in Reddit's API
- Collects up to 10 pages (1000 submissions) per search query
- Continues fetching batches as long as the previous batch returned the full 100 results
- Includes proper rate limiting with delays between API calls to avoid hitting rate limits
- Accumulates results from all pages before filtering and processing

## When to Use Specialized Scrapers

- **Initial Data Collection**: When building a dataset from scratch
- **Research Projects**: When researching specific financial events or trends
- **Filling Data Gaps**: When specific historical periods are missing from your dataset
- **Comprehensive Analysis**: When you need the most complete historical record possible

## Example Integration

Specialized scrapers can be easily integrated into custom workflows:

```python
from reddit_scraper.scrapers.targeted_historical_scraper import TargetedHistoricalScraper

async def collect_historical_data():
    scraper = TargetedHistoricalScraper()
    await scraper.execute()
    print(f"Collected {scraper.total_collected} submissions")
```
