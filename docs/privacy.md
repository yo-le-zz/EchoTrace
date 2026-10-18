# Privacy and legal notes

This page explains how EchoTrace is built to stay on the right side of data-protection law and what
remains **your** responsibility. It is general information, not legal advice; rules differ by
country and by situation. When in doubt, ask a lawyer or your data-protection officer.

## What the tool does and does not do

- It reads **public** pages and search-engine results, like a person would with a browser. It never
  logs in, never bypasses a block, never uses leaked data (the breach check only asks HaveIBeenPwned
  whether an address appears in a known breach and returns breach names, not the leaked content).
- It does **no facial recognition and no biometric identification**. Faces are only counted
  (optional), and profile pictures are compared as image files (perceptual hash), which detects the
  same picture being reused, not the same person in a different picture.
- Everything is stored **locally**. Nothing is sent to an EchoTrace server; there is none.

## Built-in safeguards

| GDPR principle | In EchoTrace |
|---|---|
| Purpose limitation | A purpose is required for each analysis, stored with it and printed in the reports |
| Data minimisation | Only the fields you type are used; photos are hashed, not stored; no bulk import |
| Storage limitation | Analyses older than `retention_days` (90) are deleted at startup |
| Access / portability | History tab → *Exporter toutes mes données* (or `echotrace-cli export-data`) |
| Erasure | *Tout effacer* (or `echotrace-cli erase`), per-analysis deletion, *Purger maintenant* |
| Accuracy | Confidence scores, evidence column, false-positive memory, "a hit is not proof" in every report |
| Security | API keys in a user-only file; TLS verified; reports escape scraped content |

## Your responsibilities

1. **Have a lawful basis** for searching a person. The five purposes offered are a reminder, not a
   permission: searching yourself or with the person's agreement is the safest; "legitimate interest"
   (journalism, due diligence, protecting your rights) needs a real balancing test and often a
   notice to the person. Employers and recruiters face stricter rules in many countries.
2. **Do not search special categories** (health, religion, sexual orientation, political opinions,
   etc.) and do not use the tool to infer them. Do not search minors.
3. **Do not turn it into monitoring.** A one-off check differs from watching someone over time.
   `rescan` / scheduled runs are meant for your own footprint, a brand, or a person who agreed.
4. **Protect the reports.** They are personal data. Keep them only as long as the purpose requires
   and delete them (the retention setting does not delete files you exported).
5. **Respect the sites.** Their terms may restrict automated access; keep the default delays and
   limits, use the cache, and do not circumvent blocks or captchas.
6. **Law of your country.** Some countries restrict profiling or automated collection even from
   public sources, and the "personal or household use" exemption does not cover professional use.

## Things deliberately not included

Bulk lists of people, face matching between photos, scraping behind a login, automatic harassment
or contact features, and silent background monitoring.
