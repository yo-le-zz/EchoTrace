# Configuration

Settings are edited in the app (**Configuration**) and stored in `echotrace_config.json` inside the
per-user config directory (file mode 600 on Linux/macOS, since it can hold API keys).
Unknown keys are ignored, so files stay compatible across versions.

| Key | Default | Meaning |
|---|---|---|
| `hibp_api_key` | `""` | HaveIBeenPwned v3 key. Without it the breach check is skipped |
| `hunter_api_key`, `github_token` | `""` | Reserved for future modules, currently unused |
| `request_timeout` | 10 | Seconds per request |
| `request_delay_min` / `request_delay_max` | 0.3 / 1.5 | Random pause between search-engine requests |
| `max_concurrent` | 25 | Parallel username checks (1-200) |
| `use_proxies`, `proxy_list` | false, [] | One proxy URL picked at random per request |
| `cache_enabled`, `cache_ttl_hours` | true, 24 | Cache of username checks |
| `min_score_required` | 100 | Input score needed to start an analysis |
| `confidence_threshold` | 0.0 | Initial minimum confidence shown in the results (0 = everything) |
| `max_username_variations` | 10 | Spelling variations tested per username (wildcard mode adds up to 30 more) |
| `profile` | `equilibre` | Last applied preset: `rapide`, `equilibre`, `complet`, `discret` (see `PROFILES` in `config/settings.py`) |
| `two_pass` | true | Variants on probe sites first, then on all sites if they exist |
| `verify_profiles` | true | Re-read found profiles to look for name/company/city/same-picture evidence |
| `per_host_limit` | 3 | Simultaneous requests to a single site |
| `retention_days` | 90 | Analyses older than this are deleted at startup (0 = keep forever) |
| `export_dir` | `""` | Export folder; empty means `Documents/EchoTrace` |

`theme` and `language` are stored but only the default (Catppuccin Macchiato, French) exists.

## Input score

Each filled field adds points (`config/fields.py`): email 90, phone 80, photo 70, username 50,
last name 40, GitHub 40, ... An analysis needs at least two fields and `min_score_required` points.

## Environment

- `ECHOTRACE_HOME`: store config, data, cache, logs and exports under this single folder.

## Export / import

The dialog can export the settings to share them: API keys are replaced by a mask and are never
imported back.
