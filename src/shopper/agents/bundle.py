"""The four agent functions the graph runs and the reply's reader, as one bundle, and what each
returns.

`build_graph` in graph.py takes the bundle, so a test passes its own agents; `resume_with_reply`
in sessions.py takes it for the reader. The functions take the model client and their tools as
plain arguments and know nothing of the graph or of LangGraph. A tool is a freshly limited view,
made each time the agent's node runs.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from shopper.llm import ChatModel
from shopper.state import (
    Answer,
    DecisionFactor,
    DomainModel,
    LcaResult,
    Listing,
    ProductOption,
    Question,
    Request,
    TrailEntry,
    Warning,
)
from shopper.tools.brief_store import BriefStore
from shopper.tools.results import PageFetch, WebSearch


class BriefOutput(DomainModel):
    """The decision factors, the questions drawn from them, the answers already stated, and the
    local category term, which option research searches for.

    `phrased_questions` holds every question category research phrased, asked or not, so an
    answer to a factor not asked can still be read against its question's choices; the usage
    question is never among them.
    """

    factors: tuple[DecisionFactor, ...] = ()
    questions: tuple[Question, ...] = ()
    phrased_questions: tuple[Question, ...] = ()
    stated_answers: tuple[Answer, ...] = ()
    local_term: str | None = None
    trail: tuple[TrailEntry, ...] = ()
    warnings: tuple[Warning, ...] = ()


class TcoOutput(DomainModel):
    """The product options, the linked product first when there is one."""

    options: tuple[ProductOption, ...] = ()
    trail: tuple[TrailEntry, ...] = ()
    warnings: tuple[Warning, ...] = ()


class LcaOutput(DomainModel):
    """An option with no estimate has no result."""

    results: tuple[LcaResult, ...] = ()
    trail: tuple[TrailEntry, ...] = ()
    warnings: tuple[Warning, ...] = ()


class SecondHandOutput(DomainModel):
    listings: tuple[Listing, ...] = ()
    trail: tuple[TrailEntry, ...] = ()
    warnings: tuple[Warning, ...] = ()


class ReplyOutput(DomainModel):
    """What the reply was read to say: an answer per factor it speaks to, those of the user's
    own factors it adds first, and the factors it adds. `answered_by_the_request` says a phrase
    was about a factor the request already answers, and `asks_to_change_request` that one asked
    to change the category or the budget; both phrases are on the trail only."""

    answers: tuple[Answer, ...] = ()
    factors: tuple[DecisionFactor, ...] = ()
    answered_by_the_request: bool = False
    asks_to_change_request: bool = False
    trail: tuple[TrailEntry, ...] = ()


class ReplyUnreadError(Exception):
    """The reply could not be read: its model call failed twice. Nothing is resumed."""


# The second argument is the linked product: present only when a pasted link was read.
BriefAgent = Callable[
    [Request, ProductOption | None, ChatModel, WebSearch, BriefStore], Awaitable[BriefOutput]
]
# The arguments after the request: the linked product (when a pasted link was read), the local
# category term (when category research found one), the decision factors, the questions and the
# answers; last the page fetch that reads the listing and product pages. It returns the linked
# product among its options.
TcoAgent = Callable[
    [
        Request,
        ProductOption | None,
        str | None,
        Sequence[DecisionFactor],
        Sequence[Question],
        Sequence[Answer],
        ChatModel,
        WebSearch,
        PageFetch,
    ],
    Awaitable[TcoOutput],
]
LcaAgent = Callable[[Sequence[ProductOption], ChatModel], Awaitable[LcaOutput]]
SecondHandAgent = Callable[
    [Request, Sequence[Answer], Sequence[ProductOption], ChatModel], Awaitable[SecondHandOutput]
]
# The reply's reader, run before the graph resumes, never as a node. The arguments after the
# request and the reply: the decision factors, the questions asked, every question phrased (asked
# or not), the answers the request states and the local category term. It raises
# ReplyUnreadError when the reply could not be read.
ReplyAgent = Callable[
    [
        Request,
        str,
        Sequence[DecisionFactor],
        Sequence[Question],
        Sequence[Question],
        Sequence[Answer],
        str | None,
        ChatModel,
    ],
    Awaitable[ReplyOutput],
]


@dataclass(frozen=True)
class AgentBundle:
    brief: BriefAgent
    tco: TcoAgent
    lca: LcaAgent
    second_hand: SecondHandAgent
    reply: ReplyAgent
