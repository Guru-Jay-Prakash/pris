#!/usr/bin/env python3
"""
PRIS daily scraper — runs on GitHub Actions, costs nothing, touches no Claude account.

Design contract (same rules as the rest of PRIS):
  - Every record must carry the URL of a page this script actually fetched
    (or, for hardcoded recurring programmes, the official programme page).
  - A field not present in the fetched HTML stays null. Nothing is guessed.
  - Every domain gets a CONTROL PROBE before being trusted: a deliberately
    invalid URL must NOT return job-like content. A domain that fails the
    probe is quarantined for that run — zero records taken.
  - robots.txt is honored. Sources whose robots forbid our paths are skipped.
  - Output: raw_ingest.json in the exact shape build_data.py consumes.
    build_data.py (the validator) then applies the classification gate,
    the false-friend list, and the <20-records abort.

This script is deliberately dumb: fixed parsers, no judgment. When a site
redesigns, its source drops to zero records and shows FAILED on the app's
Data Sources page — that is the signal to ask Claude to repair this file.
"""
import json, re, sys, datetime, time, urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "PRIS-refresh/1.0 (personal research-vacancy index; +https://github.com/Guru-Jay-Prakash/pris)"
TODAY = datetime.date.today().isoformat()
TIMEOUT = 25
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en"})

# ---------------------------------------------------------------- filters ----
POSTDOC_RE = re.compile(
    r"post[- ]?doc|postdoctoral|research fellow|research associate|"
    r"wissenschaftliche[rn]? mitarbeiter|研究員", re.I)
EXCLUDE_RE = re.compile(
    r"\bphd\b|doctoral (student|position|candidate)|studentship|\bjrf\b|technician|"
    r"lecturer|professor|\bdean\b|\bchair\b|sessional|assistant head|administrat|"
    r"secretary|coordinator|manager\b|internship|master", re.I)
FALSE_FRIEND_RE = re.compile(
    r"structural biolog|structural enzymolog|protein structure|crystallograph|cryo.em|"
    r"structural geolog|soil (microbiolog|biolog|ecolog|microbiome)|food structure|"
    r"structural (equation|causal|racism)", re.I)

def keep(title):
    t = title or ""
    return bool(POSTDOC_RE.search(t)) and not EXCLUDE_RE.search(t) and not FALSE_FRIEND_RE.search(t)

# ---------------------------------------------------------------- fetching ---
_robots = {}
def allowed(url):
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = S.get(base + "/robots.txt", timeout=TIMEOUT)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])  # robots unreachable -> default allow, note stays in source config
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)

def fetch(url, retries=2):
    last = None
    for _ in range(retries + 1):
        try:
            r = S.get(url, timeout=TIMEOUT)
            if r.status_code == 200 and r.text:
                return r.text
            last = "HTTP %s" % r.status_code
        except Exception as e:
            last = str(e)[:120]
        time.sleep(2)
    raise RuntimeError(last or "fetch failed")

def probe_ok(base, link_pattern):
    """Control probe: an invalid URL must not return content our parser would
    mistake for job listings. Returns (ok, note)."""
    url = base.rstrip("/") + "/pris-probe-does-not-exist-9999"
    try:
        r = S.get(url, timeout=TIMEOUT)
    except Exception as e:
        return True, "probe unreachable (%s) — treated as pass, watch this source" % str(e)[:60]
    if r.status_code >= 400:
        return True, "probe returned HTTP %s (clean)" % r.status_code
    if link_pattern and re.search(link_pattern, r.text or ""):
        return False, "QUARANTINED: invalid URL returned job-like content (soft-200 with matching links)"
    return True, "probe soft-200 but no job markup — pages are validated by content, not status"

# --------------------------------------------------------------- extraction --
def clean(s):
    return re.sub(r"\s+", " ", s or "").strip() or None

def month_year_date(text, want_future=True):
    """Resolve 'DD Mon' / 'DD Month YYYY' style dates. Year absent -> nearest
    sensible year, marked derived by the caller."""
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*(\d{4})?", text or "", re.I)
    if not m:
        return None, False
    day, mon = int(m.group(1)), m.group(2)[:3].title()
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    mo = months.index(mon) + 1
    today = datetime.date.today()
    if m.group(3):
        try: return datetime.date(int(m.group(3)), mo, day).isoformat(), False
        except ValueError: return None, False
    try:
        d = datetime.date(today.year, mo, day)
    except ValueError:
        return None, False
    if want_future and d < today - datetime.timedelta(days=14):
        d = datetime.date(today.year + 1, mo, day)
    return d.isoformat(), True  # derived year

def anchors(soup, base, href_re):
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])
        if re.search(href_re, href):
            title = clean(a.get_text())
            if title and len(title) > 8 and (title, href) not in seen:
                seen.add((title, href))
                out.append((title, href, a))
    return out

def block_text(a, levels=3):
    node = a
    for _ in range(levels):
        if node.parent is None: break
        node = node.parent
        if len(clean(node.get_text()) or "") > 60: break
    return clean(node.get_text()) or ""

# ---------------------------------------------------------------- sources ----
def rec(sid, title, url, uni=None, dp=None, c=None, ct=None, sal=None,
        dl=None, pd=None, dv=None, fc=None, warn=None):
    return {"s": sid, "t": title, "u": uni, "dp": dp, "c": c, "ct": ct,
            "sal": sal, "dl": dl, "pd": pd, "url": url,
            "dv": dv or [], **({"fc": fc} if fc else {}), **({"warn": warn} if warn else {})}

def src_the(out):
    base = "https://www.timeshighereducation.com"
    pages = ["/unijobs/listings/civil-engineering/", "/unijobs/listings/civil-engineering/?page=2",
             "/unijobs/listings/postdoctoral/"]
    seen = set()
    for p in pages:
        soup = BeautifulSoup(fetch(base + p), "html.parser")
        for title, href, a in anchors(soup, base, r"/unijobs/listing/\d+/"):
            if href in seen or not keep(title): continue
            seen.add(href)
            blk = block_text(a)
            sal = clean((re.search(r"[£$€]\s?[\d,]+(?:[^.;|]{0,40})", blk) or [None] and re.search(r"[£$€]\s?[\d,][^|;\n]{0,50}", blk)) and re.search(r"[£$€]\s?[\d,][^|;\n]{0,50}", blk).group(0))
            uni_m = re.search(r"^([A-Z][^|\n]{3,70}?)\s*(?:logo)?\s*$", blk, re.M)
            out.append(rec("the", title, href, uni=clean(uni_m.group(1)) if uni_m else None, sal=sal))

def src_academicpositions(out):
    base = "https://academicpositions.com"
    pages = (["/jobs/position/post-doc/field/engineering?page=%d" % i for i in range(1, 4)] +
             ["/jobs/position/post-doc?page=%d" % i for i in range(1, 3)])
    seen = set()
    for p in pages:
        soup = BeautifulSoup(fetch(base + p.replace("?page=1", "")), "html.parser")
        got = anchors(soup, base, r"academicpositions\.com/ad/")
        if not got:
            raise RuntimeError("no /ad/ links found — empty shell or markup changed")
        for title, href, a in got:
            if href in seen or not keep(title): continue
            seen.add(href)
            blk = block_text(a)
            dlm = re.search(r"(20\d\d-\d\d-\d\d)", blk)
            out.append(rec("academicpositions", title, href, dl=dlm.group(1) if dlm else None))

def src_jobsacuk(out):
    base = "https://www.jobs.ac.uk"
    queries = ["structural+engineering", "civil+engineering", "finite+element",
               "structural+dynamics", "computational+mechanics", "geotechnical", "postdoctoral"]
    seen = set()
    for q in queries:
        soup = BeautifulSoup(fetch(base + "/search/?keywords=%s&sort=re" % q), "html.parser")
        for title, href, a in anchors(soup, base, r"jobs\.ac\.uk/job/[A-Z0-9]+/"):
            if href in seen or not keep(title): continue
            seen.add(href)
            blk = block_text(a)
            sal_m = re.search(r"£[\d,][^|;\n]{0,60}", blk)
            dl, derived = (None, False)
            dlm = re.search(r"Closes?:?\s*([^|\n]{4,30})", blk, re.I)
            if dlm: dl, derived = month_year_date(dlm.group(1))
            out.append(rec("jobsacuk", title, href, c=None, sal=clean(sal_m.group(0)) if sal_m else None,
                           dl=dl, dv=(["deadline.year"] if derived else [])))

WATCHLIST = [
    dict(id="eth", name="ETH Zurich jobs board", base="https://jobs.ethz.ch",
         page="https://jobs.ethz.ch/", link=r"jobs\.ethz\.ch/job/view/", uni="ETH Zurich",
         c="Switzerland", ct="Zurich", fc=None,
         note="University-wide board, fully open robots. Structural/seismic content appears here; titles are classified by the validator."),
    dict(id="tudelft", name="TU Delft careers (q=structural)", base="https://careers.tudelft.nl",
         page="https://careers.tudelft.nl/search/?q=structural&locale=en_US",
         link=r"careers\.tudelft\.nl/job/", uni="TU Delft", c="Netherlands", ct="Delft", fc=None,
         note="Server-rendered SuccessFactors search filtered to 'structural'. Soft-404 host: pages validated by content."),
    dict(id="uiuc", name="UIUC Civil & Environmental Engineering", base="https://cee.illinois.edu",
         page="https://cee.illinois.edu/about/employment", link=r"(csod\.com|/requisition/)",
         uni="University of Illinois Urbana-Champaign", dp="Civil & Environmental Engineering",
         c="USA", ct="Urbana", fc=None, note="Department employment page; postings link to the Illinois jobs portal."),
    dict(id="toronto", name="University of Toronto Civil & Mineral Engineering", base="https://civmin.utoronto.ca",
         page="https://civmin.utoronto.ca/about-civmin/opportunities/",
         link=r"civmin\.utoronto\.ca/(about-civmin/opportunities/.+|wp-content/uploads/.+\.(docx|pdf))",
         uni="University of Toronto", dp="Civil & Mineral Engineering", c="Canada", ct="Toronto", fc=None,
         note="Department opportunities page; some postings are .docx/.pdf attachments — open the original."),
    dict(id="nus", name="NUS Civil & Environmental Engineering", base="https://cde.nus.edu.sg",
         page="https://cde.nus.edu.sg/cee/about-us/careerscee/", link=r"cde\.nus\.edu\.sg/cee/.*career",
         uni="National University of Singapore", dp="Civil & Environmental Engineering",
         c="Singapore", ct="Singapore", fc=None,
         note="Department careers hub; researcher-position subpage often empty — monitored for when it is not."),
    dict(id="eritokyo", name="University of Tokyo Earthquake Research Institute", base="https://www.eri.u-tokyo.ac.jp",
         page="https://www.eri.u-tokyo.ac.jp/recruitinfo/", link=r"eri\.u-tokyo\.ac\.jp/wp-content/uploads/.+\.pdf",
         uni="University of Tokyo", dp="Earthquake Research Institute", c="Japan", ct="Tokyo", fc="high",
         note="Entirely earthquake research. Postings are Japanese-language PDFs — titles kept verbatim; open the original."),
]

def src_watchlist(w, out):
    soup = BeautifulSoup(fetch(w["page"]), "html.parser")
    got = anchors(soup, w["base"], w["link"])
    n = 0
    for title, href, a in got:
        jp = w["id"] == "eritokyo"
        if not jp and not keep(title):
            continue
        if jp and not re.search(r"研究員|postdoc|research", title, re.I):
            continue
        out.append(rec(w["id"], title, href, uni=w.get("uni"), dp=w.get("dp"),
                       c=w.get("c"), ct=w.get("ct"), fc=w.get("fc"),
                       warn="Japanese-language posting; details in the linked PDF." if jp else None))
        n += 1
    return n

def src_recurring(out):
    """Fellowships with officially published cycles. Not scraped daily — the
    entries point at the official programme pages; deadlines are the published
    cycle dates. Verified against the live pages on 2026-07-29."""
    today = datetime.date.today()
    # Humboldt Research Fellowship: three annual review deadlines (15 Mar / 15 Jul / 15 Nov)
    cands = []
    for y in (today.year, today.year + 1):
        for mo, d in ((3, 15), (7, 15), (11, 15)):
            dt = datetime.date(y, mo, d)
            if dt >= today: cands.append(dt)
    hb = min(cands).isoformat()
    out.append(rec("humboldt", "Humboldt Research Fellowship for Postdoctoral Researchers",
                   "https://www.humboldt-foundation.de/en/apply/sponsorship-programmes/humboldt-research-fellowship",
                   uni="Alexander von Humboldt Foundation", c="Germany",
                   sal="EUR 3,000–3,600/month (published programme rate)",
                   dl=hb, dv=["deadline.nextCycleComputed"], fc="high",
                   warn="All-discipline fellowship — the applicant defines the research field and German host. Each review round closes early after 800 applications."))
    out.append(rec("jsps", "JSPS International Fellowship for Research in Japan (Standard, FY2027 1st call)",
                   "https://www.jsps.go.jp/english/e-fellow/",
                   uni="Japan Society for the Promotion of Science", c="Japan",
                   dl="2026-08-28" if today <= datetime.date(2026, 8, 28) else "2027-04-23",
                   fc="high",
                   warn="All-discipline fellowship; the JAPANESE HOST INSTITUTION submits the application, not the fellow — contact a host professor first."))
    out.append(rec("quakecore", "QuakeCoRE Contestable Funding Round (annual RfP, early Sep – early Oct)",
                   "https://www.quakecore.nz/opportunities/",
                   uni="QuakeCoRE — NZ Centre for Earthquake Resilience", c="New Zealand",
                   fc="high",
                   warn="Recurring funding round, window published as early-September to early-October; exact dates on the official page. Not crawled daily (site restricts bots); entry maintained from the published cycle."))

# ------------------------------------------------------------------- main ----
STATIC_SOURCES = [
  {"id":"euraxess","name":"EURAXESS","status":"BLOCKED","listUrls":["https://euraxess.ec.europa.eu/jobs/search"],
   "note":"robots.txt disallows /jobs/* and /*? — the search and every detail page. Not polled; respected, not worked around. The single biggest coverage loss for European structural engineering."},
  {"id":"nature","name":"Nature Careers","status":"BLOCKED","listUrls":["https://www.nature.com/naturecareers/"],
   "note":"robots.txt disallows the job search and RSS, and blocks AI agents by name. Not polled."},
  {"id":"higheredjobs","name":"HigherEdJobs","status":"BLOCKED","listUrls":["https://www.higheredjobs.com/"],
   "note":"WAF challenge on all paths. Not pollable."},
  {"id":"findapostdoc","name":"FindAPostDoc","status":"REJECTED","listUrls":["https://www.findapostdoc.com/"],
   "note":"403s on listing paths; the one responding route served 2017-vintage postings. Excluded as a stale-data hazard."},
  {"id":"jrecin","name":"JREC-IN Portal (Japan)","status":"QUARANTINED","listUrls":["https://jrecin.jst.go.jp/"],
   "note":"Failed the control probe on 2026-07-28: invalid job IDs returned complete plausible postings. Not trusted by plain fetch."},
  {"id":"purdue","name":"Purdue careers portal","status":"REJECTED","listUrls":["https://careers.purdue.edu/"],
   "note":"Failed the control probe (soft-200 on invalid URLs) and renders via JavaScript. Excluded."},
  {"id":"canterbury","name":"University of Canterbury NZ jobs","status":"BLOCKED","listUrls":["https://jobs.canterbury.ac.nz/"],
   "note":"robots.txt disallows the jobs host outright. Not polled, despite NZ's strength in earthquake engineering."},
  {"id":"jsonly","name":"JS-only portals (DTU, NTNU, Bristol, SNSF, DAAD, MSCA portal, EPFL, Polimi, HKUST)","status":"FAILED",
   "listUrls":["https://www.dtu.dk/","https://www.ntnu.edu/vacancies","https://www.bristol.ac.uk/jobs/","https://www.snf.ch/","https://www.daad.de/","https://marie-sklodowska-curie-actions.ec.europa.eu/calls"],
   "note":"Listings render only in JavaScript (or the domain blocks AI agents / times out), invisible to this fetcher. Several likely have JSON APIs — future work, tracked in the README."},
]

def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "raw_ingest.json"
    prev_first_seen = {}
    try:
        prev = json.load(open(out_path))
        for r in prev.get("records", []):
            if r.get("url") and r.get("pd"):
                prev_first_seen[r["url"]] = r["pd"]
    except Exception:
        pass

    records, sources = [], []
    runs = [
        ("the", "THE unijobs", ["https://www.timeshighereducation.com/unijobs/listings/civil-engineering/","https://www.timeshighereducation.com/unijobs/listings/postdoctoral/"],
         "Civil-engineering and postdoctoral listing routes (robots-permitted; the RSS feed is not). Cards omit deadlines; expired ads persist — status is computed from what is printed.",
         lambda o: src_the(o), "https://www.timeshighereducation.com", r"/unijobs/listing/\d+/"),
        ("academicpositions", "AcademicPositions.com", ["https://academicpositions.com/jobs/position/post-doc/field/engineering","https://academicpositions.com/jobs/position/post-doc"],
         "Engineering postdoc feed + general feed, server-rendered. Failure mode is an empty shell without /ad/ links — detected and reported as FAILED.",
         lambda o: src_academicpositions(o), "https://academicpositions.com", r"/ad/"),
        ("jobsacuk", "jobs.ac.uk", ["https://www.jobs.ac.uk/search/?keywords=structural+engineering","https://www.jobs.ac.uk/search/?keywords=civil+engineering","https://www.jobs.ac.uk/search/?keywords=postdoctoral"],
         "Field-targeted keyword searches. Years absent next to dates are resolved and marked derived (dv: deadline.year).",
         lambda o: src_jobsacuk(o), "https://www.jobs.ac.uk", r"/job/[A-Z0-9]+/"),
    ]
    for w in WATCHLIST:
        runs.append((w["id"], w["name"], [w["page"]], w["note"],
                     (lambda o, w=w: src_watchlist(w, o)), w["base"], w["link"]))

    for sid, name, urls, note, fn, base, linkpat in runs:
        before = len(records)
        try:
            if not allowed(urls[0]):
                sources.append({"id": sid, "name": name, "status": "BLOCKED", "listUrls": urls,
                                "note": note + " robots.txt disallowed our path at run time — skipped."})
                continue
            ok, pnote = probe_ok(base, linkpat)
            if not ok:
                sources.append({"id": sid, "name": name, "status": "QUARANTINED", "listUrls": urls,
                                "note": note + " " + pnote})
                continue
            fn(records)
            got = len(records) - before
            sources.append({"id": sid, "name": name, "status": "OK", "listUrls": urls,
                            "note": note + (" No postdoc-level rows on the page this run — monitored." if got == 0 else "") + " [" + pnote + "]"})
        except Exception as e:
            del records[before:]
            sources.append({"id": sid, "name": name, "status": "FAILED", "listUrls": urls,
                            "note": note + " RUN ERROR: " + str(e)[:160] + " — likely a site redesign; ask Claude to repair scraper.py."})

    src_recurring(records)
    for sid, name, url, note in [
        ("humboldt","Humboldt Research Fellowship","https://www.humboldt-foundation.de/en/apply/sponsorship-programmes/humboldt-research-fellowship",
         "Recurring programme. Entry maintained from the published cycle (15 Mar / 15 Jul / 15 Nov), verified 2026-07-29 — not scraped daily."),
        ("jsps","JSPS International Fellowships","https://www.jsps.go.jp/english/e-fellow/",
         "Recurring programme. FY2027 deadlines published: 2026-08-28 and 2027-04-23 (host institution submits). Verified 2026-07-29."),
        ("quakecore","QuakeCoRE (NZ)","https://www.quakecore.nz/opportunities/",
         "Recurring earthquake-resilience funding rounds. Site blocklists AI crawlers, so it is not crawled; the entry carries the published cycle."),
    ]:
        sources.append({"id": sid, "name": name, "status": "OK", "listUrls": [url], "note": note})
    sources.extend(STATIC_SOURCES)

    for r in records:
        if not r.get("pd"):
            if r["url"] in prev_first_seen:
                r["pd"] = prev_first_seen[r["url"]]
            else:
                r["pd"] = TODAY
                r.setdefault("dv", []).append("postedDate.firstSeenByPRIS")

    json.dump({"fetchedAt": TODAY, "sources": sources, "records": records},
              open(out_path, "w"), ensure_ascii=False, indent=1)
    ok_n = sum(1 for s in sources if s["status"] == "OK")
    print("scraper: %d records from %d OK sources (of %d evaluated)" % (len(records), ok_n, len(sources)))
    failed = [s["id"] for s in sources if s["status"] == "FAILED"]
    if failed:
        print("scraper: FAILED sources needing repair: %s" % ", ".join(failed))
    if len(records) < 10:
        print("scraper: FATAL — implausibly few records; refusing to hand a collapsed set to the validator")
        sys.exit(3)

if __name__ == "__main__":
    main()
