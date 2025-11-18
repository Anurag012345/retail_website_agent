# Tavily AI CLI

Simple command-line tool for product research and content extraction:
1. **Search**: pass a query string (e.g., "mobile phone") and get ranked web results.
2. **Extract**: pass specific URLs and get summarized content with product details.
3. **Search Products**: search for products on specific retail websites (Flipkart, Amazon, etc.) and extract detailed product information.

## Prerequisites

- Python 3.10+
- Tavily API key (set as `TAVILY_API_KEY` environment variable or in `.env` file)

## Quick start

```powershell
# from E:\Retail Demo Check
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
notepad .env   # set TAVILY_API_KEY=your_key
```

## Usage Examples

### Case 1: Search products on specific retail website

Search for products only on a specific retailer's website and extract complete product information (title, price, ratings, specifications).

**Flipkart search:**
```powershell
python -m tavily_demo.main search-products --query "best smartphones under 30000" --site flipkart --max-results 5 --extract-top 3
```

**Amazon search:**
```powershell
python -m tavily_demo.main search-products --query "best smartphones under 10000" --site amazon --max-results 5 --extract-top 3
```

**Auto-detect (mention retailer in query):**
```powershell
python -m tavily_demo.main search-products --query "best smartphones under 20000 on Flipkart" --max-results 5 --extract-top 3
```

**Output includes:**
- Product Title
- Price
- Ratings
- Retailer (auto-detected)
- Description

**Supported retailers:**
- Flipkart (`--site flipkart`)
- Amazon (`--site amazon`)
- Myntra (`--site myntra`)
- Ajio (`--site ajio`)
- Snapdeal (`--site snapdeal`)
- Meesho (`--site meesho`)

### Case 2: Extract complete product details from URL

Extract detailed product information from any product page URL. Auto-detects retailer (Amazon, Flipkart, Myntra, Ajio).

**Flipkart product:**
```powershell
python -m tavily_demo.main extract "https://www.flipkart.com/poco-m7-5g-locked-airtel-prepaid-satin-black-128-gb/p/itma98bb9c85c53b" --product
```

**Amazon product:**
```powershell
python -m tavily_demo.main extract "https://www.amazon.in/Apple-MacBook-Laptop-12-core-16-core/dp/B0DLHFY1C7" --product
```

**Any retail URL:**
```powershell
python -m tavily_demo.main extract "YOUR_PRODUCT_URL" --product
```

**Output includes:**
- Complete product title
- Price
- Ratings
- Retailer (auto-detected)
- Product description
- About This Product bullets
- Technical specifications table
- Ports & connectivity features

### 1. Search for a query

```powershell
python -m tavily_demo.main search --query "mobile phone" --max-results 5
```

Output: A Rich table with search results (title, URL, snippet).

Add `--json` to see raw Tavily response.

### 2. Extract content from URLs

```powershell
python -m tavily_demo.main extract https://www.flipkart.com/mobile --query "product details"
```

Output: A Rich table with extracted summaries per URL (title, URL, summary).

Add `--json` to see raw Tavily payload. Use `--product` flag for detailed product extraction.

## Flags

- `--query/-q`: Search string (required for `search` and `search-products`) or focus prompt for `extract`.
- `--site/-s`: Restrict search to specific retailer (e.g., `flipkart`, `amazon`, `myntra`) - only for `search-products`.
- `--product/-p`: Enable detailed product extraction mode - only for `extract` command.
- `--max-results/-m`: Number of results to return (default 5, only for `search` and `search-products`).
- `--search-depth/-d`: `basic` (faster) or `advanced` (more detailed, only for `search` and `search-products`).
- `--extract-top/-e`: Number of top pages to extract product details from (1-10, default 3, only for `search-products`).
- `--json`: Emit raw JSON instead of formatted table.
- `--api-key`: Tavily API key (overrides `TAVILY_API_KEY` env var).

## Tests

```powershell
pytest
```

Runs unit tests covering search and extract logic.

## Project structure

```
src/tavily_demo/
  config.py       # env loading
  client.py       # Tavily API wrapper (search, extract)
  main.py         # CLI commands
tests/
  test_client.py  # unit tests
  test_live_search.py  # integration test (auto-skip if no API key)
```

Happy searching!
