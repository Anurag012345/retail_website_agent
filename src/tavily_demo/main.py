from __future__ import annotations

import json
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from .client import TavilyTester

app = typer.Typer(help="Tavily search & extract CLI")
console = Console()


def _format_hits(response: dict) -> Table:
    table = Table(title="Tavily Results", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("Title", overflow="fold")
    table.add_column("URL", overflow="fold")
    table.add_column("Snippet", overflow="fold")

    for idx, result in enumerate(response.get("results", []), start=1):
        table.add_row(str(idx), result.get("title", "?"), result.get("url", ""), result.get("content", ""))
    return table


@app.command()
def search(
    query: str = typer.Option(..., "--query", "-q", help="Search query (e.g., 'mobile phone')"),
    max_results: int = typer.Option(5, "--max-results", "-m", min=1, max=25),
    search_depth: str = typer.Option("basic", "--search-depth", "-d"),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON"),
    api_key: Optional[str] = typer.Option(None, envvar="TAVILY_API_KEY"),
):
    """Search the web for a query."""
    tester = TavilyTester.build(api_key=api_key)
    response = tester.search(query=query, max_results=max_results, search_depth=search_depth)

    if json_output:
        console.print_json(json.dumps(response))
    else:
        console.rule(f"Query: {query}")
        console.print(_format_hits(response))
        console.print(f"Total tokens used: {response.get('usage', {}).get('total_tokens', 'n/a')}")


@app.command()
def extract(
    urls: List[str] = typer.Argument(..., help="One or more URLs to extract"),
    query: str = typer.Option("Page summary", "--query", "-q", help="What to extract/focus on"),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON"),
    product: bool = typer.Option(False, "--product", "-p", help="Parse as product page (auto-detects retailer)"),
    api_key: Optional[str] = typer.Option(None, envvar="TAVILY_API_KEY"),
):
    """Extract and summarize content from specific URLs (supports any retail website)."""
    from .client import parse_product
    
    tester = TavilyTester.build(api_key=api_key)
    response = tester.extract_urls(urls=urls, query=query)

    if json_output:
        console.print_json(json.dumps(response["raw"]))
        return

    summaries = response.get("summaries", [])
    if not summaries:
        console.print("[yellow]No extractable content found.[/yellow]")
        return

    # Product-specific parsing (auto-detects retailer)
    if product and summaries:
        for idx, summary in enumerate(summaries, start=1):
            raw_results = response.get("raw", {}).get("results", [])
            if idx - 1 < len(raw_results):
                raw_item = raw_results[idx - 1]
                raw_content = raw_item.get("raw_content") or raw_item.get("content") or ""
                title = raw_item.get("title", "")
                url = raw_item.get("url", "")
                
                if raw_content:
                    product_info = parse_product(raw_content, url=url, title=title)
                    
                    console.rule(f"[bold cyan]Product {idx}[/bold cyan]")
                    console.print(f"[dim]URL: {url}[/dim]\n")
                    
                    if product_info.get('retailer'):
                        console.print(f"[bold]Retailer:[/bold] {product_info['retailer'].title()}\n")
                    
                    if product_info.get('title'):
                        console.print(f"[bold]Title:[/bold] {product_info['title']}\n")
                    
                    if product_info.get('price'):
                        console.print(f"[bold green]Price:[/bold green] {product_info['price']}\n")
                    
                    if product_info.get('ratings'):
                        console.print(f"[bold yellow]Ratings:[/bold yellow] {product_info['ratings']}\n")
                    
                    if product_info.get('description'):
                        console.print(f"[bold]Description:[/bold]")
                        console.print(f"  {product_info['description'][:500]}\n")
                    
                    if product_info.get('about_bullets'):
                        console.print("[bold]About This Product:[/bold]")
                        for i, bullet in enumerate(product_info['about_bullets'], 1):
                            console.print(f"  {i}. {bullet}")
                        console.print()
                    
                    if product_info.get('technical_details'):
                        console.print("[bold]Technical Details:[/bold]")
                        details_table = Table(show_header=False, box=None, padding=(0, 2))
                        details_table.add_column("Key", style="cyan")
                        details_table.add_column("Value")
                        for key, val in list(product_info['technical_details'].items())[:15]:
                            details_table.add_row(key, val)
                        console.print(details_table)
                        console.print()
                    
                    if product_info.get('features'):
                        console.print("[bold]Ports & Features:[/bold]")
                        for feat in product_info['features']:
                            console.print(f"  • {feat}")
                        console.print()
        return

    # Default table output
    table = Table(title="Extracted Content", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Title / URL", overflow="fold")
    table.add_column("Summary", overflow="fold")

    for idx, summary in enumerate(summaries, start=1):
        title = summary.get("title") or "(no title)"
        url = summary.get("url") or ""
        text = summary.get("summary") or "(empty)"
        table.add_row(str(idx), f"{title}\n{url}", text)

    console.print(table)


@app.command()
def search_products(
    query: str = typer.Option(..., "--query", "-q", help="Search query (e.g., 'mobile phones under 10k')"),
    max_results: int = typer.Option(5, "--max-results", "-m", min=1, max=25),
    search_depth: str = typer.Option("basic", "--search-depth", "-d"),
    extract_top_n: int = typer.Option(3, "--extract-top", "-e", min=1, max=10, help="Extract products from top N results"),
    site: Optional[str] = typer.Option(None, "--site", "-s", help="Restrict search to specific site (e.g., 'flipkart', 'amazon', 'myntra')"),
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON"),
    api_key: Optional[str] = typer.Option(None, envvar="TAVILY_API_KEY"),
):
    """Search for a product query and extract detailed product listings (optionally from specific site)."""
    
    # Auto-detect domain from query or use --site flag
    include_domains = None
    
    if site:
        # Map common site names to domains
        site_domains = {
            "flipkart": ["flipkart.com"],
            "amazon": ["amazon.in", "amazon.com"],
            "myntra": ["myntra.com"],
            "ajio": ["ajio.com"],
            "snapdeal": ["snapdeal.com"],
            "meesho": ["meesho.com"],
        }
        site_lower = site.lower()
        include_domains = site_domains.get(site_lower)
        if not include_domains:
            # If not in map, use as-is
            include_domains = [site]
    elif "flipkart" in query.lower():
        include_domains = ["flipkart.com"]
    elif "amazon" in query.lower():
        include_domains = ["amazon.in", "amazon.com"]
    elif "myntra" in query.lower():
        include_domains = ["myntra.com"]
    elif "ajio" in query.lower():
        include_domains = ["ajio.com"]
    
    tester = TavilyTester.build(api_key=api_key)
    response = tester.search_and_extract_products(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        extract_top_n=extract_top_n,
        include_domains=include_domains,
    )

    if json_output:
        console.print_json(json.dumps(response))
        return

    console.rule(f"Query: {query}")
    
    # Show search results
    search_results = response.get("search_results", [])
    if search_results:
        search_table = Table(title="[bold]Top Search Results[/bold]", show_lines=False)
        search_table.add_column("#", justify="right", width=3)
        search_table.add_column("Source", overflow="fold")
        search_table.add_column("URL", overflow="fold", width=40)
        
        for idx, result in enumerate(search_results[:5], start=1):
            title = result.get("title", "?")[:50]
            url = result.get("url", "")
            search_table.add_row(str(idx), title, url)
        
        console.print(search_table)
        console.print("")
    
    # Show extracted products with complete info
    extracted_products = response.get("extracted_products", [])
    if extracted_products:
        for source_idx, source in enumerate(extracted_products, start=1):
            source_title = source.get("source_title", "Source")
            source_url = source.get("source_url", "")
            product_info = source.get("product_info", {})
            
            if product_info:
                console.rule(f"[bold cyan]Product {source_idx}: {source_title}[/bold cyan]")
                console.print(f"[dim]URL: {source_url}[/dim]")
                console.print()
                
                # Display complete product information
                if product_info.get('title'):
                    console.print(f"[bold]Title:[/bold] {product_info['title']}")
                
                if product_info.get('price'):
                    console.print(f"[bold green]Price:[/bold green] {product_info['price']}")
                
                if product_info.get('ratings'):
                    console.print(f"[bold yellow]Ratings:[/bold yellow] {product_info['ratings']}")
                
                if product_info.get('retailer'):
                    console.print(f"[bold]Retailer:[/bold] {product_info['retailer'].title()}")
                
                console.print()
                
                # Description
                if product_info.get('description'):
                    console.print(f"[bold]Description:[/bold]")
                    console.print(f"  {product_info['description'][:500]}")
                    console.print()
                
                # About bullets
                if product_info.get('about_bullets'):
                    console.print("[bold]About This Product:[/bold]")
                    bullets_table = Table(show_header=False, box=None, padding=(0, 1))
                    bullets_table.add_column("#", justify="right", width=3)
                    bullets_table.add_column("Feature")
                    for idx, bullet in enumerate(product_info['about_bullets'][:10], start=1):
                        bullets_table.add_row(str(idx), bullet)
                    console.print(bullets_table)
                    console.print()
                
                # Technical details
                if product_info.get('technical_details'):
                    console.print("[bold]Technical Details:[/bold]")
                    details_table = Table(show_header=False, box=None, padding=(0, 2))
                    details_table.add_column("Key", style="cyan")
                    details_table.add_column("Value")
                    for key, val in list(product_info['technical_details'].items())[:15]:
                        details_table.add_row(key, val)
                    console.print(details_table)
                    console.print()
                
                # Features
                if product_info.get('features'):
                    console.print("[bold]Ports & Features:[/bold]")
                    for feat in product_info['features'][:10]:
                        console.print(f"  • {feat}")
                    console.print()
                
                console.print()
    else:
        console.print("[yellow]No detailed product information could be extracted.[/yellow]")


if __name__ == "__main__":
    app()


if __name__ == "__main__":
    app()
