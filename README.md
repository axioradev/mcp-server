# Axiora MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that gives AI agents access to financial data for **4,000+ Japanese listed companies**. Search companies, analyze financials, read translated filings, screen stocks, track ownership changes, and more — all from Claude, Cursor, or any MCP-compatible client.

Data is sourced from [EDINET](https://disclosure2.edinet-fsa.go.jp/) (Japan's FSA) — audited XBRL filings, not scraped or AI-estimated.

**Free API key:** [axiora.dev](https://axiora.dev) — full access to all companies and all endpoints.

## Available Tools (33)

### Company Discovery
| Tool | Description |
|------|-------------|
| `search_companies` | Find companies by name (JP/EN), securities code, or EDINET code |
| `search_companies_batch` | Look up multiple companies at once (up to 10) |
| `get_company` | Detailed info for a single company |
| `get_sector_overview` | List all 33 TSE sectors or get stats for one sector |

### Financial Data
| Tool | Description |
|------|-------------|
| `get_financials` | Revenue, net income, assets, equity, ROE, ROA, margins — up to 20 years |
| `get_growth` | YoY growth rates and 3yr/5yr CAGRs |
| `get_health_score` | Financial health score (0-100) with component breakdown and risk flags |
| `get_peers` | Find peer companies in same sector with similar revenue |
| `compare_companies` | Side-by-side financials for 2-5 companies |
| `get_timeseries` | Chart-ready time-series for any metric across multiple companies |

### Screening & Rankings
| Tool | Description |
|------|-------------|
| `screen_companies` | Filter by sector, min revenue, min ROE, max PE, and more |
| `get_ranking` | Rank all companies by any metric (revenue, ROE, margins, etc.) |
| `get_health_ranking` | Rank by financial health score |

### Filing Content & Translations
| Tool | Description |
|------|-------------|
| `get_sections` | Full Japanese text from annual filings (MD&A, risk factors, governance...) with English translations |
| `get_translations` | English translations of a specific filing |
| `search_translations` | Full-text search across all translated filings |

### Filings & Coverage
| Tool | Description |
|------|-------------|
| `list_filings` | List filings with filters (company, doc type) |
| `get_filing_calendar` | Filing calendar for a month (filings per day) |
| `get_coverage` | Data coverage stats (totals, freshness) |

### Buybacks
| Tool | Description |
|------|-------------|
| `get_buybacks` | Monthly buyback execution reports — shares acquired, amounts spent, completion % |

### Ownership Intelligence
| Tool | Description |
|------|-------------|
| `get_shareholdings` | Large shareholding reports (>=5% holders) with purposes and funding sources |
| `get_ownership_trajectories` | Per-filer ownership time-series showing accumulation/exit patterns |
| `get_ownership_movers` | Market-wide biggest ownership moves ranked by velocity |
| `get_ownership_signals` | Detected signals: accumulation streaks, step-ups, exits, activist escalations |
| `get_cross_holdings` | Cross-holding pairs where two companies hold >=5% of each other |
| `get_probability_table` | P(reaching 10%/20%/33% | current trajectory) — conditional completion probabilities |
| `get_capital_allocation` | Classify a company as Returner, Hoarder, Reinvestor, or Mixed |
| `get_capital_allocation_ranking` | Rank companies by capital allocation style |
| `get_activist_campaigns` | Detected activist campaigns with holding trajectories and outcomes |
| `get_unwinding_scoreboard` | Cross-holdings being dissolved — tracking Japan's governance reform |

### Governance
| Tool | Description |
|------|-------------|
| `get_board_composition` | Directors, auditors, officers with outside/independent status and gender breakdown |
| `get_voting_results` | AGM voting results — proposal-level votes, approval %, outcomes |

## Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/axiora-dev/mcp-server.git
   cd mcp-server
   ```

2. If you don't have uv installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Set up your API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your API key from https://axiora.dev
   ```

4. Run the server:
   ```bash
   uv run server.py
   ```

## Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "axiora": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/mcp-server", "run", "server.py"],
      "env": {
        "AXIORA_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add axiora -- uv --directory /absolute/path/to/mcp-server run server.py
```

### Cursor

Add to Cursor Settings → MCP Servers:

```json
{
  "mcpServers": {
    "axiora": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/mcp-server", "run", "server.py"],
      "env": {
        "AXIORA_API_KEY": "your-api-key"
      }
    }
  }
}
```

### VS Code (Copilot)

Add to `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "axiora": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/mcp-server", "run", "server.py"],
      "env": {
        "AXIORA_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "axiora": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/mcp-server", "run", "server.py"],
      "env": {
        "AXIORA_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Example Prompts

Once connected, try asking your AI assistant:

- "What are Toyota's financials for the last 5 years?"
- "Compare Sony, Nintendo, and Bandai Namco"
- "Find Japanese companies with ROE above 15% in the electronics sector"
- "What risks does SoftBank mention in their latest annual report?"
- "Show me the healthiest companies in the information & communication sector"
- "Who is accumulating shares in Japanese companies right now?"
- "Show me activist campaigns in Japan"
- "What's Toyota's board composition?"
- "Which companies are classified as capital returners?"

## Alternative: Hosted MCP (Zero Install)

Don't want to run a local server? Axiora also offers a **hosted MCP endpoint** at `https://api.axiora.dev/mcp` with the same tools — no installation required.

## Python SDK

For programmatic access beyond MCP, install the [Python SDK](https://pypi.org/project/axiora/):

```bash
pip install axiora
```

```python
from axiora import Axiora

client = Axiora(api_key="your-api-key")
toyota = client.companies.retrieve("7203")
financials = client.companies.retrieve_financials("7203", years=10)
results = client.screen.retrieve(min_roe=15.0, sector="電気機器")
```

## Data Coverage

| Dimension | Detail |
|-----------|--------|
| Companies | ~4,000 listed + ~7,500 non-listed (11,000+ total) |
| Metrics | 52 per company per fiscal year |
| History | Up to 15 years (FY2010-FY2025) |
| Standards | JP GAAP, IFRS, US GAAP (auto-normalized) |
| Translations | English translations of MD&A, risk factors, governance, and more |
| Ownership | 19,000+ large shareholding reports with trajectory analysis |
| Buybacks | 6,900+ monthly buyback execution reports |
| Updates | Every 30 minutes from EDINET |
| Source | Audited XBRL filings (金融庁 Financial Services Agency) |

## Links

- [Axiora](https://axiora.dev) — Dashboard, API keys, docs
- [API Documentation](https://axiora.dev/docs)
- [Python SDK on PyPI](https://pypi.org/project/axiora/)

## License

MIT
