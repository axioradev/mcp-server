"""Axiora MCP Server — Japanese financial data for AI agents.

Connects Claude, Cursor, and other AI assistants to 4,000+ Japanese
listed companies via the Axiora API. Search companies, analyze financials,
read translated filings, screen stocks, track ownership changes, and more.

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
        "get financials, rankings, health scores, translated filings, "
        "ownership trajectories, buybacks, and more."
    ),
)

API_BASE = os.environ.get("AXIORA_BASE_URL", "https://api.axiora.dev/v1")
API_KEY = os.environ.get("AXIORA_API_KEY", "")

if not API_KEY:
    logger.warning(
        "AXIORA_API_KEY not set. Get a free key at https://axiora.dev"
    )


async def _request(path: str, params: dict | None = None) -> dict | None:
    """Make a GET request to the Axiora API."""
    if not API_KEY:
        return {"error": "AXIORA_API_KEY not set. Get a free key at https://axiora.dev"}

    url = f"{API_BASE}{path}"
    params = {k: v for k, v in (params or {}).items() if v is not None}
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": "axiora-mcp-server/0.2.0",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                url, headers=headers, params=params, timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            ct = e.response.headers.get("content-type", "")
            if ct.startswith("application/json"):
                body = e.response.json()
                error_msg = body.get("error", {}).get("message", str(e))
            else:
                error_msg = f"HTTP {e.response.status_code}"
            return {"error": error_msg}
        except httpx.TimeoutException:
            return {"error": "Request timed out. Try again."}
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
async def search_companies(
    query: str, sector: str | None = None, limit: int = 10,
) -> str:
    """Search for Japanese listed companies by name or code.

    Args:
        query: Company name (JP or EN), securities code, or EDINET code.
        sector: Optional sector filter (e.g. '電気機器', '情報・通信業').
        limit: Max results to return (default 10, max 50).
    """
    data = await _request(
        "/companies/search", {"q": query, "sector": sector, "limit": limit},
    )
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


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

    return json.dumps(results or [], indent=2, ensure_ascii=False)


@mcp.tool()
async def get_company(code: str) -> str:
    """Get detailed info for a single company.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
    """
    data = await _request(f"/companies/{code}")
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_sector_overview(sector: str | None = None) -> str:
    """List sectors with company counts, or get stats for a specific sector.

    Args:
        sector: If provided, returns aggregate stats for that sector.
            If omitted, returns all sectors with company counts.
    """
    if sector:
        data = await _request(f"/sectors/{sector}")
    else:
        data = await _request("/sectors")
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


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
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_growth(code: str, years: int = 5) -> str:
    """Get year-over-year growth rates and CAGRs for a company.

    Args:
        code: EDINET code or securities code.
        years: Number of years of history (default 5, max 20).
    """
    data = await _request(f"/companies/{code}/growth", {"years": years})
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_health_score(code: str) -> str:
    """Get the financial health score (0-100) for a company.

    Returns a transparent score with component breakdown (stability,
    profitability, cash flow), risk flags, and industry adjustment.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
    """
    data = await _request(f"/companies/{code}/health")
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_peers(code: str, limit: int = 10) -> str:
    """Find peer companies in the same sector with similar revenue.

    Returns companies ranked by revenue proximity to the target.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        limit: Max results (default 10, max 50).
    """
    data = await _request(f"/companies/{code}/peers", {"limit": limit})
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def compare_companies(codes: list[str], years: int = 3) -> str:
    """Compare financials of 2-5 companies side by side.

    Args:
        codes: List of EDINET or securities codes (2-5 companies).
        years: Number of years to include (default 3, max 10).
    """
    if len(codes) < 2 or len(codes) > 5:
        return json.dumps({"error": "Provide 2-5 company codes."})

    data = await _request(
        "/compare", {"codes": ",".join(codes), "years": years},
    )
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_timeseries(
    codes: list[str], metric: str = "revenue", years: int = 10,
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

    data = await _request("/timeseries", {
        "codes": ",".join(codes), "metric": metric, "years": years,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Screening & rankings
# ---------------------------------------------------------------------------


@mcp.tool()
async def screen_companies(
    sector: str | None = None,
    min_revenue: int | None = None,
    min_net_income: int | None = None,
    min_roe: float | None = None,
    max_pe_ratio: float | None = None,
    limit: int = 20,
) -> str:
    """Screen companies by financial criteria.

    All filters are combined with AND logic.

    Args:
        sector: Filter by sector (e.g. '情報・通信業').
        min_revenue: Minimum revenue in JPY.
        min_net_income: Minimum net income in JPY.
        min_roe: Minimum ROE percentage (e.g. 10.0 for 10%).
        max_pe_ratio: Maximum PE ratio (e.g. 15.0).
        limit: Max results (default 20, max 100).
    """
    data = await _request("/screen", {
        "sector": sector, "min_revenue": min_revenue,
        "min_net_income": min_net_income, "min_roe": min_roe,
        "max_pe_ratio": max_pe_ratio, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


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
        "sector": sector, "order": order, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_health_ranking(
    sector: str | None = None, order: str = "desc", limit: int = 20,
) -> str:
    """Rank companies by financial health score.

    Args:
        sector: Optional sector filter (e.g. '電気機器').
        order: 'desc' for healthiest first (default), 'asc' for weakest.
        limit: Max results (default 20, max 100).
    """
    data = await _request("/rankings/health_score", {
        "sector": sector, "order": order, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Filing content & translations
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_sections(
    code: str, section: str | None = None, fiscal_year: int | None = None,
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
        "section": section, "fiscal_year": fiscal_year,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_translations(doc_id: str, section: str | None = None) -> str:
    """Get English translations of a Japanese filing.

    Args:
        doc_id: EDINET document ID (e.g. 'S100ABCD').
        section: Optional filter: mda, risk_factors, business_overview,
            governance, financial_notes, accounting_policy.
    """
    data = await _request(
        f"/filings/{doc_id}/translations", {"section": section},
    )
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def search_translations(
    query: str, section: str | None = None, limit: int = 10,
) -> str:
    """Full-text search across English translations of Japanese filings.

    Returns matching sections with highlighted snippets, ranked by relevance.

    Args:
        query: Search terms (e.g. 'semiconductor', 'supply chain risk').
        section: Optional filter by section (mda, risk_factors, etc.).
        limit: Max results (default 10, max 50).
    """
    data = await _request("/translations/search", {
        "q": query, "section": section, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


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
        doc_type: Document type code (120=annual, 130=semi-annual,
            140=quarterly, 220=buyback).
        limit: Max results (default 20, max 100).
    """
    data = await _request("/filings", {
        "company_code": company_code, "doc_type": doc_type, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_filing_calendar(month: str) -> str:
    """Get filing calendar for a month — how many filings per day.

    Useful for knowing when annual reports are filed.

    Args:
        month: Month in YYYY-MM format (e.g. '2025-06').
    """
    data = await _request("/filings/calendar", {"month": month})
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_coverage() -> str:
    """Get data coverage statistics — totals, metric availability, freshness.

    Shows what data is available, how many companies and filings exist,
    and per-metric coverage percentages. Useful for assessing data quality.
    """
    data = await _request("/coverage")
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Buybacks
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_buybacks(code: str, limit: int = 20) -> str:
    """Get share buyback reports for a company.

    Returns monthly buyback status filings showing shares acquired,
    amounts spent, cumulative progress, and treasury share holdings.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        limit: Max results (default 20, max 100).
    """
    data = await _request(f"/companies/{code}/buybacks", {"limit": limit})
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Ownership intelligence
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_shareholdings(code: str, limit: int = 20) -> str:
    """Get large shareholding reports for a company.

    Returns filings by investors who hold >=5% of the company's shares.
    Shows who is buying/selling significant stakes, holding ratios,
    purposes, and funding sources.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        limit: Max results (default 20, max 100).
    """
    data = await _request(f"/companies/{code}/shareholdings", {"limit": limit})
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_ownership_trajectories(
    code: str,
    trajectory_type: str | None = None,
    limit: int = 20,
) -> str:
    """Get ownership trajectories for a company.

    Returns per-filer ownership time-series showing accumulation/exit
    patterns, velocity, and streak data.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        trajectory_type: Optional filter: 'accumulating', 'exiting',
            'stable', 'new_position'.
        limit: Max results (default 20, max 100).
    """
    data = await _request(f"/companies/{code}/ownership/trajectories", {
        "trajectory_type": trajectory_type, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_ownership_movers(
    days: int = 30,
    trajectory_type: str | None = None,
    limit: int = 20,
) -> str:
    """Get market-wide biggest ownership moves.

    Returns filers with the largest accumulations or exits in the
    last N days, ranked by velocity (percentage points per month).

    Args:
        days: Look back period (default 30, max 365).
        trajectory_type: Optional: 'accumulating' or 'exiting'.
        limit: Max results (default 20, max 100).
    """
    data = await _request("/ownership/movers", {
        "days": days, "trajectory_type": trajectory_type, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_ownership_signals(
    code: str | None = None,
    signal_type: str | None = None,
    days: int = 90,
    limit: int = 20,
) -> str:
    """Get detected ownership signals.

    Returns signals like accumulation streaks, large step-ups/downs,
    exits below 5%, activist escalations, and pace accelerations.

    Args:
        code: Optional EDINET or securities code to filter by issuer.
        signal_type: Optional filter: accumulation_streak, large_step_up,
            large_step_down, exit_below_5pct, activist_escalation,
            new_position, pace_acceleration.
        days: Look back period (default 90, max 365).
        limit: Max results (default 20, max 100).
    """
    data = await _request("/ownership/signals", {
        "code": code, "signal_type": signal_type,
        "days": days, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_cross_holdings(
    code: str | None = None, limit: int = 20,
) -> str:
    """Get cross-holding pairs where two companies hold >=5% of each other.

    Cross-shareholdings are a key feature of Japanese corporate governance.
    Returns pairs sorted by combined holding ratio.

    Args:
        code: Optional EDINET or securities code to filter by company.
        limit: Max results (default 20, max 100).
    """
    data = await _request("/ownership/cross-holdings", {
        "code": code, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_probability_table() -> str:
    """Get the conditional completion table for ownership trajectories.

    Shows P(reaching threshold | current trajectory features) computed from
    all historical trajectories. Bucketed by stake range, streak length,
    and purpose type. Thresholds: 10%, 20%, 33% (blocking minority).
    """
    data = await _request("/ownership/probability-table")
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_capital_allocation(code: str) -> str:
    """Get capital allocation classification for a company.

    Classifies companies as Returner, Hoarder, Reinvestor, Mixed,
    or Insufficient Data based on FCF deployment analysis.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
    """
    data = await _request(f"/companies/{code}/capital-allocation")
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_capital_allocation_ranking(
    classification: str | None = None,
    sector: str | None = None,
    limit: int = 20,
) -> str:
    """Rank companies by capital allocation classification.

    Args:
        classification: Optional filter: 'returner', 'hoarder',
            'reinvestor', 'mixed'.
        sector: Optional sector filter (e.g. '電気機器').
        limit: Max results (default 20, max 100).
    """
    data = await _request("/rankings/capital-allocation", {
        "classification": classification, "sector": sector, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_activist_campaigns(limit: int = 20) -> str:
    """Get detected activist campaigns in Japanese companies.

    Returns companies where filers changed purpose to activist or filed
    important proposals, with holding trajectories and outcomes.

    Args:
        limit: Max results (default 20, max 100).
    """
    data = await _request("/ownership/activist-campaigns", {"limit": limit})
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_unwinding_scoreboard(limit: int = 20) -> str:
    """Get cross-holdings that are being unwound.

    Returns cross-holding pairs where at least one side shows declining
    ownership. Tracks the dissolution of Japan's traditional
    cross-shareholding structures.

    Args:
        limit: Max results (default 20, max 100).
    """
    data = await _request(
        "/ownership/unwinding-scoreboard", {"limit": limit},
    )
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_board_composition(
    code: str, fiscal_year: int | None = None,
) -> str:
    """Get board composition and officer list for a company.

    Returns directors, auditors, executive officers with outside/independent
    status, gender breakdown, and shares held.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        fiscal_year: Optional fiscal year. Defaults to latest.
    """
    data = await _request(f"/companies/{code}/board", {
        "fiscal_year": fiscal_year,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_voting_results(
    code: str,
    fiscal_year: int | None = None,
    limit: int = 20,
) -> str:
    """Get AGM voting results for a company.

    Returns proposal-level results including votes for/against/abstain,
    approval percentages, and outcomes.

    Args:
        code: EDINET code (e.g. 'E02144') or securities code (e.g. '7203').
        fiscal_year: Optional fiscal year filter.
        limit: Max results (default 20, max 100).
    """
    data = await _request(f"/companies/{code}/voting", {
        "fiscal_year": fiscal_year, "limit": limit,
    })
    return json.dumps(_unwrap(data), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    logger.info("Starting Axiora MCP Server...")
    mcp.run(transport="stdio")
