# Graph diagram

A figure for people. The graph is described in `agents.md` ("The graph"); this file adds nothing
to it, so no task needs to read it.

The nodes and edges as `build_graph` in `src/shopper/graph/graph.py` wires them. A dotted line is a
conditional edge. To print the diagram LangGraph derives from the code, for
comparison: `build_graph(chat, memory_checkpointer(), fixture_sources()).get_graph().draw_mermaid()`.

```mermaid
flowchart TD
    start([Input]) --> parse[parse_request<br/>supervisor, small model]
    parse -. product link .-> read_link[read_link<br/>supervisor: the page at the link]
    parse -. request does not run .-> assemble
    parse -. request runs .-> brief[brief<br/>decision factors and questions]
    read_link -. request does not run .-> assemble
    read_link -. request runs .-> brief
    brief --> interview{{interview<br/>pause for the user's answers}}
    interview --> tco[tco<br/>product options]
    tco --> lca[lca<br/>CO2e per option]
    tco --> second_hand[second_hand<br/>used listings]
    lca --> assemble[assemble_report<br/>calc/ computes every number]
    second_hand --> assemble
    assemble --> done([Report])
```
