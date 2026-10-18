# Usage

## Usernames

Type one or several usernames in the **Pseudo(s)** field, separated by `;`
(`yolezz ; yo_le_zz`). The CLI takes `--pseudo` several times.

### Automatic variants

`yolezz` is also tried as `yo_le_zz`, `yo-le-zz`, `yo.le.zz`, `yo_lezz`, `yole.zz`..., then with
common prefixes/suffixes and "leet" substitutions. A separated name works the other way round:
`yo_le_zz` also tries `yolezz`. Syllables are a heuristic (vowel groups), not a dictionary.
The number of variants is `max_username_variations` (profile "complet" tests 30).

A variant never scores as high as the exact name, and the sites that answer 200 for anything
(Instagram, LinkedIn...) are marked *low reliability* and capped.

### Wildcard mode

End the username with a dot (`yolezz.`), or write `yolezz.*` / `yolezz.{}` (`yolezz_*` for an
underscore, `yolezz*` for no separator):

1. DuckDuckGo and Bing are searched for `"yolezz.*"`, `"yolezz."`...; every handle of the form
   `yolezz.<word>` found in titles, snippets and URLs is kept;
2. a list of common suffixes is added (`official`, `dev`, `secret`, `backup`, `yt`, `2`...);
3. each candidate is then checked on the sites like any other username.

A plain trailing `_` or `-` is a normal username, because `alice_` exists.

### Two passes

With `two_pass` (default), every candidate is first tested on ~14 fast, reliable "probe" sites. Only
candidates that exist somewhere (and the exact name) are tested on the other sites, which divides the
number of requests by roughly 4. The profile "complet" disables it.

## Photos

Add several files or URLs. For each one: size, hashes, faces counted (with the `image` extra), and
for URLs, links to Google Lens, Yandex and Bing to open yourself. Two photos that are the same image
are reported. When profiles are verified, a profile picture that matches one of your photos
(perceptual hash, tolerant to resizing and recompression) adds +0.30 confidence.

## Reading the results

| Column | Meaning |
|---|---|
| Confiance | 0-1; username hits start from the site reliability, verification adds evidence |
| Indices | what the profile page showed: name, company, city, same picture; or "profil non vérifiable" |
| Statut | confirmed / to check / false positive (right click) |
| Note | free text, kept with the analysis |

A *false positive* is remembered for that target (same username/email/phone/name): the same URL is
not proposed again next time. Marking the result differently restores it.

## Comparing and rescanning

History tab: select two analyses and **Comparer** shows what appeared, disappeared or changed.
`echotrace-cli rescan <id>` runs the same target again and prints the diff; its exit code is `3`
when something new appeared, so a scheduled task (cron, Windows Task Scheduler) can alert you.
Schedule it only on yourself or someone who agreed: see [privacy.md](privacy.md).

## Command line

```
echotrace-cli purposes                       # the five accepted purposes
echotrace-cli run --pseudo X --email Y --purpose 1 --export html,pdf --out ./reports
echotrace-cli list | show ID | diff OLD NEW | rescan ID
echotrace-cli purge --days 30 | export-data FILE | erase --yes
```

Exit codes: 0 ok, 1 error, 2 invalid input, 3 new results since the previous analysis.

## Adding sites and plugins

- `<config folder>/sites.json` uses the same format as `src/echotrace/modules/data/sites.json`; an
  entry with the same name replaces the bundled one. `uv run python scripts/check_sites.py` checks
  that every site behaves (a random username must *not* be found).
- `<config folder>/plugins/*.py`: any `BaseModule` subclass is loaded. Plugins run with your
  privileges: only install code you trust. See [modules.md](modules.md).
