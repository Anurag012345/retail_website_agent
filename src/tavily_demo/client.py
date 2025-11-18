from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional

from tavily import TavilyClient

from .config import Settings, load_settings


def parse_product(raw_content: str, url: str = "", title: str = "") -> Dict[str, Any]:
    """Universal product parser that auto-detects retailer and extracts complete product info.
    
    Supports: Amazon, Flipkart, Myntra, Ajio, and other e-commerce sites.
    """
    rc = raw_content
    url_lower = url.lower()
    
    # Detect retailer
    retailer = "unknown"
    if "amazon" in url_lower:
        retailer = "amazon"
    elif "flipkart" in url_lower:
        retailer = "flipkart"
    elif "myntra" in url_lower:
        retailer = "myntra"
    elif "ajio" in url_lower:
        retailer = "ajio"
    
    product = {
        'title': None,  # Will extract from content
        'price': None,
        'about_bullets': [],
        'technical_details': {},
        'features': [],
        'ratings': None,
        'retailer': retailer,
        'description': None
    }
    
    # Extract actual product title from page content
    title_patterns = [
        # Amazon patterns
        r'<title[^>]*>([^|<]+?)(?:\s*[:|]\s*Amazon)',
        r'Product Title[:\s]*([^\n]{20,200})',
        
        # Flipkart patterns  
        r'<title[^>]*>([^|<]+?)(?:\s*[:|]\s*Flipkart)',
        r'Product Name[:\s]*([^\n]{20,200})',
        
        # Look for product names in listings (usually have brand + model)
        r'(?:APPLE|Samsung|Xiaomi|Redmi|OnePlus|Realme|Oppo|Vivo|Motorola|Nokia|Nothing|POCO|iQOO)\s+[A-Z][^\n]{15,150}',
        
        # Generic patterns - look for heading markers
        r'^#+\s*([^\n]{20,200})',  # Markdown headings
        r'Product:\s*([^\n]{20,200})',
        r'Name:\s*([^\n]{20,200})',
    ]
    
    extracted_title = None
    for pat in title_patterns:
        m = re.search(pat, rc, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            candidate = m.group(1).strip() if m.lastindex else m.group(0).strip()
            # Filter out generic page titles and navigation
            exclude_phrases = ['online shopping', 'buy online', 'best price', 'flipkart.com', 
                             'amazon.in', 'home', 'cart', 'login', 'mobiles under', 'best sellers']
            if len(candidate) > 20 and not any(x in candidate.lower() for x in exclude_phrases):
                extracted_title = candidate
                break
    
    # For listing pages, try to extract first product from structured data
    if not extracted_title or any(phrase in (extracted_title or '').lower() for phrase in ['mobiles under', 'results for', 'best sellers', 'of over']):
        # Strategy 1: Look for product links/titles (Amazon/Flipkart format)
        # Pattern: Brand + Model with specs in markdown link format
        link_pattern = r'\[([^\]]{30,200}(?:GB|TB|Pro|Max|Plus|Ultra|Lite|Prime)[^\]]{0,50})\]\('
        link_matches = list(re.finditer(link_pattern, rc))
        
        for match in link_matches[:15]:
            candidate = match.group(1).strip()
            # Filter out navigation/UI elements
            if any(skip in candidate.lower() for skip in ['account', 'cart', 'login', 'sign in', 'become', 'explore', 'image']):
                continue
            # Check if it looks like a product (has brand name)
            if re.search(r'\b(?:APPLE|iPhone|Samsung|Galaxy|Xiaomi|Redmi|OnePlus|Realme|Oppo|Vivo|Motorola|Moto|Nokia|Nothing|POCO|iQOO|Google|Pixel|Asus|Lenovo|Honor|Infinix|Tecno|Lava|Micromax)\b', candidate, re.IGNORECASE):
                extracted_title = candidate[:150]  # Limit length
                break
        
        # Strategy 2: If Strategy 1 failed, look for product names with prices nearby
        if not extracted_title:
            product_name_pattern = r'(?:APPLE|iPhone|Samsung|Galaxy|Xiaomi|Redmi|OnePlus|Realme|Oppo|Vivo|Motorola|Moto|Nokia|Nothing|POCO|iQOO|Google Pixel|Asus|Lenovo|Honor|Infinix|Tecno|Lava|Micromax)\s+(?:[A-Z][A-Za-z0-9\s\+\-\(\)]+(?:GB|TB|Pro|Max|Plus|Ultra|Lite|Prime)?(?:\s*\([^)]+\))?)'
            matches = list(re.finditer(product_name_pattern, rc, flags=re.IGNORECASE))
            
            # Find first product name that has a price within 500 chars
            for match in matches[:10]:  # Check first 10 matches
                product_name = match.group(0).strip()
                # Clean up the product name
                product_name = re.sub(r'\s+', ' ', product_name)
                product_name = re.sub(r'\s*\.\.\.$', '', product_name)  # Remove trailing ...
                
                if len(product_name) < 30:  # Too short, likely not a full product name
                    continue
                    
                start = match.start()
                # Look for price near this product name
                nearby_text = rc[max(0, start-300):start+500]
                if re.search(r'[₹$]\s*[\d,]+', nearby_text):
                    extracted_title = product_name
                    break
    
    # If we found a product title in content, use it; otherwise fall back to page title
    if extracted_title:
        # Clean up markdown formatting
        extracted_title = re.sub(r'^#+\s*', '', extracted_title)  # Remove markdown headers
        extracted_title = re.sub(r'\s+', ' ', extracted_title).strip()  # Normalize spaces
    
    product['title'] = extracted_title if extracted_title else title
    
    # Extract price (supports ₹, $, and various formats)
    price_patterns = [
        r'₹\s*[\d,]+(?:\.\d{2})?',
        r'M\.R\.P\.?:?\s*₹\s*[\d,]+',
        r'Price:\s*₹\s*[\d,]+',
        r'\$\s*[\d,]+(?:\.\d{2})?',
        r'Rs\.?\s*[\d,]+',
        r'INR\s*[\d,]+',
    ]
    for pat in price_patterns:
        m = re.search(pat, rc)
        if m:
            product['price'] = m.group(0).strip()
            break
    
    # Extract About this item bullets
    bullets = []
    # Look for the actual "About this item" section with bullets (not navigation)
    about_patterns = [
        r'About this item\s*={3,}\s*\n((?:\*\s+.*?\n)+)',  # Markdown style with ===
        r'About this item\s*-{3,}\s*\n((?:\*\s+.*?\n)+)',  # Markdown style with ---
        r'About this item\s*\n\s*\n((?:\*\s+.*?\n)+)',     # Simple newlines
    ]
    
    for pat in about_patterns:
        m = re.search(pat, rc, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            bullet_block = m.group(1)
            for line in bullet_block.splitlines():
                ls = line.strip()
                if ls.startswith('*'):
                    bullet_text = ls.lstrip('* ').strip()
                    if len(bullet_text) > 20:  # Only substantial bullets
                        bullets.append(bullet_text)
            break
    
    # Flipkart: Look for Highlights section
    if len(bullets) < 3 and retailer == 'flipkart':
        highlights_patterns = [
            r'Highlights[:\s]*\n([^\n]{0,100}\n(?:[^\n]{20,500}\n){1,10})',
            r'Key Features[:\s]*\n([^\n]{0,100}\n(?:[^\n]{20,500}\n){1,10})',
        ]
        for pat in highlights_patterns:
            m = re.search(pat, rc, flags=re.IGNORECASE)
            if m:
                highlight_block = m.group(1)
                for line in highlight_block.splitlines():
                    ls = line.strip()
                    if ls and len(ls) > 20 and not any(skip in ls.lower() for skip in ['image', 'javascript', 'http']):
                        bullets.append(ls)
                break
    
    # Fallback: if no structured bullets found, look for feature-rich lines
    if len(bullets) < 3:
        about_idx = rc.lower().find('about this item')
        if about_idx != -1:
            blk = rc[about_idx:about_idx + 15000]
            lines = blk.splitlines()
            
            skip_phrases = [
                'javascript:', 'image', 'click to open', 'read more', 'see all',
                'customer review', 'http', 'void(0'
            ]
            
            for line in lines:
                ls = line.strip()
                if not ls or len(ls) < 30:
                    continue
                
                # Skip if contains any skip phrase
                if any(skip in ls.lower() for skip in skip_phrases):
                    continue
                
                # Look for lines with substantial product features
                if any(kw in ls.lower() for kw in ['chip', 'cpu', 'gpu', 'display', 'battery', 
                                                        'memory', 'storage', 'camera', 'thunderbolt', 
                                                        'performance', 'intelligence', 'apps']):
                    if len(ls) < 300:
                        bullets.append(ls)
    
    product['about_bullets'] = bullets[:12]
    
    # Extract product description (first substantial paragraph)
    desc_patterns = [
        r'Product [Dd]escription[:\s]*([^\n]{100,800})',
        r'Description[:\s]*\n+([^\n]{100,800})',
        r'About [Tt]his [Pp]roduct[:\s]*([^\n]{100,800})',
        r'Product [Dd]etails[:\s]*\n+([^\n]{100,800})',  # Flipkart
    ]
    for pat in desc_patterns:
        m = re.search(pat, rc, flags=re.IGNORECASE)
        if m:
            desc = m.group(1).strip()
            # Clean up description
            desc = re.sub(r'\[Image[^\]]*\]\([^)]*\)', '', desc)  # Remove image links
            desc = re.sub(r'https?://[^\s]+', '', desc)  # Remove URLs
            if len(desc) > 50:
                product['description'] = desc
                break
    
    # If no description found, extract from first meaningful paragraph
    if not product['description']:
        paragraphs = [p.strip() for p in rc.split('\n\n') if 100 < len(p.strip()) < 1000]
        if paragraphs:
            product['description'] = paragraphs[0][:500]
    
    # Fix title if it's an error message and we have a good description
    if product['title'] and any(err in product['title'].lower() for err in ['sorry', 'problem', 'error', 'not found']):
        if product['description'] and len(product['description']) > 50:
            # Use description as title if current title is an error
            product['title'] = product['description'][:200]
    
    # Extract technical details (key-value pairs)
    tech_details = {}
    
    # Try multiple section names for technical details
    tech_section_names = ['technical details', 'specifications', 'general', 'product information', 'spec']
    tech_idx = -1
    
    for section_name in tech_section_names:
        tech_idx = rc.lower().find(section_name)
        if tech_idx != -1:
            break
    
    if tech_idx != -1:
        blk = rc[tech_idx:tech_idx + 15000]
        
        # Parse markdown table format: | Key | Value |
        lines = blk.splitlines()
        product_name_count = 0  # Track if this looks like a comparison table
        
        for line in lines:
            # Skip headers, separators, and empty lines
            if not line.strip() or '===' in line or '---' in line:
                continue
            
            # Match table rows: | key | value |
            if line.count('|') >= 2:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 2:
                    key = parts[0]
                    val = parts[1]
                    
                    # Detect if this is a product comparison table (multiple product names)
                    # Check if key contains brand names + model names (like "Samsung Galaxy M35 5G")
                    if re.search(r'(?:Samsung|Redmi|Xiaomi|Realme|OnePlus|OPPO|Vivo|iPhone|iQOO|POCO|Motorola|Nokia)\s+[A-Za-z0-9\s]+(?:5G|4G|Pro|Max|Plus|Ultra)', key, re.IGNORECASE):
                        product_name_count += 1
                        if product_name_count > 2:  # More than 2 product names = comparison table
                            tech_details.clear()  # Clear any details collected so far
                            break
                        continue  # Skip this entry
                    
                    # Filter out navigation, images, JavaScript
                    if any(skip in key.lower() for skip in ['image', 'click', 'javascript:', 'http', 'void(0']):
                        continue
                    if any(skip in val.lower() for skip in ['javascript:', 'http://www.', 'https://www.', 'void(0']):
                        continue
                    
                    # Skip if value contains multiple product names (comparison data)
                    if re.search(r'(?:Samsung|Redmi|Xiaomi|Realme|OnePlus|OPPO|Vivo|iPhone|iQOO|POCO)\s+[A-Za-z0-9\s]+(?:5G|4G)', val, re.IGNORECASE):
                        continue
                        
                    # Only substantial key-value pairs that look like specs
                    if 3 < len(key) < 80 and 1 < len(val) < 300:
                        # Prefer specification-like keys
                        spec_keywords = ['brand', 'model', 'processor', 'ram', 'storage', 'display', 'battery', 
                                       'camera', 'color', 'weight', 'dimensions', 'os', 'operating system',
                                       'chipset', 'memory', 'screen', 'resolution', 'refresh rate']
                        if any(kw in key.lower() for kw in spec_keywords):
                            tech_details[key] = val
                        elif len(tech_details) < 5:  # Only add non-spec keys if we have few details
                            tech_details[key] = val
        
        # Fallback: parse colon-separated lines if table parsing didn't work
        if len(tech_details) < 3:
            for line in blk.splitlines():
                # Skip image and JavaScript lines
                if 'image' in line.lower() or 'javascript' in line.lower() or 'http' in line:
                    continue
                    
                if ':' in line:
                    parts = line.split(':', maxsplit=1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip()
                        # Filter out navigation and UI elements
                        if 5 < len(key) < 50 and 2 < len(val) < 200:
                            if not any(skip in key.lower() for skip in ['image', 'click', 'see all']):
                                tech_details[key] = val
    
    product['technical_details'] = tech_details
    
    # Extract features/ports
    features = []
    feature_keywords = [
        'Thunderbolt', 'HDMI', 'SDXC', 'Wi-Fi', 'Wi‑Fi', 'Bluetooth',
        'FaceTime', 'Touch ID', 'MagSafe', 'USB-C', 'headphone jack',
        'Magic Keyboard', 'Touch Bar', 'Force Touch'
    ]
    
    for kw in feature_keywords:
        matches = re.finditer(rf'[^.]*{kw}[^.]*\.?', rc, flags=re.IGNORECASE)
        for m in matches:
            feat = m.group(0).strip()
            # Filter out image references and links
            if 15 < len(feat) < 150 and 'http' not in feat and 'image' not in feat.lower() and '[![' not in feat:
                features.append(feat)
                break
    
    product['features'] = features[:10]
    
    # Extract ratings
    rating_patterns = [
        r'(\d+\.?\d*)\s*out of\s*5\s*stars',
        r'(\d+\.?\d*)\s*★',
        r'Rating:\s*(\d+\.?\d*)',
    ]
    for pat in rating_patterns:
        m = re.search(pat, rc, flags=re.IGNORECASE)
        if m:
            product['ratings'] = m.group(0).strip()
            break
    
    return product


@dataclass
class TavilyTester:
    """Simple wrapper for Tavily client."""

    settings: Settings
    client: TavilyClient

    @classmethod
    def build(cls, *, api_key: Optional[str] = None) -> "TavilyTester":
        settings = load_settings(api_key=api_key)
        client = TavilyClient(api_key=settings.api_key)
        return cls(settings=settings, client=client)

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> Dict[str, Any]:
        """Search the web for a query."""
        if not query:
            raise ValueError("query must be a non-empty string")
        return self.client.search(query=query, max_results=max_results, search_depth=search_depth)

    def extract_urls(
        self,
        urls: List[str],
        *,
        query: str = "Page summary",
    ) -> Dict[str, Any]:
        """Extract content from URLs and return summarized results."""
        if not urls:
            raise ValueError("urls list must not be empty")

        extraction = self.client.extract(
            urls=urls,
            extract_depth="advanced",
            format="markdown",
            include_images=False,
            timeout=90,
        )

        def summarize_text(text: Optional[str]) -> str:
            if not text:
                return ""
            collapsed = re.sub(r"\s+", " ", text.strip())
            sentences_split = re.split(r"(?<=[.!?])\s+", collapsed)
            snippet = " ".join(sentences_split[:3]).strip()
            if not snippet:
                snippet = collapsed[:300].strip()
            return snippet

        summaries = [
            {
                "url": item.get("url"),
                "title": item.get("title"),
                "summary": summarize_text(item.get("raw_content") or item.get("content")),
            }
            for item in extraction.get("results", [])
        ]

        return {
            "summaries": summaries,
            "raw": extraction,
        }

    def search_and_extract_products(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        extract_top_n: int = 3,
        include_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Search for a query and extract detailed product info.
        
        Strategy: 
        1. Search for query (optionally restricted to specific domains)
        2. Extract full page content from top N results
        3. Parse product details from extracted content
        
        Args:
            query: Search query
            max_results: Maximum search results to fetch
            search_depth: Search depth ("basic" or "advanced")
            extract_top_n: Number of top results to extract from
            include_domains: List of domains to restrict search to (e.g., ["flipkart.com", "amazon.in"])
        """
        if not query:
            raise ValueError("query must be a non-empty string")
        if extract_top_n < 1:
            raise ValueError("extract_top_n must be >= 1")

        # Step 1: Get search results with domain filtering
        search_params = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth
        }
        
        if include_domains:
            search_params["include_domains"] = include_domains
        
        search_response = self.client.search(**search_params)
        results = search_response.get("results", [])

        # Step 2: Try to extract content from top URLs
        urls_to_extract = [r.get("url") for r in results[:extract_top_n] if r.get("url")]
        
        extracted_products = []
        raw_extractions = []
        
        if urls_to_extract:
            try:
                extraction = self.client.extract(
                    urls=urls_to_extract,
                    extract_depth="advanced",
                    format="markdown",
                    include_images=False,
                    timeout=90,
                )
                raw_extractions = extraction.get("results", [])
                
                # Parse products from extracted content using universal parser
                for item in raw_extractions:
                    url = item.get("url", "")
                    # Use raw_content (new API) or content (fallback)
                    content = item.get("raw_content") or item.get("content")
                    title = item.get("title", "")
                    
                    if content:
                        # Use universal parser to extract complete product info
                        product_info = parse_product(content, url=url, title=title)
                        extracted_products.append({
                            "source_url": url,
                            "source_title": title,
                            "product_info": product_info,
                        })
            except Exception as e:
                # If extraction fails, still return search results
                pass

        # Step 3: If no products extracted, create pseudo-products from search results
        if not extracted_products and results:
            # Fallback: use search result titles and snippets as product info
            fallback_products = []
            for result in results[:5]:
                title = result.get("title", "")
                snippet = result.get("content", "")
                if title or snippet:
                    fallback_products.append({
                        "name": title,
                        "description": snippet[:200],
                        "source": "search_result",
                    })
            
            if fallback_products:
                extracted_products.append({
                    "source_url": "search_results",
                    "source_title": "Web Search Results",
                    "products": fallback_products,
                })

        return {
            "search_results": results,
            "extracted_products": extracted_products,
            "raw_extractions": raw_extractions,
        }

    def _parse_products_from_content(self, text: Optional[str]) -> List[Dict[str, str]]:
        """Extract structured product info from page content with complete details."""
        if not text:
            return []
        
        products = []
        lines = text.splitlines()
        
        # Brand list for matching
        brands = {
            "realme", "redmi", "iphone", "samsung", "poco", "motorola",
            "vivo", "oppo", "oneplus", "nothing", "nokia", "asus", "htc",
            "infinix", "tecno", "honor", "micromax", "lava", "symphony",
            "ai+", "itel", "moto"
        }
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            
            # Skip empty, short, or image/markdown lines
            if not line or len(line) < 8:
                continue
            
            # Skip image markdown, navigation, scripts
            if any(skip in line for skip in [
                "![Image", "[![Image", "href=", "<script", "<style",
                "[orders", "[help", "[cart", "[home", "[search",
                "javascript:", "|-", "![[image"
            ]):
                continue
            
            lower = line.lower()
            
            # Skip obvious non-product lines
            if any(skip in lower for skip in [
                "seller", "sponsored", "filters", "sort by", "best",
                "login", "account", "latest", "buy"
            ]):
                continue
            
            # Check if line contains a brand name and model info
            has_brand = any(brand in lower for brand in brands)
            
            # Extract product if it has brand + model/variant info
            if has_brand and ("(" in line or "5g" in lower or "4g" in lower or len(line) > 30):
                # Extract the core product info from the line
                # Typical Flipkart format: "Brand Model (Color, Storage)"
                
                # Clean up the line - remove leading/trailing brackets or markdown
                clean_line = line.replace("![Image", "").replace("[![Image", "")
                clean_line = clean_line.replace("](", " ").replace(")", "")
                clean_line = clean_line[:120].strip()  # Limit length
                
                # Only add if it looks like real product info
                if "(" in clean_line and ")" in clean_line:
                    products.append({"detail": clean_line})
                elif len(clean_line) > 25 and any(
                    keyword in lower for keyword in [
                        "5g", "4g", "gb", "mp", "mah", "battery", "display",
                        "camera", "processor", "storage", "ram"
                    ]
                ):
                    products.append({"detail": clean_line})
                
                if len(products) >= 12:
                    break
        
        # If we got very few products, fallback to more lenient approach
        if len(products) < 5:
            products = []
            for line in lines:
                stripped = line.strip()
                if not stripped or len(stripped) < 10:
                    continue
                
                # Skip image/script lines
                if any(skip in stripped for skip in ["![Image", "[![Image", "<script", "javascript:"]):
                    continue
                
                lower = stripped.lower()
                
                # More lenient: any line with brand + specs info
                has_brand = any(brand in lower for brand in brands)
                has_spec_indicator = any(
                    spec in lower for spec in ["gb", "5g", "4g", "mp", "mah", "inch", "hz"]
                )
                
                if has_brand and (has_spec_indicator or len(stripped) > 35):
                    # Clean markdown
                    clean = stripped.replace("![Image", "").replace("[![Image", "")
                    clean = clean.replace("](", " ").replace(")", "")
                    clean = clean[:120].strip()
                    
                    if clean and clean not in [p.get("detail", "") for p in products]:
                        products.append({"detail": clean})
                
                if len(products) >= 12:
                    break
        
        return products[:12]
