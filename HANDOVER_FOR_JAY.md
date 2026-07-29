# PRIS — Owner's Guide for Dr. Jay Prakash

**Your site: https://guru-jay-prakash.github.io/pris/** — bookmark it. It updates itself every
morning at 07:00 IST. You install nothing and maintain nothing for day-to-day use.

**Good news first: you already own all of it.** The GitHub account `Guru-Jay-Prakash` is yours,
and everything lives inside it — the website, the data, and the daily automation. There is no
transfer to do and nothing to migrate. This guide exists so you can run it alone, forever.

---

## 1. How PRIS works (60-second version)

| Piece | Where it lives | What it does |
|---|---|---|
| The website | GitHub Pages, **your account** (free) | What you open every day |
| The data | `pris_data.js` in **your repository** | The vacancy list, rebuilt daily |
| The daily engine | GitHub Actions, **your account** (free on public repos) | Fetches job sites at 07:00 IST, validates, publishes |
| Your saved jobs & notes | **Your own browser only** | Private; never uploaded; survives every update |

**No AI runs the daily updates.** GitHub does, free, on its own servers
([GitHub's plans](https://docs.github.com/get-started/learning-about-github/githubs-products),
[Actions billing](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions)).
AI is only needed occasionally — when a job site redesigns and a parser needs repair
(realistically a few times a year).

Trust rules baked into the code: every vacancy carries an **"Open the original posting"** button
linking to the real page it was read from — that page is always the authority; blank fields mean
the employer didn't publish that detail, nothing is ever invented; sources that return fake
content are quarantined automatically.

## 2. Protect the one thing that matters: your GitHub account

Since everything is inside `Guru-Jay-Prakash`, that login IS the system. Three one-time steps:

1. **Know your password** — store it in a password manager or written somewhere safe.
2. **Add a recovery email/phone**: https://github.com/settings/emails
3. **Turn on two-factor authentication**: https://github.com/settings/security — and save the
   recovery codes it gives you.

Do these once and no lost phone or forgotten password can take PRIS away from you.

## 3. The three screens you should recognise (5 minutes, once)

Log in at github.com and open your repository `pris`:

- **Actions tab** — the daily engine's history. Green ticks = mornings that worked.
  The **"Run workflow"** button (under *PRIS daily data refresh*) forces a refresh any time.
- **Data Sources page on your website** (left sidebar) — which job sites were polled today,
  and any shown in red as FAILED.
- **The pencil icon** on any file — GitHub's built-in editor. This is how repairs land,
  no software needed.

**If a morning run ever fails, GitHub emails you automatically.** The site keeps showing the
last good day's data — a failure can never blank your site.

## 4. When something breaks: the repair playbook (no coding needed)

**Symptoms:** a "Run failed" email from GitHub, a red FAILED source on the Data Sources page,
or an amber "data is X days old" banner on the site.

**The fix works with ANY free AI chatbot** — ChatGPT Free, Google Gemini (free), or Claude
(free). All accept pasted text and small file uploads within daily limits, which is all this
needs ([free-tier comparison](https://pecollective.com/blog/ai-free-tiers-2026/),
[file upload limits](https://onefileapp.com/blog/ai-file-upload-limits-compared),
[which free tier wins](https://aiwire.ai/articles/chatgpt-vs-claude-vs-gemini-which-free-tier-wins)).

1. In your repo, open **`scraper.py`** → copy icon (two squares) → copy everything.
2. Open any AI chatbot and send this, then paste the file:

   > This Python script scrapes postdoctoral job listings daily on GitHub Actions.
   > The source called "____" (copy the FAILED name and its error note from my site's
   > Data Sources page) stopped working, probably because that website redesigned.
   > Fix ONLY that source's parser and give me back the COMPLETE corrected file.
   > Keep every safety rule unchanged: the control probe, the robots.txt check, the
   > postdoc filters, and never inventing data — a field not printed on the fetched
   > page must stay null. Here is the file:

3. In your repo: `scraper.py` → **pencil icon** → select all → paste the corrected file →
   **Commit changes** (green button).
4. **Actions** tab → *PRIS daily data refresh* → **Run workflow**. Green tick = fixed.
   Red again? Paste the red error text into the same chat and ask again.

You cannot break your data doing this: a bad script publishes **nothing** (the validator
refuses any dataset under 20 records), so the site simply keeps yesterday's list until the
fix works.

**Can an AI run PRIS automatically for free?** No — scheduled unattended AI runs are paid
features everywhere. You also don't need it: GitHub owns the schedule for free; AI is only
your occasional repair mechanic, and free tiers handle that fine.

## 5. About Rahul's part, and what happens without it

Rahul's Claude account currently runs one **optional** extra: a twice-monthly (1st and 15th)
intelligent sweep — checking Indian institution pages the script can't parse, verifying
postings against their individual pages, and auto-repairing the scraper. It uses an access
key you created (scoped to this one repository only; you can revoke it anytime at
https://github.com/settings/tokens?type=beta, and it expires on its own in ~1 year).

| Event | Effect on your PRIS |
|---|---|
| Rahul's Claude account deleted | **Daily updates continue unaffected.** You lose only the fortnightly sweep. Manual substitute: once a fortnight, ask any free chatbot to check researchersjob.com and the IIT postdoc pages for new civil-engineering positions, and add finds via your site's **Data Manager → New record**. |
| Rahul's anything else | No effect. Nothing of PRIS lives outside your accounts. |
| A job site redesigns | That one source shows FAILED; the rest keep working. Repair playbook above. |
| GitHub retires free Pages/Actions (no sign of it — [pricing changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)) | `index.html` opened straight from disk still works — it carries a built-in copy of the last data. |
| You lose your GitHub login | The real risk. Section 2 prevents it. A full backup of every file also sits in the project folder — rebuildable on a fresh account in ~20 minutes via SETUP_GITHUB.md. |

## 6. Honest limits — so you use PRIS correctly

- **PRIS is an index, not an authority.** Before applying, ALWAYS open the original posting.
  If PRIS and the posting disagree, the posting is right.
- **Coverage is real but partial.** EURAXESS (most European postings) blocks automated
  collection — emailing support@euraxess.eu to request data access is the single biggest
  upgrade available to you. India has no engineering-postdoc feed anywhere; Indian coverage
  relies on the fortnightly sweep and your own additions.
- **Thin weeks are the market, not a malfunction.** Your niche posts a handful of positions
  worldwide in any week. PRIS's value compounds — it never misses a day.
- **The "YOUR FIELD" badge is ~90% accurate, not 100%** — it reads titles and departments.
  The purple "Adjacent" section exists because winnable positions hide behind vague titles.
