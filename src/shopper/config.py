"""Settings, model IDs and endpoints. The only module that reads the environment."""

import os
from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from shopper.calc.conversion import FixedRate

Tier = Literal["small", "medium", "large"]

NEBIUS_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"
NEBIUS_KEY_NAME = "NEBIUS_TOKEN_FACTORY"

# Findings behind these choices: docs/findings/task_1.2.md. `MODEL_IDS`, at the end of this module,
# is these with what the environment overrides (docs/architecture/models.md, "Tiers").
DEFAULT_MODEL_IDS: Mapping[Tier, str] = MappingProxyType(
    {
        "small": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        "medium": "nvidia/nemotron-3-super-120b-a12b",
        "large": "nvidia/Nemotron-3-Ultra-550b-a55b",
    }
)
MODEL_ID_NAMES: Mapping[Tier, str] = MappingProxyType(
    {
        "small": "NEBIUS_MODEL_SMALL",
        "medium": "NEBIUS_MODEL_MEDIUM",
        "large": "NEBIUS_MODEL_LARGE",
    }
)
# The other small-tier candidate; used only by check_models to compare it with the small tier.
SMALL_TIER_ALTERNATIVE = "nvidia/Nemotron-3_5-Lightning"

MODEL_TIMEOUT_SECONDS = 60.0
# The Nemotron models reason before answering, and the reasoning counts as output tokens.
MODEL_MAX_TOKENS = 4000
# Sent with a call that asks for little reasoning: Nemotron 3 Super's low-effort mode, from its
# model card; Nebius passes it on (docs/findings/task_1.7.2.md).
LOW_EFFORT_REQUEST: Mapping[str, Any] = MappingProxyType(
    {"chat_template_kwargs": MappingProxyType({"enable_thinking": True, "low_effort": True})}
)


# --- Agents: the real ones, or the stubs, so a run from the browser spends one supervisor model
# call and no search or page credits. A pasted link is still read, so pair the stubs with the
# recorded sources ---

AgentsMode = Literal["real", "stubs"]
AGENTS_NAME = "SHOPPER_AGENTS"

# --- Sources: live or recorded (docs/architecture/data_sources.md, "Rules for every source") ---

SourcesMode = Literal["live", "fixtures"]
SOURCES_NAME = "SHOPPER_SOURCES"
TAVILY_KEY_NAME = "TAVILY_API_KEY"
FIRECRAWL_KEY_NAME = "FIRECRAWL_API_KEY"
TAVILY_DAILY_CREDIT_LIMIT_NAME = "TAVILY_DAILY_CREDIT_LIMIT"
DEFAULT_TAVILY_DAILY_CREDIT_LIMIT = 100

CACHE_FOLDER = Path(".cache")
FIXTURES_FOLDER = Path("tests/fixtures")
# The SQLite file the API saves its sessions in (docs/architecture/sessions.md); the
# terminal app keeps them in memory.
SESSIONS_DATABASE = CACHE_FOLDER / "sessions.sqlite"
# A stream with nothing to send for this long sends a keep-alive comment, so a proxy does not
# close it while an agent works.
KEEP_ALIVE_SECONDS = 15.0
# Postgres to save the sessions in when set (`langgraph-checkpoint-postgres`); the SQLite file
# when not.
DATABASE_URL_NAME = "DATABASE_URL"
# A session is deleted this long after its latest checkpoint (eu_market.md, "Personal data"),
# by a sweep at startup and then every interval.
SESSION_RETENTION_DAYS = 7
SWEEP_INTERVAL_SECONDS = 3600.0
# The deployment runs without endpoint auth, so a client IP may start this many sessions an
# hour; above it the API answers `too_many_sessions`.
SESSIONS_PER_IP_PER_HOUR_NAME = "SESSIONS_PER_IP_PER_HOUR"
DEFAULT_SESSIONS_PER_IP_PER_HOUR = 30
# And anyone with the URL can spend, so this many sessions may start in 24 hours, from all clients
# together; above it the API answers `too_many_sessions_today`.
SESSIONS_PER_DAY_NAME = "SESSIONS_PER_DAY"
DEFAULT_SESSIONS_PER_DAY = 100
# The proxies in front of the API that each append to `X-Forwarded-For`; 0 uses the connection's
# own address as the client's.
TRUSTED_PROXY_HOPS_NAME = "TRUSTED_PROXY_HOPS"
DEFAULT_TRUSTED_PROXY_HOPS = 0
# The origins whose pages may call the API (CORS), comma-separated; the Next.js dev server's
# when not set.
FRONTEND_ORIGINS_NAME = "FRONTEND_ORIGINS"
DEFAULT_FRONTEND_ORIGINS = ("http://localhost:3000",)

# What `POST /sessions/{id}/recalculate` takes, both ends included (calculations.md, "Changing
# the assumptions"); outside them it answers `invalid_assumptions`.
RECALCULATE_HORIZON_YEARS = (1, 30)
RECALCULATE_USES_PER_YEAR = (1, 3650)
RECALCULATE_LIFESPAN_YEARS = (Decimal("0.1"), Decimal(100))

# A 429 is retried once when it asks to wait this long or less.
MAX_RETRY_AFTER_SECONDS = 5.0

# --- Calls per analysis (data_sources.md, "Calls per analysis"). Cache hits do not count ---

BRIEF_SEARCH_LIMIT = 3
# Two listing searches (the second with the English category), and an evidence and a findings
# search for each of three options and for each of three options a slot is refilled with.
TCO_SEARCH_LIMIT = 14
PASTED_LINK_FETCH_LIMIT = 1
# The listing pages and product pages option research reads (option_research.md).
TCO_FETCH_LIMIT = 12

# --- Tavily (data_sources.md, "Tavily" and "Search purposes") ---

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT_SECONDS = 20.0
# Never "advanced" without changing data_sources.md: it doubles the credits.
TAVILY_FIXED_PARAMETERS: Mapping[str, Any] = MappingProxyType(
    {
        "search_depth": "basic",
        "auto_parameters": False,
        "max_results": 8,
        "chunks_per_source": 3,
        "topic": "general",
        "include_answer": False,
        "include_usage": True,
    }
)
NETHERLANDS = "netherlands"


class SearchPurpose(StrEnum):
    """Every search has one; it sets the country boost, the domains and how long a result lasts.

    The published footprint search of the LCA agent is added in task 1.9.
    """

    CATEGORY = "category"
    CATEGORY_CARE = "category_care"
    LISTING_PAGES = "listing_pages"
    EVIDENCE = "evidence"
    FINDINGS = "findings"


SOCIAL_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
)
VIDEO_DOMAINS = ("youtube.com", "vimeo.com", "dailymotion.com")
PINTEREST_DOMAINS = ("pinterest.com", "pinterest.nl", "pinterest.co.uk")
FORUM_DOMAINS = ("reddit.com", "quora.com")
# Every other eBay site a search may return; task 1.8 found ebay.co.uk in an evidence search.
# Excluded from the evidence search only, so the other purposes' cached searches stay valid.
OTHER_EBAY_DOMAINS = (
    "ebay.be",
    "ebay.fr",
    "ebay.it",
    "ebay.es",
    "ebay.at",
    "ebay.ie",
    "ebay.pl",
    "ebay.ch",
    "ebay.co.uk",
    "ebay.ca",
    "ebay.com.au",
)
MARKETPLACE_DOMAINS = (
    "ebay.com",
    "ebay.nl",
    "ebay.de",
    "marktplaats.nl",
    "vinted.nl",
    "aliexpress.com",
    "temu.com",
)
SHOP_DOMAINS = (
    "amazon.com",
    "amazon.nl",
    "amazon.de",
    "bol.com",
    "coolblue.nl",
    "mediamarkt.nl",
    "blokker.nl",
    "action.com",
)
# Independent testers and consumer organisations, named in the read prompts of option research
# (tasks 1.8.2 and 1.8.4). Not sent to Tavily: the live check in task 1.6 found that
# `include_domains_mode="prefer"` brought none of them into the results (data_sources.md,
# "Search purposes").
PREFERRED_TESTER_DOMAINS = (
    "consumentenbond.nl",
    "test-aankoop.be",
    "test.de",
    "which.co.uk",
    "rtings.com",
    "ifixit.com",
    "seriouseats.com",
    "wirecutter.com",
)


class ComparisonSite(BaseModel):
    """What option research knows of a comparison site (docs/findings/task_1.12.md).

    `not_listing` holds the parts of a URL that mark a result as no listing page of the whole
    category: a product page, an information page, or a listing filtered on a brand or a search
    word. `category_cut` holds the parts before which such a URL is the listing page of its
    category: a filtered list cut there stands for it (task 1.15's live kettle search found only
    beslist.nl lists filtered on a search word or a brand). A kieskeurig.nl product page is not
    cut: its path names the category of whatever matched, a football or a toy.
    `price_includes_shipping` says the offer's price is the item price plus its shipping rate;
    `new_only` that an offer stating no condition is new, because the site lists new items only.
    """

    model_config = ConfigDict(frozen=True)

    not_listing: tuple[str, ...]
    category_cut: tuple[str, ...] = ()
    price_includes_shipping: bool
    new_only: bool


# The comparison sites option research reads, by domain, in the order they are tried; the
# listing pages search is restricted to them. tweakers.net and klarna.com gave no listing page in
# task 1.12 ("Decided", item 2).
COMPARISON_SITES: Mapping[str, ComparisonSite] = MappingProxyType(
    {
        "beslist.nl": ComparisonSite(
            not_listing=("/p/", "/r/", "merk~"),
            category_cut=("/r/", "/c/"),
            price_includes_shipping=False,
            new_only=True,
        ),
        "kieskeurig.nl": ComparisonSite(
            not_listing=("/product/", "/informatie"),
            price_includes_shipping=True,
            new_only=False,
        ),
    }
)
COMPARISON_SITE_DOMAINS = tuple(COMPARISON_SITES)
_NO_SOCIAL = SOCIAL_DOMAINS + VIDEO_DOMAINS + PINTEREST_DOMAINS + FORUM_DOMAINS
_NO_SHOPPING = _NO_SOCIAL + MARKETPLACE_DOMAINS + SHOP_DOMAINS

# The parameters each purpose adds to the fixed ones.
SEARCH_PURPOSE_PARAMETERS: Mapping[SearchPurpose, Mapping[str, Any]] = MappingProxyType(
    {
        SearchPurpose.CATEGORY: MappingProxyType({"exclude_domains": _NO_SHOPPING}),
        SearchPurpose.CATEGORY_CARE: MappingProxyType(
            {"country": NETHERLANDS, "exclude_domains": _NO_SHOPPING}
        ),
        # The listing pages of the comparison sites, searched with the local category term.
        SearchPurpose.LISTING_PAGES: MappingProxyType(
            {"country": NETHERLANDS, "include_domains": COMPARISON_SITE_DOMAINS}
        ),
        # Full page text, at no extra credit: snippets gave no recurring cost in the live check
        # of task 1.8.3 (docs/findings/task_1.8.3.md).
        SearchPurpose.EVIDENCE: MappingProxyType(
            {
                "country": NETHERLANDS,
                "exclude_domains": SOCIAL_DOMAINS
                + VIDEO_DOMAINS
                + PINTEREST_DOMAINS
                + MARKETPLACE_DOMAINS
                + OTHER_EBAY_DOMAINS,
                "include_raw_content": "text",
            }
        ),
        # Retailer review pages are not fetched (product.md, "Durability evidence"); forums
        # and comparison sites are allowed, because owner reports are found there. Snippets
        # only: full page text added no correct finding in the live check of task 1.8.4
        # (docs/findings/task_1.8.4.md).
        SearchPurpose.FINDINGS: MappingProxyType(
            {
                "exclude_domains": VIDEO_DOMAINS
                + PINTEREST_DOMAINS
                + MARKETPLACE_DOMAINS
                + SHOP_DOMAINS,
            }
        ),
    }
)
# A result's full page text is cut to this length; the model reads the cut text and the quote
# check runs on it (data_sources.md, "Tavily").
RAW_CONTENT_MAX_CHARACTERS = 6000
# How long a cached search lasts; a purpose not listed does not expire.
SEARCH_CACHE_MAX_AGE: Mapping[SearchPurpose, timedelta] = MappingProxyType(
    {SearchPurpose.LISTING_PAGES: timedelta(days=1)}
)

# --- Category research (category_brief.md; data_sources.md, "Research rules") ---

# The search query of each template search; only the category is filled in. A template is written
# in the language its purpose searches in.
SEARCH_TEMPLATES: Mapping[SearchPurpose, str] = MappingProxyType(
    {
        SearchPurpose.CATEGORY: "{category} buying guide what to look for",
        SearchPurpose.CATEGORY_CARE: "{category} care maintenance and replacement parts",
    }
)
# With fewer researched factors than this, a follow-up search may run and the brief is cached
# for a day only.
ENOUGH_RESEARCHED_FACTORS = 3
THIN_BRIEF_MAX_AGE = timedelta(days=1)
# A choice is shown as one line among the question's choices, so it stays short.
MAX_CHOICE_CHARACTERS = 40
# A follow-up search query a model proposes is discarded when it is longer.
MAX_FOLLOW_UP_CHARACTERS = 120
# The read and the phrasing call reason at length before they answer, and the reasoning counts
# toward the limit: the live reads of task 1.7 used up to 7,485 tokens (models.md).
BRIEF_MAX_TOKENS = 16000
BRIEF_TIMEOUT_SECONDS = 120.0

# --- Option research (option_research.md) ---

# The listing pages search; the local category term, or the English category when the term
# stands in too few listed names, is filled in (docs/findings/task_1.12.md).
LISTING_TEMPLATE = "{term} kopen"
# The local term has to stand in at least this many names on the listing pages ("Decided",
# item 1).
MIN_NAMES_WITH_TERM = 3
# The reads stop at this many buyable candidates or at TCO_FETCH_LIMIT pages, listing pages
# included, counted cached or not; at most this many pages are read at once ("Decided", items 5
# and 6).
ENOUGH_BUYABLE = 5
MAX_READS_AT_ONCE = 3
# A product over the budget is read only when judged long by its name, and only up to this many
# times the budget; one at most.
MAX_TIMES_THE_BUDGET = 3
# On one page, an offer in stock under this share of the median of at least this many other
# offers is dropped as an outlier ("Decided", item 8; the Metabo SBE 650 at €32.95, 37%). It was
# 0.6 until task 1.15 found the WMF's €44.99 at bol.com, 58%, a real sale.
PRICE_OUTLIER_SHARE = Decimal("0.5")
MIN_OTHER_OFFERS = 3
# What the page read's quote for an item sold without a part it needs has to hold ("Decided",
# item 10): a part named missing, or the words shops use for a bare tool.
MISSING_PART_WORDS = (
    "zonder accu",
    "zonder lader",
    "zonder batterij",
    "zonder deksel",
    "zonder voet",
    "solo",
    "body",
    "basic body",
    "without battery",
    "without charger",
    "excl. accu",
    "exclusief accu",
)
# The units a product name states a size, a capacity or a power in ("24 cm", "1.7L", "18V"); a
# page whose name states none while most listed names do gets a trail note ("Decided", item 8).
SIZE_UNITS = ("cm", "mm", "l", "ltr", "liter", "litre", "ml", "v", "volt", "w", "watt", "ah")
# Colours name no product: two pans of one brand that share only "zwart" are two products (kept
# once in task 1.15's live run). Dutch and English, as product names on the comparison sites
# write them.
COLOUR_WORDS = frozenset(
    {
        *("zwart", "wit", "grijs", "antraciet", "zilver", "goud", "rood", "blauw", "groen"),
        *("geel", "oranje", "roze", "paars", "bruin", "beige", "creme", "crème"),
        *("black", "white", "grey", "gray", "anthracite", "silver", "gold", "red", "blue"),
        *("green", "yellow", "orange", "pink", "purple", "brown", "cream"),
    }
)
# The evidence search of a product option; only its name is filled in. Chosen in the live check
# of task 1.8.3 (docs/findings/task_1.8.3.md).
EVIDENCE_TEMPLATE = "{product} durability lifespan warranty"
# The findings search of a product option; only its name is filled in. Chosen in the live check
# of task 1.8.4 (docs/findings/task_1.8.4.md).
FINDINGS_TEMPLATE = "{product} long term review durability"
# At most this many findings per product option, one per cited result. The read is asked for a
# few more, since some fail the checks.
MAX_FINDINGS = 3
FINDINGS_ASKED = 5
# A finding's summary: at most this many words, and no run of this many words copied from the
# results (option_evidence.md, "Findings"). The prompt asks for one word less than the check.
MAX_SUMMARY_WORDS = 25
COPIED_RUN_WORDS = 6
FINDINGS_MAX_TOKENS = 16000
FINDINGS_TIMEOUT_SECONDS = 120.0
# An estimated lifespan is kept between these, in whole years (option_evidence.md, "Evidence").
LIFESPAN_ESTIMATE_YEARS = (1, 50)
# The EU legal guarantee says nothing about one product, so a warranty of this length or less is
# not durability evidence (docs/eu_market.md, "Guarantees and lifespan").
LEGAL_GUARANTEE_YEARS = Decimal(2)
# The fixed rates a recurring cost is converted at; any other currency is dropped
# (docs/adr/0002-fixed-rate-conversion-recurring-costs.md).
FIXED_RATES: Mapping[str, FixedRate] = MappingProxyType(
    {
        "USD": FixedRate(Decimal("1.1253"), date(2026, 10, 16), "ECB euro reference rate"),
        "GBP": FixedRate(Decimal("0.84385"), date(2026, 10, 16), "ECB euro reference rate"),
    }
)
# The evidence read reads the full page text of up to nine results.
EVIDENCE_MAX_TOKENS = 24000
EVIDENCE_TIMEOUT_SECONDS = 180.0
# The durability judgements and the page reads reason before they answer, as the brief's read
# does.
OPTION_RESEARCH_MAX_TOKENS = 16000
OPTION_RESEARCH_TIMEOUT_SECONDS = 120.0

# --- LCA tier 3 (docs/architecture/calculations.md, "CO2e of a model estimate") ---

# A model estimate's high end is at least this many times its low end (why 2: lca.md).
LCA_MIN_SPREAD = Decimal(2)
# Assumed masses are scaled to a stated weight only by a scale inside these, both included.
WEIGHT_SCALE_WINDOW = (Decimal("0.5"), Decimal(2))
# A reply that points a row at no page material, with masses summing to this many times the page's
# weight or more, may have counted that weight as a material: the option is declined.
WEIGHT_TWICE_TIMES = 1.5
# A model's factor outside these, in kg CO2e per kg, is taken for a slip of units (per tonne,
# per gram): from about wood to a printed circuit board, with room on both sides.
LCA_FACTOR_BOUNDS = (0.05, 500.0)
# One call to the large tier for every option, reasoning in full: the probe of task 1.9.7 took
# 12.5 s and 4,506 completion tokens for three options (docs/findings/task_1.9.7.md).
LCA_MAX_TOKENS = 16000
LCA_TIMEOUT_SECONDS = 60.0
# The whole estimate, the retry after invalid output included.
LCA_TIME_CAP_SECONDS = 150.0

# --- CO2e for scale (docs/architecture/calculations.md, "CO2e for scale") ---

# The average new car registered in the EU, Norway and Iceland in 2025, from the European
# Environment Agency (June 2026; provisional until manufacturers have reviewed it). A test (WLTP)
# value that counts the tailpipe only and averages in electric cars, so it gives more kilometres per
# kilogram than a real drive would, which makes the difference look larger: for scale only, not an
# equivalence, and the line says so.
CAR_CO2_GRAMS_PER_KM = Decimal("96.7")
CAR_CO2_YEAR = 2025
CAR_CO2_SOURCE_URL = (
    "https://www.eea.europa.eu/en/newsroom/news/"
    "average-co2-emissions-from-new-cars-and-vans-significantly-decreased-in-2025"
)

# --- Firecrawl, for a pasted link, listing pages and product pages (data_sources.md) ---

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"
FIRECRAWL_TIMEOUT_SECONDS = 60.0
FIRECRAWL_PARAMETERS: Mapping[str, Any] = MappingProxyType({"formats": ("markdown", "rawHtml")})
# Firecrawl answered 429 after nine reads within about a minute in task 1.12. A 429 is retried once,
# after its Retry-After up to the longest wait, or after the pause when it states none
# (docs/findings/task_1.12.md, "Decided", item 6).
FIRECRAWL_RETRY_PAUSE_SECONDS = 20.0
FIRECRAWL_MAX_RETRY_AFTER_SECONDS = 60.0
PAGE_CACHE_MAX_AGE = timedelta(days=1)
# The page text the model reads for materials and weight is cut to this length; the product's
# own description comes near the top of a shop page.
PAGE_TEXT_MAX_CHARACTERS = 12000


# --- LangSmith tracing, a developer tool (eu_market.md, "Personal data") ---

LANGSMITH_TRACING_NAME = "LANGSMITH_TRACING"
LANGSMITH_KEY_NAME = "LANGSMITH_API_KEY"
LANGSMITH_PROJECT_NAME = "LANGSMITH_PROJECT"
DEFAULT_LANGSMITH_PROJECT = "true-cost-copilot"
LANGSMITH_EU_URL = "https://eu.api.smith.langchain.com"


class TracingSettings(BaseModel):
    """What LangSmith is given in code when tracing is on, so it never reads its own settings
    from the environment."""

    model_config = ConfigDict(frozen=True)

    api_key: str
    project: str
    endpoint: str = LANGSMITH_EU_URL


class MissingSettingError(RuntimeError):
    """A required environment variable is absent or empty."""


class InvalidSettingError(RuntimeError):
    """An environment variable holds a value the app cannot use."""


def load_env(
    dotenv_path: Path = Path(".env"), environ: Mapping[str, str] | None = None
) -> Mapping[str, str]:
    """Values from the .env file, overridden by the process environment."""
    process_env = os.environ if environ is None else environ
    return {**_read_dotenv(dotenv_path), **process_env}


def require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise MissingSettingError(f"{name} is not set. Add it to .env (see .env.example).")
    return value


def model_ids(env: Mapping[str, str]) -> Mapping[Tier, str]:
    """Each tier's model: the one the environment names, or the default when unset or empty."""
    return MappingProxyType(
        {
            tier: env.get(MODEL_ID_NAMES[tier], "").strip() or default
            for tier, default in DEFAULT_MODEL_IDS.items()
        }
    )


def agents_mode(env: Mapping[str, str]) -> AgentsMode:
    """The real agents by default; the stubs only when chosen explicitly."""
    value = env.get(AGENTS_NAME, "").strip()
    if value in ("", "real"):
        return "real"
    if value == "stubs":
        return "stubs"
    raise InvalidSettingError(f"{AGENTS_NAME} must be real or stubs.")


def sources_mode(env: Mapping[str, str]) -> SourcesMode:
    """Live by default; recorded responses only when chosen explicitly."""
    value = env.get(SOURCES_NAME, "").strip()
    if value in ("", "live"):
        return "live"
    if value == "fixtures":
        return "fixtures"
    raise InvalidSettingError(f"{SOURCES_NAME} must be live or fixtures.")


def tavily_daily_credit_limit(env: Mapping[str, str]) -> int:
    return _whole_number(env, TAVILY_DAILY_CREDIT_LIMIT_NAME, DEFAULT_TAVILY_DAILY_CREDIT_LIMIT)


def sessions_per_ip_per_hour(env: Mapping[str, str]) -> int:
    return _whole_number(env, SESSIONS_PER_IP_PER_HOUR_NAME, DEFAULT_SESSIONS_PER_IP_PER_HOUR)


def sessions_per_day(env: Mapping[str, str]) -> int:
    return _whole_number(env, SESSIONS_PER_DAY_NAME, DEFAULT_SESSIONS_PER_DAY)


def trusted_proxy_hops(env: Mapping[str, str]) -> int:
    return _whole_number(env, TRUSTED_PROXY_HOPS_NAME, DEFAULT_TRUSTED_PROXY_HOPS)


def database_url(env: Mapping[str, str]) -> str | None:
    """The Postgres database the sessions are saved in; none for the SQLite file."""
    return env.get(DATABASE_URL_NAME, "").strip() or None


def frontend_origins(env: Mapping[str, str]) -> tuple[str, ...]:
    origins = tuple(
        origin.strip() for origin in env.get(FRONTEND_ORIGINS_NAME, "").split(",") if origin.strip()
    )
    return origins or DEFAULT_FRONTEND_ORIGINS


def tracing_settings(env: Mapping[str, str]) -> TracingSettings | None:
    """Off unless set to true; on, the key is required and the project has a default."""
    value = env.get(LANGSMITH_TRACING_NAME, "").strip().lower()
    if value in ("", "false"):
        return None
    if value != "true":
        raise InvalidSettingError(f"{LANGSMITH_TRACING_NAME} must be true or false.")
    project = env.get(LANGSMITH_PROJECT_NAME, "").strip() or DEFAULT_LANGSMITH_PROJECT
    return TracingSettings(api_key=require(env, LANGSMITH_KEY_NAME), project=project)


def _whole_number(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name, "").strip()
    if not value:
        return default
    if not value.isdigit():
        raise InvalidSettingError(f"{name} must be a whole number.")
    return int(value)


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    pairs = (
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    return {name.strip(): value.strip().strip("'\"") for name, value in pairs}


# The model each tier calls, for every caller, the trail and the traces alike.
MODEL_IDS: Mapping[Tier, str] = model_ids(load_env())
