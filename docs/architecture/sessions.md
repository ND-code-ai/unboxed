# Sessions

Read this when working on the pause for the user's answers, the functions in `graph/sessions.py`
and `graph/graph.py` that the entry points call, progress events, reading a saved session, or the
session errors. The agents, the graph's nodes and the shared state are in `agents.md`.

## The pause

After the brief agent, the graph stops and its state is saved under a session id.
It resumes when answers arrive, or when the user skips. Use LangGraph's own interrupt and
checkpoint mechanism; do not build a second state store. Skipping everything is a valid answer
and must produce a full report.

The pause is its own node, `interview`: it calls `interrupt()`, is resumed with an
`InterviewAnswers` (`state.py`: the answers picked, the answers read in the reply, the user's own
factors the reply adds and the reply's trail entries), and writes the complete set: the `stated`
answers the brief agent recorded, the reply's answers to factors not asked (its own factors'
first), then one per question (the strongest: `chosen`, then the reply's `stated` or `not_sure`,
then a `not_sure` picked, or `skipped` for a question with no answer; "skip all" is no answers, so
every one is `skipped`). A factor with no question and no stated value gets no answer. It writes
`factors` in full, the reply's own factors after the request's and before usage, and the reply's
trail entries. Uses per
year in `assumptions` comes from the answer to the factor of kind `usage`: copied from the chosen
choice, or from a `stated` answer, where code put it (never the model, never the caller);
otherwise it is missing. Turning the answers into the complete set is a pure function
the node calls, tested directly. It pauses even when there are no questions: the pause is also
where the user sees what was understood and can start again, so every request that runs pauses
exactly once, and resuming with no answers gives the report. LangGraph runs the node again from its start on resume, so it does
nothing before `interrupt()` that may not be repeated. The reply is read before the graph
resumes, never in a node: a node that raised would have saved the answers as its resume value.

## The functions the entry points call

The entry points call the eight functions below and nothing else from `graph/`; the terminal app
uses `memory_checkpointer`, `build_graph`, `start_session` and `resume_session`. `graph.py`
holds the three that build the graph and its checkpointer, beside the state type, the node names,
the progress types (`Progress` and `ProgressStatus`) and `run_graph`, which runs the graph with
its progress events and which only `sessions.py` calls. `sessions.py` holds the five that take a
session id, and what they return and raise: `SessionStart`, the saved session's three shapes, the
two outcomes of a reply (`ResumedWithReply` and `ReplyUnanswered`, each with a `ReplyRead`) and
the session errors below.

| Module | Name | What it does |
|---|---|---|
| `graph.py` | `state_serde()` | The serializer every checkpointer saves the state with, with the allow-list below. The API's saved checkpointer is an `AsyncSqliteSaver` (`langgraph-checkpoint-sqlite`) on the file `SESSIONS_DATABASE` in `config.py`, made with this serde (task 2.5.1) |
| `graph.py` | `memory_checkpointer()` | An in-memory checkpointer for the CLI and tests, which are one process |
| `graph.py` | `build_graph(chat, checkpointer, sources, agents)` | Builds the graph once per process. `sources` holds the services behind the tools, live or their fixture twins (`tools/sources.py`). `agents` is a frozen bundle of the four agent functions (brief, TCO, LCA, second-hand) and the reply's reader, so a test passes its own without faking code in the repo; the default is `DEFAULT_AGENTS` (`agents/default.py`): each real agent there is and the stub of every other one. The model client and sources are bound to the nodes here; each time a node runs it makes its agent a freshly limited view of its tool (`data_sources.md`, "Calls per analysis") and logs the credits that view used. The functions in `agents/` take the client and the tool as plain arguments and import nothing from LangGraph. The brief and TCO agents take the web search, and the TCO agent the page fetch too (the product pages); the LCA agent takes none, because tier 3 searches nothing (tier 1, an optional layer, would add it); the brief agent also takes the brief store, made from the sources' cache folder and clock (`tools/brief_store.py`); the second-hand agent takes no tool until the eBay task |
| `sessions.py` | `start_session(graph, session_id, input, understood, progress)` | Async. Returns a `SessionStart`: session id, request, warnings, the decision factors, the questions, the answers the request states, and the report when the graph finished without pausing, which is only a request that does not run. The optional `understood` is called with the request once it is known to run, before category research starts, so the caller can show it while the research runs |
| `sessions.py` | `resume_session(graph, session_id, answers, progress)` | Async. Takes `Answer`s with status `chosen` or `not_sure` and returns the report. Runs `check_resume` first |
| `sessions.py` | `resume_with_reply(graph, session_id, answers, reply, chat, agents, progress, *, reading, replied)` | Async. As `resume_session`, with the user's reply read first by the bundle's reader with the saved factors, questions, phrased questions, stated answers and local term (`reading_answers.md`, "The reply"); a blank reply is none. Returns a `ResumedWithReply`, with what the reply gave (a `ReplyRead`: its answers that count, the factors it added, whether it asked to change the request, and whether it answered only what a choice picked or the request already answers) and the report, or a `ReplyUnanswered` when no answer was picked and the reply gave none: then nothing is resumed and the session stays paused, its `ReplyRead` marked `unanswered`, and `has_questions` says whether the session paused with questions (the API words `reply_unanswered` by it, task 3.1.5). The optional `reading` is called as the reading starts and finishes, and `replied` with the `ReplyRead` and the paused session's request and decision factors once the reply is read, before any agent starts (task 2.5.6), so the reply's lines can name the saved factors and those it adds (task 3.1.5); neither is called for a blank reply |
| `sessions.py` | `check_resume(graph, session_id, answers)` | Async. Raises what resuming would (below) and runs nothing, so a caller can refuse before a run starts |
| `sessions.py` | `read_session(graph, session_id)` | Async. The saved session, or nothing for an unknown id (below) |

The session id is the LangGraph thread id. The caller of `start_session` makes a new one each
time, so two sessions never share a thread, and it knows the session even when the start
raises.

## Progress

The optional `progress` of `start_session`, `resume_session` and `resume_with_reply` is called with an
`Agent` and a status: `started` when the agent's first node starts, `finished` when its last
ends without raising. `parse_request`, `read_link` and `assemble_report` are the supervisor, so it
starts at `parse_request` and finishes after `assemble_report`; `interview` is no agent. The LCA
and second-hand agents run at once, so their events interleave. A start reports the supervisor
starting and the brief agent starting and finishing; a resume the other three agents and the
supervisor finishing; a request that does not run the supervisor only. The words for each status
are in `wording.py` (`STARTED` and `FINISHED`); the terminal
app prints only the agents starting, the API sends both.

## Reading a saved session

`read_session` gives a `PausedSession` with the `SessionStart` when
the session waits for answers; a `FinishedSession` with the report when it holds one, a request
that did not run included; an `InterruptedSession` with the code `run_stopped` when it does
neither (a run stopped by a restart or an unexpected exception, or a parsing call that failed);
or nothing for an unknown id. Whether a run is going on now only the API knows (task 2.5.3). A
session saved before a model in `state.py` changed reads as not found, and resuming it raises
`SessionNotFoundError`: the checkpointer gives such a model back built without validation, so
the reloaded state is validated against today's models first. The sweep removes it 7 days
after its newest checkpoint, as it removes every session (`service_architecture.md`, "The app").
`read_report` gives a finished session's report, for a recalculation; it raises
`SessionNotFoundError` for an unknown id and `SessionHasNoReportError` for a session that is
paused or interrupted.

A checkpointer restores models and enums by class from an allow-list. The list is collected by
code from `state.py` (every domain model and every enum), never written by hand, because a class
missing from it comes back as a plain dict without an error. A parametrised generic model
(`Sourced[Decimal]`) is restored only inside another model, which is where it is used; it is
never a value of a state key on its own. The round trip is tested for a sample of every state
type (`tests/test_checkpointer.py`).

## Errors

`start_session` raises the supervisor's two typed errors unchanged (`supervisor.md`); no
report exists then. `check_resume`, and `resume_session` and `resume_with_reply` through it, read
the saved state before the graph runs and raise `SessionNotFoundError` for an unknown session id
(or one that no longer loads) and `SessionNotPausedError` for a session that is not waiting for
answers. Waiting means the pending step is `interview` and it holds an
interrupt; a finished session and one whose parsing call failed are both not waiting. Answers
are a programming error (`InvalidAnswersError`, a `ValueError` of its own, so a database error is
never taken for one) when one names a factor with no question or a choice that
is not on its question, when two are for the same factor, when a status is not `chosen` or
`not_sure`, when one says it is from the reply, or when one carries its own uses per year: the
caller asks the user again before calling. The session stays paused and can be resumed again. A
factor has at most one question. `resume_with_reply` checks the answers picked before the reply is
read, then the combined set (the reply's answers are checked against every phrased question)
before it resumes. When the reading fails twice it raises the reader's `ReplyUnreadError`
unchanged; the graph does not resume and nothing more is spent.
`check_resume` checks the answers, before the graph runs, with the same pure function the node
calls: LangGraph saves a resume value once `interrupt()` has returned it, so an answer
the node rejected would be handed to the node again on the next resume, whatever the caller
sent.
