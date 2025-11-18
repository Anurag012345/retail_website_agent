from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class RetailUseCase:
    """Represents a structured retail website research question."""

    brand: str
    objective: str
    audience: Optional[str] = None
    site: Optional[str] = None

    def build_query(self) -> str:
        return build_retail_query(
            brand=self.brand,
            objective=self.objective,
            audience=self.audience,
            site=self.site,
        )


def _sanitize_site(site: str) -> str:
    candidate = site.strip()
    if not candidate:
        raise ValueError("site must be a non-empty string when provided")

    if not candidate.startswith("http://") and not candidate.startswith("https://"):
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    hostname = parsed.netloc or parsed.path
    return hostname.lstrip("www.")


def build_retail_query(
    *,
    brand: str,
    objective: str,
    audience: Optional[str] = None,
    site: Optional[str] = None,
) -> str:
    """Return a Tavily-friendly query tailored for retail website insights."""
    brand_value = brand.strip()
    if not brand_value:
        raise ValueError("brand must be provided")

    objective_value = objective.strip()
    if not objective_value:
        raise ValueError("objective must be provided")

    parts = [brand_value, "retail website", objective_value]
    if audience and audience.strip():
        parts.append(f"for {audience.strip()} shoppers")

    if site:
        hostname = _sanitize_site(site)
        parts.append(f"site:{hostname}")

    return " ".join(parts)
