# PRIS — Postdoctoral Research Intelligence System

**Live site: https://guru-jay-prakash.github.io/pris/**

A search and tracking tool for fully funded postdoctoral positions worldwide. Open the link — nothing to install.

## What this repository holds

| File | Purpose |
|---|---|
| `index.html` | The entire application. Single file, no dependencies, no build step. |
| `pris_data.js` | The dataset. Overwritten every morning by an automated refresh. |
| `build_data.py` | Validates raw fetches and produces `pris_data.js`. |
| `raw_ingest.json` | The most recent raw fetch, before validation. |

`index.html` also contains a fallback copy of the data, so it still works if `pris_data.js` fails to load — and says so in an amber banner when that happens.

## Data policy

Every record carries the URL of the posting it was read from, and an **Open the original posting** button. The posting is the authority; this is an index over it.

Enforced in code, not just stated:

- A record without its own posting URL is rejected.
- A source that fails a control probe — where deliberately invalid URLs return plausible content instead of errors — is quarantined and all its records discarded.
- A field not present on the fetched page stays `null`. Nothing is completed or inferred.
- Derived and computed values are labelled per record, with an explanation of how each was produced.
- If fewer than 20 records survive validation, the build aborts rather than overwrite a good dataset.
- Match scores skip components a posting says nothing about instead of awarding a pass.
- The competitiveness estimate is withheld when fewer than 2 of its 5 inputs are real.
- Acceptance rates are shown only where officially published, never estimated.

## Sources

Polled: jobs.ac.uk · AcademicPositions · THE unijobs · researchersjob.com · IndiaBioscience · IIT Delhi

Not polled, by their own rules: EURAXESS, Nature Careers and HigherEdJobs disallow automated access to their job pages. This respects that rather than working around it.

Quarantined: JREC-IN (Japan) — the fetch returned fabricated postings for invalid job IDs and cannot currently be trusted.

Coverage is therefore uneven, and Indian coverage is partial: the national scheme portals publish PDFs on client-rendered pages and cannot be ingested. The in-app **Data Sources** page lists the current status of every source.

## Privacy

Saved positions, applications, notes, reminders and your profile are stored in your own browser and are never uploaded. Nothing about you leaves your machine.
