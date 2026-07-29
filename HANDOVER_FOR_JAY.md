# PRIS — Handover Guide for Dr. Jay Prakash

**Your site: https://guru-jay-prakash.github.io/pris/** — bookmark it. It updates itself every
morning at 07:00 IST. You install nothing and maintain nothing for day-to-day use.

This document exists so you never depend on anyone. Read it once; keep it.

---

## 1. How PRIS works (60-second version)

| Piece | Where it lives | What it does |
|---|---|---|
| The website | GitHub Pages (free) | What you open every day |
| The data | `pris_data.js` in the GitHub repository | The vacancy list, rebuilt daily |
| The daily engine | GitHub Actions (free, runs on GitHub's servers) | Fetches job sites at 07:00 IST, validates, publishes |
| Your saved jobs & notes | **Your own browser only** | Private; never uploaded; survives every update |

**No AI runs the daily updates.** GitHub does, for free, forever. AI is only needed
occasionally — when a job site redesigns its pages and a parser needs repairing (realistically
a few times a year).

Trust rules baked into the code: every vacancy links to the real posting it was read from
("Open the original posting" button — that page is always the authority); blank fields mean
the employer didn't publish that detail — nothing is ever invented; sources that return fake
content are automatically quarantined.

---

## 2. Making PRIS 100% yours (do this once, ~20 minutes)

Right now the repository sits in Rahul's GitHub account. Transfer it to your own and every
dependency on Rahul disappears.

**Step A — Create your free GitHub account** at https://github.com/signup.
The free plan is enough: public repositories are free, GitHub Pages is free, and Actions
on public repositories runs at no cost ([GitHub's plans](https://docs.github.com/get-started/learning-about-github/githubs-products),
[Actions billing](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions)).

**Step B — Rahul transfers the repository to you:**
1. Rahul opens https://github.com/Guru-Jay-Prakash/pris/settings
2. Scrolls to **Danger Zone** → **Transfer ownership**
3. Types your GitHub username, confirms.
4. You accept the transfer (GitHub emails you a link).

**Step C — You switch two things back on (transfers reset them):**
1. **Website:** your repo → Settings → Pages → Source: *Deploy from a branch* → Branch:
   *main*, folder */ (root)* → Save. Your new address becomes
   `https://YOUR-USERNAME.github.io/pris/` — the old address stops working, so re-bookmark.
2. **Daily engine:** your repo → **Actions** tab → if a yellow banner asks you to enable
   workflows, click **"I understand my workflows, go ahead and enable them"**.
   Test it: Actions → *PRIS daily data refresh* → **Run workflow** → green button.
   Two minutes later: green tick = working.

**Step D — nothing else.** No token needed for the daily engine — it uses GitHub's own
built-in permissions. If a run ever fails, **GitHub emails you automatically**.

> If Rahul's account is deleted *before* a transfer happens: the site and automation die with
> it, but nothing is truly lost — the complete system (all files) is also saved in the
> project folder. Anyone can re-upload those files to a fresh GitHub repository following
> SETUP_GITHUB.md, and you're back in ~20 minutes.

---

## 3. When something breaks: the repair playbook (no coding needed)

**How you'll know:** GitHub emails you "Run failed", or the site's **Data Sources** page
shows a source in red saying FAILED, or the site shows an amber "data is X days old" banner.

**The fix — works with ANY free AI chatbot.** Yes, this genuinely works on free tiers:
ChatGPT Free, Google Gemini (free), and Claude (free) all accept pasted text and file
uploads within daily limits, which is all this needs
([free-tier comparison](https://pecollective.com/blog/ai-free-tiers-2026/),
[file upload limits compared](https://onefileapp.com/blog/ai-file-upload-limits-compared),
[which free tier wins](https://aiwire.ai/articles/chatgpt-vs-claude-vs-gemini-which-free-tier-wins)).
The repair is a single-file edit — small enough for any of them.

1. In your repo, click **`scraper.py`**, then the **copy** icon (two squares) to copy its
   full contents.
2. Open any AI chatbot and paste this prompt, then the file:

   > This Python script scrapes postdoctoral job listings daily on GitHub Actions.
   > The source called "____" (copy the FAILED name and its error note from the Data
   > Sources page of my site) has stopped working, probably because that website
   > redesigned its pages. Please fix ONLY that source's parser and give me back the
   > COMPLETE corrected file. Keep every safety rule unchanged: the control probe, the
   > robots.txt check, the postdoc filters, and never inventing any data — a field not
   > printed on the fetched page must stay null. Here is the file:

3. Back in your repo: open `scraper.py` → **pencil icon** (Edit) → select all → paste the
   AI's corrected file → **Commit changes** (green button).
4. Actions tab → *PRIS daily data refresh* → **Run workflow**. Green tick = fixed.

If the AI's fix doesn't work, paste the red error text from the failed Actions run back into
the same chat and ask again. Nothing you do here can destroy your data: a broken script
publishes **nothing** (the validator refuses datasets under 20 records), so the site just
keeps showing the last good day until the fix lands.

**Can an AI run PRIS *automatically* on a free tier?** No — scheduled, unattended AI runs
are paid features everywhere. But you don't need that: the schedule is GitHub's (free), and
AI is only the occasional repair mechanic, which free tiers handle fine as shown above.

---

## 4. What runs where after handover — dependency map

| Event | Effect on your PRIS |
|---|---|
| Rahul's **Claude** account deleted | Daily updates continue unaffected. You lose only the optional twice-monthly "intelligent sweep" (India institution checks, deep verification). Replace it manually: once a fortnight, ask any free AI chatbot to check researchersjob.com and the IIT pages for new civil-engineering postdocs, then add finds via your site's **Data Manager → New record**. |
| Rahul's **GitHub** account deleted, transfer done | Nothing. It's your repo. |
| Rahul's GitHub deleted, transfer NOT done | Site dies; rebuild in 20 min from the project-folder backup using SETUP_GITHUB.md. |
| A job site redesigns | That source shows FAILED; the rest keep working. Use the repair playbook. |
| GitHub retires free Pages/Actions (no sign of this — [pricing changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)) | The site file also works opened directly from disk — `index.html` contains a built-in copy of the last data. |

## 5. Honest limits — so you use PRIS correctly

- **PRIS is an index, not an authority.** Before applying, ALWAYS open the original posting.
  If PRIS and the posting disagree, the posting is right.
- **Coverage is real but partial.** EURAXESS (most European postings) legally blocks
  automated collection — emailing support@euraxess.eu for data access is the single biggest
  upgrade available. India has no engineering-postdoc feed anywhere; Indian coverage relies
  on the fortnightly sweep and your own additions.
- **Thin weeks are the market, not a malfunction.** Your niche posts a handful of positions
  worldwide in any given week. PRIS's value compounds: it never misses a day.
- **The "YOUR FIELD" badge is ~90% accurate, not 100%** — it reads titles and departments.
  The adjacent (purple) section exists precisely because winnable positions hide behind
  vague titles.
