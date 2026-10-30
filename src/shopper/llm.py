"""Model client for Nebius Token Factory. Callers ask for a tier, never a model name."""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

import httpx
import openai
from langsmith.wrappers import wrap_openai
from pydantic import BaseModel, ConfigDict, ValidationError

from shopper.config import (
    LOW_EFFORT_REQUEST,
    MODEL_IDS,
    MODEL_MAX_TOKENS,
    MODEL_TIMEOUT_SECONDS,
    NEBIUS_BASE_URL,
    Tier,
)

RETRY_PROMPT = (
    "That answer did not match the required JSON schema:\n{error}\n"
    "Answer again with only the corrected JSON object."
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: Tier
    model: str
    messages: tuple[dict[str, str], ...]
    json_schema: dict[str, Any] | None = None
    timeout: float = MODEL_TIMEOUT_SECONDS
    max_tokens: int = MODEL_MAX_TOKENS
    temperature: float | None = None
    # Little reasoning before the answer; the default reasons in full.
    low_effort: bool = False


# The name of a model call's run in a trace.
NEBIUS_RUN_NAME = "nebius_chat"


class ChatError(Exception):
    """The model service failed to answer. Raised only by a ChatModel."""


class ChatTimeoutError(ChatError):
    """The model service did not answer within the request's timeout."""


ChatModel = Callable[[ChatRequest], Awaitable[str]]


def nebius_chat(api_key: str, http_client: httpx.AsyncClient | None = None) -> ChatModel:
    """The real ChatModel: Nebius Token Factory through its OpenAI-compatible API.

    Each call is a child run of the current trace when tracing is on (`tracing.py`), with its
    tier, request arguments, reply and tokens; the run is named after the schema the call asks
    for, and tagged with its tier and reasoning. A test passes an `http_client` with a fake
    transport.
    """
    # `max_retries=1` sends a request that timed out, or met a connection error, a rate limit or
    # a server error, once more; a call that times out twice is a timeout (task 1.11).
    client = wrap_openai(
        openai.AsyncOpenAI(
            base_url=NEBIUS_BASE_URL, api_key=api_key, max_retries=1, http_client=http_client
        ),
        chat_name=NEBIUS_RUN_NAME,
    )

    async def chat(request: ChatRequest) -> str:
        """Send one request and return the answer text; raises ChatError on failure."""
        try:
            response = await client.chat.completions.create(
                model=request.model,
                messages=list(request.messages),
                max_tokens=request.max_tokens,
                timeout=request.timeout,
                **_response_format(request.json_schema),
                **_temperature(request.temperature),
                **_effort(request.low_effort),
                langsmith_extra=_run_details(request),
            )
        except openai.APITimeoutError as error:
            raise ChatTimeoutError(f"no answer within {request.timeout:.0f} s") from error
        except openai.OpenAIError as error:
            raise ChatError(f"{type(error).__name__}: {error}") from error
        return response.choices[0].message.content or ""

    return chat


def _run_details(request: ChatRequest) -> dict[str, Any]:
    """The name, tags and metadata of the call's run in a trace; LangSmith's wrapper takes them
    out of the request before it is sent."""
    schema = (request.json_schema or {}).get("title")
    name = NEBIUS_RUN_NAME if schema is None else f"{NEBIUS_RUN_NAME} · {schema}"
    reasoning = "little-reasoning" if request.low_effort else "full-reasoning"
    return {"name": name, "tags": [request.tier, reasoning], "metadata": {"tier": request.tier}}


def _response_format(json_schema: dict[str, Any] | None) -> dict[str, Any]:
    """The extra request arguments that ask for JSON matching the schema, if one is given."""
    if json_schema is None:
        return {}
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": json_schema, "strict": True},
        }
    }


def _temperature(temperature: float | None) -> dict[str, Any]:
    """The extra request argument for a temperature, if one is given."""
    return {} if temperature is None else {"temperature": temperature}


class Completion[T](BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: Tier
    model: str
    value: T


class LlmFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: Tier
    model: str
    kind: Literal["timeout", "error", "invalid_output"]
    detail: str


def _effort(low_effort: bool) -> dict[str, Any]:
    """The extra request argument that asks for little reasoning, if the call wants it."""
    if not low_effort:
        return {}
    return {"extra_body": {name: dict(value) for name, value in LOW_EFFORT_REQUEST.items()}}


async def complete(
    chat: ChatModel, tier: Tier, prompt: str, *, system: str | None = None
) -> Completion[str] | LlmFailure:
    """Ask the tier's model for free text. A service failure is returned, not raised."""
    request = ChatRequest(tier=tier, model=MODEL_IDS[tier], messages=_messages(prompt, system))
    reply = await _ask(chat, tier, request)
    if isinstance(reply, LlmFailure):
        return reply
    return Completion(tier=tier, model=request.model, value=reply)


async def complete_structured[T: BaseModel](
    chat: ChatModel,
    tier: Tier,
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    temperature: float | None = None,
    max_tokens: int = MODEL_MAX_TOKENS,
    timeout: float = MODEL_TIMEOUT_SECONDS,
    low_effort: bool = False,
) -> Completion[T] | LlmFailure:
    """Ask the tier's model for an instance of `schema`.

    Output that fails validation is retried once with the validation error in the prompt;
    a second failure is returned as an `invalid_output` failure. `max_tokens` counts the
    model's reasoning too, so a long input may need more than the default. `low_effort` asks
    for little reasoning, which the medium tier honours (models.md).
    """
    request = ChatRequest(
        tier=tier,
        model=MODEL_IDS[tier],
        messages=_messages(prompt, system),
        json_schema=schema.model_json_schema(),
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
        low_effort=low_effort,
    )
    reply = await _ask(chat, tier, request)
    if isinstance(reply, LlmFailure):
        return reply
    try:
        return Completion(tier=tier, model=request.model, value=_parse(reply, schema))
    except ValidationError as first_error:
        retry = request.model_copy(
            update={"messages": (*request.messages, *_correction(reply, first_error))}
        )
    reply = await _ask(chat, tier, retry)
    if isinstance(reply, LlmFailure):
        return reply
    try:
        return Completion(tier=tier, model=request.model, value=_parse(reply, schema))
    except ValidationError as second_error:
        return LlmFailure(
            tier=tier, model=request.model, kind="invalid_output", detail=str(second_error)
        )


def _parse[T: BaseModel](reply: str, schema: type[T]) -> T:
    """Validate the model's JSON reply against the schema; raises ValidationError."""
    return schema.model_validate_json(_strip_code_fence(reply))


def _strip_code_fence(reply: str) -> str:
    """Remove a Markdown code fence around the reply, which some models add to JSON."""
    text = reply.strip()
    if not text.startswith("```"):
        return text
    return text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def _correction(reply: str, error: ValidationError) -> tuple[dict[str, str], ...]:
    """The messages appended for the retry: the invalid reply and a request to fix it."""
    return (
        {"role": "assistant", "content": reply},
        {"role": "user", "content": RETRY_PROMPT.format(error=error)},
    )


async def _ask(chat: ChatModel, tier: Tier, request: ChatRequest) -> str | LlmFailure:
    """Call the model and turn a timeout or service error into an LlmFailure."""
    try:
        return await chat(request)
    except ChatTimeoutError as error:
        return LlmFailure(tier=tier, model=request.model, kind="timeout", detail=str(error))
    except ChatError as error:
        return LlmFailure(tier=tier, model=request.model, kind="error", detail=str(error))


def _messages(prompt: str, system: str | None) -> tuple[dict[str, str], ...]:
    """The chat messages for a prompt, with the system message first when given."""
    system_messages = ({"role": "system", "content": system},) if system else ()
    return (*system_messages, {"role": "user", "content": prompt})
