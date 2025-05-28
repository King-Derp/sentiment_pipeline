# Specialized Scrapers

> **Note on Deprecation**: The Deep Historical and Hybrid Scrapers mentioned in this document are deprecated and no longer maintained. The rest of the document remains relevant for active implementations.

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

### ⚠️ 2. Deep Historical Scraper (Deprecated)

> **Deprecation Notice**: This scraper is no longer maintained. The functionality has been consolidated into the Targeted Historical Scraper.

The `DeepHistoricalScraper` was designed to employ a more granular approach by splitting the historical timeline into small windows, allowing for more thorough data collection.

#### Key Features (Historical Reference):

- **Monthly Time Windows**: Broke down years into monthly chunks
- **Comprehensive Coverage**: Was more likely to find submissions that might be missed by broader searches
- **Pagination Support**: Retrieved up to 1000 submissions per time window when available

#### Historical Usage:

```bash
# No longer functional
python -m reddit_scraper.cli scraper deep
```

### ⚠️ 3. Hybrid Scraper (Deprecated)

> **Deprecation Notice**: This scraper is no longer maintained. The functionality has been consolidated into the Targeted Historical Scraper.

The `HybridScraper` was designed to combine aspects of both targeted and deep historical scraping approaches.

#### Key Features (Historical Reference):

- **Dual Search Strategy**: Used both targeted search terms and time-based windows
- **Flexible Time Ranges**: Could be configured to search by year, month, or custom date ranges
- **Pagination Support**: Retrieved up to 1000 submissions per search when available

#### Historical Usage:

```bash
# No longer functional
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
