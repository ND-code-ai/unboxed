"""The agents the entry points run: each real agent there is, and the stub of every other one.

A test passes its own bundle to `build_graph`; `STUB_AGENTS` stays whole for the tests that want
fixed data.
"""

from dataclasses import replace

from shopper.agents.brief.agent import research_brief
from shopper.agents.brief.reply import read_reply
from shopper.agents.lca.agent import estimate_co2e
from shopper.agents.stubs import STUB_AGENTS
from shopper.agents.tco.agent import research_options

DEFAULT_AGENTS = replace(
    STUB_AGENTS,
    brief=research_brief,
    tco=research_options,
    lca=estimate_co2e,
    reply=read_reply,
)
