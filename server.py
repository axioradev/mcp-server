"""Axiora MCP Server — Japanese financial data for AI agents.

Connects Claude, Cursor, and other AI assistants to 4,000+ Japanese
listed companies via the Axiora API. Search companies, analyze financials,
read translated filings, screen stocks, and more.

Get your free API key at https://axiora.dev

Usage:
    uv run server.py
"""

import json
import logging
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("axiora-mcp")

mcp = FastMCP(
    "axiora",
    instructions=(
        "Axiora provides structured financial data for Japanese listed "
        "companies. Data comes from EDINET (金融庁) filings — audited XBRL, "
        "not scraped or AI-estimated. Use these tools to search companies, "
        "get financials, rankings, health scores, translated filings, and more."
    ),
)

API_BASE = os.environ.get("AXIORA_BASE_URL", "https://api.axiora.dev/v1")
API_KEY = os.environ.get("AXIORA_API_KEY", "")


async def _request(path: str, params: dict | None = None) -> dict | None:
    """Make a GET request to the Axiora API."""
    url = f"{API_BASE}{path}"
    params = {k: v for k, v in (params or {}).items() if v is not None}
    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, params=params, timeout=30.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            body = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = body.get("error", {}).get("message", str(e))
            return {"error": error_msg}
        except Exception as e:
            return {"error": str(e)}


def _unwrap(data: dict | None, key: str = "data") -> list | dict:
    """Unwrap Axiora API envelope: {"data": ..., "meta": ...} → data."""
    if data is None:
        return {"error": "No response from API."}
    if "error" in data:
        return data
    return data.get(key, data)


# ---------------------------------------------------------------------------
# Company discovery
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_companies(query: str, limit: int = 10) -> str:
    """Search for Japanese listed companies by name or code.

    Args:
        query: Company name (JP or EN), securities code, or EDINET code.
        limit: Max results to return (default 10, max 100).
    """
    data = await _request("/companies/search", {"q": query, "limit": limit})
    result = _unwrap(data)

    if not result:
        return "No companies found."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def search_companies_batch(queries: list[str]) -> str:
    """Look up multiple companies at once by code or name.

    Useful for comparison workflows. Accepts a mix of EDINET codes,
    securities codes, and name fragments. Returns all matches.

    Args:
        queries: List of company identifiers (max 10). Each can be an
            EDINET code, securities code, or name search string.
    """
    if not queries or len(queries) > 10:
        return json.dumps({"error": "Provide 1-10 company identifiers."})

    results = []
    for q in queries:
        data = await _request("/companies/search", {"q": q.strip(), "limit": 5})
        items = _unwrap(data)
        if isinstance(items, list):
            for item in items:
                item["query"] = q.strip()
            results.extend(items)

    if not results:
        return "No companies found."

    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_company(code: str) -> str:
    """Get detailed info for a single company.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
    """
    data = await _request(f"/companies/{code}")
    result = _unwrap(data)

    if not result:
        return f"Company '{code}' not found."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_sector_overview(sector: str | None = None) -> str:
    """List sectors with company counts, or get stats for a specific sector.

    Args:
        sector: If provided, returns aggregate stats for that sector.
            If omitted, returns all 33 TSE sectors with company counts.
    """
    if sector:
        data = await _request(f"/sectors/{sector}")
    else:
        data = await _request("/sectors")

    result = _unwrap(data)

    if not result:
        return "No sector data found."

    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Financial data
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_financials(code: str, years: int = 5) -> str:
    """Get financial time series for a company.

    Returns revenue, net income, total assets, equity, and computed
    ratios (ROE, ROA, margins) for each fiscal year.

    Args:
        code: EDINET code or securities code.
        years: Number of years to return (default 5, max 20).
    """
    data = await _request(f"/companies/{code}/financials", {"years": years})
    result = _unwrap(data)

    if not result:
        return f"No financials found for '{code}'."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_growth(code: str, years: int = 5) -> str:
    """Get year-over-year growth rates and CAGRs for a company.

    Args:
        code: EDINET code or securities code.
        years: Number of years of history (default 5, max 20).
    """
    data = await _request(f"/companies/{code}/growth", {"years": years})
    result = _unwrap(data)

    if not result:
        return f"No growth data found for '{code}'."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_health_score(code: str) -> str:
    """Get the financial health score (0-100) for a company.

    Returns a transparent score with component breakdown (stability,
    profitability, cash flow), risk flags, and industry adjustment.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
    """
    data = await _request(f"/companies/{code}/health")
    result = _unwrap(data)

    if not result:
        return f"No health score found for '{code}'."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_peers(code: str, limit: int = 10) -> str:
    """Find peer companies in the same sector with similar revenue.

    Returns companies ranked by revenue proximity to the target.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        limit: Max results (default 10, max 50).
    """
    data = await _request(f"/companies/{code}/peers", {"limit": limit})
    result = _unwrap(data)

    if not result:
        return f"No peers found for '{code}'."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def compare_companies(
    codes: list[str],
    fiscal_year: int | None = None,
) -> str:
    """Compare financials of 2-10 companies side by side.

    Args:
        codes: List of EDINET or securities codes (2-10 companies).
        fiscal_year: Optional fiscal year to compare. Defaults to latest.
    """
    if len(codes) < 2 or len(codes) > 10:
        return json.dumps({"error": "Provide 2-10 company codes."})

    codes_str = ",".join(codes)
    data = await _request("/compare", {"codes": codes_str, "fiscal_year": fiscal_year})
    result = _unwrap(data)

    if not result:
        return "No comparison data found."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_timeseries(
    codes: list[str],
    metric: str = "revenue",
    years: int = 10,
) -> str:
    """Get time-series data for a financial metric across companies.

    Returns chart-friendly format: one array per company with
    {fiscal_year, value} points.

    Args:
        codes: List of EDINET or securities codes (max 5).
        metric: Financial metric to chart. Options: revenue, net_income,
            operating_income, total_assets, total_equity, eps, bps,
            dividends_per_share, operating_cf, investing_cf, financing_cf,
            roe, pe_ratio, num_employees.
        years: Number of years (default 10, max 20).
    """
    if not codes or len(codes) > 5:
        return json.dumps({"error": "Provide 1-5 company codes."})

    codes_str = ",".join(codes)
    data = await _request("/timeseries", {
        "codes": codes_str,
        "metric": metric,
        "years": years,
    })
    result = _unwrap(data)

    if not result:
        return "No time-series data found."

    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Screening & rankings
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_companies(
    sector: str | None = None,
    revenue_min: int | None = None,
    net_income_min: int | None = None,
    roe_min: float | None = None,
    limit: int = 20,
) -> str:
    """Screen companies by financial criteria.

    All filters are combined with AND logic.

    Args:
        sector: Filter by sector (e.g. '情報・通信業', 'Information & Communication').
        revenue_min: Minimum revenue in JPY.
        net_income_min: Minimum net income in JPY.
        roe_min: Minimum ROE percentage (e.g. 10.0 for 10%).
        limit: Max results (default 20, max 100).
    """
    data = await _request("/screen", {
        "sector": sector,
        "revenue_min": revenue_min,
        "net_income_min": net_income_min,
        "roe_min": roe_min,
        "limit": limit,
    })
    result = _unwrap(data)

    if not result:
        return "No companies match the criteria."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_ranking(
    metric: str = "revenue",
    sector: str | None = None,
    order: str = "desc",
    limit: int = 20,
) -> str:
    """Get a ranking of companies by financial metric.

    Args:
        metric: Metric to rank by. One of: revenue, net_income,
            operating_income, total_assets, roe, roa, operating_margin,
            net_margin, equity_ratio, eps, bps.
        sector: Optional sector filter.
        order: 'desc' (default) for top, 'asc' for bottom.
        limit: Number of results (default 20, max 100).
    """
    data = await _request(f"/rankings/{metric}", {
        "sector": sector,
        "order": order,
        "limit": limit,
    })
    result = _unwrap(data)

    if not result:
        return "No ranking data found."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_health_ranking(
    sector: str | None = None,
    order: str = "desc",
    limit: int = 20,
) -> str:
    """Rank companies by financial health score.

    Args:
        sector: Optional sector filter (e.g. '電気機器').
        order: 'desc' for healthiest first (default), 'asc' for weakest.
        limit: Max results (default 20, max 100).
    """
    data = await _request("/rankings/health_score", {
        "sector": sector,
        "order": order,
        "limit": limit,
    })
    result = _unwrap(data)

    if not result:
        return "No health ranking data found."

    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Filing content & translations
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_sections(
    code: str,
    section: str | None = None,
    fiscal_year: int | None = None,
) -> str:
    """Get text sections from a company's annual filing (MD&A, risk factors, etc.).

    Returns full Japanese text with English translations where available.
    15 section types: mda, risk_factors, business_overview, strategy,
    sustainability, governance, accounting_policy, and more.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        section: Optional filter by section key (e.g. 'mda', 'risk_factors').
        fiscal_year: Optional fiscal year. Defaults to latest annual filing.
    """
    data = await _request(f"/companies/{code}/sections", {
        "section": section,
        "fiscal_year": fiscal_year,
    })
    result = _unwrap(data)

    if not result:
        return f"No sections found for '{code}'."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_translations(
    doc_id: str,
    section: str | None = None,
) -> str:
    """Get English translations of a Japanese filing.

    Args:
        doc_id: EDINET document ID (e.g. 'S100ABCD').
        section: Optional filter: mda, risk_factors, business_overview,
            governance, financial_notes, accounting_policy.
    """
    data = await _request(f"/filings/{doc_id}/translations", {"section": section})
    result = _unwrap(data)

    if not result:
        return f"No translations found for filing '{doc_id}'."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def search_translations(
    query: str,
    section: str | None = None,
    limit: int = 10,
) -> str:
    """Full-text search across English translations of Japanese filings.

    Returns matching sections with highlighted snippets, ranked by relevance.

    Args:
        query: Search terms (e.g. 'semiconductor', 'supply chain risk').
        section: Optional filter by section (mda, risk_factors, etc.).
        limit: Max results (default 10, max 50).
    """
    data = await _request("/translations/search", {
        "q": query,
        "section": section,
        "limit": limit,
    })
    result = _unwrap(data)

    if not result:
        return "No translation matches found."

    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Filings & coverage
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_filings(
    company_code: str | None = None,
    doc_type: str | None = None,
    limit: int = 20,
) -> str:
    """List filings with optional filters.

    Args:
        company_code: EDINET code or securities code to filter by.
        doc_type: Document type code (120=annual, 130=semi-annual, 140=quarterly).
        limit: Max results (default 20, max 100).
    """
    data = await _request("/filings", {
        "company_code": company_code,
        "doc_type": doc_type,
        "limit": limit,
    })
    result = _unwrap(data)

    if not result:
        return "No filings found."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_filing_calendar(month: str) -> str:
    """Get filing calendar for a month — how many filings per day.

    Useful for knowing when annual reports are filed.

    Args:
        month: Month in YYYY-MM format (e.g. '2025-06').
    """
    data = await _request("/filings/calendar", {"month": month})
    result = _unwrap(data)

    if not result:
        return f"No filing calendar data for '{month}'."

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_coverage() -> str:
    """Get data coverage statistics — totals, metric availability, freshness.

    Shows what data is available, how many companies and filings exist,
    and per-metric coverage percentages. Useful for assessing data quality.
    """
    data = await _request("/coverage")
    result = _unwrap(data)

    if not result:
        return "Unable to fetch coverage data."

    return json.dumps(result, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    logger.info("Starting Axiora MCP Server...")
    mcp.run(transport="stdio")
