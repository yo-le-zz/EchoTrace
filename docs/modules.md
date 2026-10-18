# Writing a module

A module is a class in `src/echotrace/modules/` that subclasses `BaseModule`.

```python
import aiohttp

from echotrace.modules.base import BaseModule, OsintResult, ProgressCallback, fetch


class ExampleModule(BaseModule):
    name = "example"                       # stored with each result
    description = "Short label shown in the log"
    requires = ["domaine"]                 # runs if at least one of these fields is filled

    async def run(self, target_data: dict, session: aiohttp.ClientSession,
                  progress_cb: ProgressCallback | None = None) -> list[OsintResult]:
        domain = target_data["domaine"]
        response = await fetch(session, f"https://{domain}/humans.txt")
        if response is None or response.status != 200:
            return []
        if progress_cb:
            progress_cb("humans.txt trouvé", 100)
        return [OsintResult(module=self.name, platform="Site", url=response.url,
                            title="humans.txt", confidence=0.5)]
```

Then register it in `ALL_MODULES` (`modules/__init__.py`).

## Rules

- Use `fetch()` (verified TLS, size cap, proxy support, returns `None` on network errors). It does not
  swallow `asyncio.CancelledError`, which the stop button relies on.
- Never put unescaped scraped text in HTML yourself: the report generator escapes everything.
- Only return a result when the data really appears in the page; do not report "probably found".
- Confidence comes from `compute_result_confidence(module, checks)` with the checks in
  `core/scorer.CHECK_WEIGHTS`. Confidence is 0.0 for informational rows (hashes, manual leads).
- Report progress with `progress_cb(message, percent)`, percent being the module's own 0-100.
- Be polite: use `random_delay()` between requests to the same service.
- Raise nothing for "not found". Unexpected exceptions are caught by the engine and shown in the log.

## Sites and plugins without touching the code

- Username sites live in `modules/data/sites.json` (`check`, `marker`, `reliability`, `probe`,
  `known_user`). Users extend it with `<config folder>/sites.json`; invalid entries are logged and
  skipped. `scripts/check_sites.py` verifies the catalogue against the real sites.
- A user plugin is a `.py` file in `<config folder>/plugins/` containing `BaseModule` subclasses
  (files starting with `_` and broken files are ignored). The engine loads built-in modules first.

## Testing

Test parsing and decision logic with plain functions (see `tests/test_modules.py`); avoid tests that
need the network. For engine behaviour, use fake modules like in `tests/test_engine.py`.
