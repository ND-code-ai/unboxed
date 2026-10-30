# Findings from task 1.6: the live check of the sources

Run with `uv run python -m shopper.check_sources "<product page URL>"`: the search query "best
frying pan tested" with the discovery parameters and `country="netherlands"`, with and without
the preferred list, then one page.

- Each search cost 1 credit and returned 7 and 8 results, with `content` of 136 to 1,489
  characters.
- `country="netherlands"` is accepted, but every result was an English-language site from
  the UK or the US. For an English search query the boost does not bring Dutch sources; task
  1.8 weighs this when it decides discovery's country.
- `include_domains_mode="prefer"` is accepted and changed three of the seven results, but no
  preferred site appeared in either list, so discovery no longer passes the list
  (`data_sources.md`, "Search purposes").
