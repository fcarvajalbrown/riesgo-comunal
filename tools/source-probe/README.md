# source-probe

Reports how a source URL answers different clients: the bare tool User-Agent, a `Mozilla/5.0 (compatible; ...)` User-Agent, a full browser header set and, with `--browser`, headless Chromium. The first line is the public IP the requests left from, so a run on a GitHub runner shows whether a source blocks cloud addresses.

Run from `backend/`:

```
uv run python ../tools/source-probe/probe.py https://www.snamchile.cl/index.php --browser
```

On a GitHub runner, run the `source-probe` workflow from the Actions tab with the URL as input.
