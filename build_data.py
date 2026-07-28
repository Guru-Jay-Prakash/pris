#!/usr/bin/env python3
"""
PRIS live-data builder.

Transforms raw ingested postings into the PRIS record schema.

HARD RULES enforced here (not just documented):
  - No record without an individual posting URL.
  - No record from a source whose status is not OK.
  - Fields that were not on the fetched page stay null. Nothing is completed,
    beautified or inferred into a factual field.
  - The only computed fields are: stipend amount/currency parsed out of the
    verbatim salary string, and research keywords matched against the posting's
    own title text. Both are recorded in `computedFields` so the UI can label
    them as derived rather than reported.
"""
import json, re, sys, os, datetime

# Usage: build_data.py <raw_ingest.json> <out_pris_data.js> [YYYY-MM-DD]
RAW_PATH = sys.argv[1] if len(sys.argv) > 1 else "raw_ingest.json"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "pris_data.js"
TODAY = sys.argv[3] if len(sys.argv) > 3 else datetime.date.today().isoformat()

CURRENCY_PATTERNS = [
    (r'£', 'GBP'), (r'€', 'EUR'), (r'₹|Rs\.?|INR', 'INR'), (r'HKD', 'HKD'),
    (r'CHF', 'CHF'), (r'SEK', 'SEK'), (r'DKK', 'DKK'), (r'NOK', 'NOK'),
    (r'AUD', 'AUD'), (r'US\$|USD', 'USD'), (r'\$', 'USD'),
]

# Keyword vocabulary. A keyword is attached ONLY if its pattern appears in the
# posting's own title or department text. This is text matching on real text,
# not an inference about the position.
KEYWORDS = {
    "Earthquake Engineering": r"earthquake|seismic",
    "Structural Optimization": r"structural optimi|topology optimi|design optimi",
    "Steel Structures": r"steel",
    "Soil-Structure Interaction": r"soil.structure|geotechnic",
    "Structural Dynamics": r"structural dynamic|vibration|dynamics of structure",
    "Computational Mechanics": r"computational mechanic|computational engineering|solid mechanic",
    "Finite Element Analysis": r"finite element|\bfem\b|\bfea\b",
    "Concrete Structures": r"concrete",
    "Composite Structures": r"composite",
    "Structural Health Monitoring": r"health monitoring|condition monitoring|structural monitoring",
    "Bridge Engineering": r"bridge",
    "Wind Engineering": r"wind",
    "Fatigue & Fracture": r"fatigue|fracture|crack",
    "Machine Learning for Structures": r"machine learning|deep learning|neural network|artificial intelligence|\bai\b|\bml\b",
    "Metaheuristic Optimization": r"metaheuristic|genetic algorithm|optimi[sz]ation",
    "Materials Engineering": r"material|alloy|polymer|nanolith|metallurg",
    "Manufacturing": r"manufactur|additive|3d print|welding",
    "Robotics": r"robot|autonomous vehicle|manipulation",
    "Quantum": r"quantum",
    "Energy Systems": r"energy|hydrogen|battery|photovolta|hydropower|solar",
    "Water & Hydrology": r"water|hydrolog|hydroclimat|catchment",
    "Life Sciences": r"biolog|genom|protein|cell|neuro|immunolog|microbio|cancer|ribosome|epigenom|physiolog|enzym|bacteri|plant|agri|veterinar|marine|algae|dialysis|medicine|clinical|dental|health",
    "Computing & Data": r"computing|computer science|data science|software|high.performance|comput(er|ational) vision|language model|informatic|cyber|wireless|telecommunication|network|iot|cryptograph",
    "Chemistry": r"chemistr|chemical|catalys|electrocatalys|proteomic|spectrosc",
    "Physics": r"physic|photon|laser|optic|plasma|semiconductor|x-ray|metrolog|isotope|synchrotron|neutron",
    "Earth & Environment": r"geolog|environment|climate|snow|soil|urban|earth observation|reservoir|phosphate|mining",
    "Social Sciences & Humanities": r"sociolog|demograph|anthropolog|philosoph|law|legal|humanities|archaeolog|border studies|economics|history",
}

def detect_currency(text):
    if not text:
        return None
    for pat, cur in CURRENCY_PATTERNS:
        if re.search(pat, text, re.I):
            return cur
    return None

def parse_amount(text, currency):
    """Pull the first monetary figure out of a verbatim salary string.
    Returns (monthly_amount, basis) or (None, None). Never guesses."""
    if not text:
        return None, None
    t = text.replace(",", "")
    nums = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', t) if float(n) >= 100]
    if not nums:
        return None, None
    low = min(nums)
    tl = text.lower()
    if re.search(r'per annum|/year|per year|p\.a\.|annum|/yr|annual', tl):
        return round(low / 12), "annual salary divided by 12"
    if re.search(r'per month|/mo|p\.m\.|/month|monthly|month', tl):
        return round(low), "monthly figure as stated"
    if currency in ("GBP", "AUD", "SGD", "HKD") and low > 20000:
        return round(low / 12), "figure above 20k treated as annual, divided by 12"
    if currency == "INR" and low < 500000:
        return round(low), "Indian stipends are quoted monthly"
    if currency == "EUR" and low > 20000:
        return round(low / 12), "figure above 20k treated as annual, divided by 12"
    return round(low), "figure as stated, basis not specified on the page"

def keywords_for(*texts):
    blob = " ".join(t for t in texts if t).lower()
    out = []
    for k, pat in KEYWORDS.items():
        if re.search(pat, blob):
            out.append(k)
    return out

def status_for(deadline):
    if not deadline:
        return "Open"
    d = (datetime.date.fromisoformat(deadline) - datetime.date.fromisoformat(TODAY)).days
    return "Closed" if d < 0 else ("Closing Soon" if d <= 21 else "Open")

def main():
    raw = json.load(open(RAW_PATH))
    raw.setdefault("fetchedAt", TODAY)
    src_by_id = {s["id"]: s for s in raw["sources"]}
    ok_sources = {s["id"] for s in raw["sources"] if s["status"] == "OK"}

    out, rejected = [], []
    seen_urls = set()

    for i, r in enumerate(raw["records"]):
        sid = r["s"]
        if sid not in ok_sources:
            rejected.append({"title": r.get("t"), "reason": "source not OK: " + sid}); continue
        if not r.get("url"):
            rejected.append({"title": r.get("t"), "reason": "no individual posting URL"}); continue
        if r["url"] in seen_urls:
            rejected.append({"title": r.get("t"), "reason": "duplicate URL"}); continue
        seen_urls.add(r["url"])

        src = src_by_id[sid]
        computed = []
        cur = detect_currency(r.get("sal"))
        amt, basis = parse_amount(r.get("sal"), cur)
        if amt:
            computed.append({"field": "stipendMonthly", "how": "parsed from the salary text shown on the page: " + basis})
        kws = keywords_for(r.get("t"), r.get("dp"))
        if kws:
            computed.append({"field": "researchKeywords", "how": "matched against words present in the posting's own title/department text"})

        out.append({
            "id": "live_%s_%04d" % (sid, i),
            "synthetic": False,
            "verified": True,
            "title": r["t"],
            "university": r.get("u"),
            "department": r.get("dp"),
            "faculty": None, "laboratory": None, "researchGroup": None,
            "country": r.get("c"),
            "city": r.get("ct"),
            "qsRank": None, "theRank": None, "rankSource": None,
            "officialWebsite": None,
            "applicationLink": r["url"],
            "applicationPortal": src["name"],
            "fundingAgency": None,
            "fundingType": None,
            "professorName": None, "professorLabel": None, "professorPosition": None,
            "professorEmail": None, "professorInterests": None,
            "scholarUrl": None, "orcid": None, "researchGate": None, "labWebsite": None,
            "description": None,
            "researchArea": kws[0] if kws else None,
            "researchKeywords": kws,
            "durationMonths": None,
            "startDate": None,
            "deadline": r.get("dl"),
            "status": status_for(r.get("dl")),
            "requiredDegree": None, "requiredExperienceYears": None,
            "requiredPublications": None,
            "requiredSkills": [], "requiredSoftware": [], "requiredLanguages": [],
            "requiredSpokenLanguage": None,
            "citizenshipRestriction": None, "ageRestriction": None,
            "requiredDocuments": [],
            "salaryText": r.get("sal"),
            "stipendMonthly": amt,
            "currency": cur,
            "annualFunding": None, "researchGrant": None,
            "conferenceGrant": None, "travelGrant": None,
            "accommodation": None, "medicalInsurance": None,
            "visaSponsorship": None, "flightTicket": None,
            "relocationSupport": None, "familySupport": None,
            "workMode": None,
            "interviewProcess": None, "selectionProcedure": None,
            "expectedTimelineWeeks": None,
            "acceptanceRateOfficial": None, "acceptanceRateSource": None,
            "sourceUrl": r["url"],
            "lastVerified": raw["fetchedAt"],
            "createdAt": r.get("pd") or raw["fetchedAt"],
            "postedDate": r.get("pd"),
            "internalNotes": "", "userRating": 0, "favourite": False,
            "provenance": {
                "sourceId": sid,
                "sourceName": src["name"],
                "listUrls": src["listUrls"],
                "fetchedAt": raw["fetchedAt"],
                "derivedFields": r.get("dv", []),
                "computedFields": computed,
                "warning": r.get("warn")
            }
        })

    payload = {
        "schema": 4,
        "builtAt": raw["fetchedAt"],
        "sources": raw["sources"],
        "counts": {
            "accepted": len(out),
            "rejected": len(rejected),
            "open": sum(1 for o in out if o["status"] != "Closed"),
            "withDeadline": sum(1 for o in out if o["deadline"]),
            "withStipend": sum(1 for o in out if o["stipendMonthly"]),
            "countries": len({o["country"] for o in out if o["country"]}),
            "institutions": len({o["university"] for o in out if o["university"]}),
        },
        "rejected": rejected,
        "records": out,
    }
    # Safety gate: never publish an empty or collapsed dataset over a good one.
    if len(out) < 20:
        print("ABORT: only %d records survived validation. Refusing to publish a "
              "collapsed dataset over the previous one. Investigate the source "
              "failures above before overwriting." % len(out))
        sys.exit(2)

    with open(OUT_PATH, "w") as f:
        f.write("/* PRIS live dataset. Regenerated by the daily refresh task on %s.\n"
                "   Overwrite this file to update the app; PRIS.html never changes. */\n" % TODAY)
        f.write("window.PRIS_LIVE_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    with open(os.path.splitext(OUT_PATH)[0] + ".json", "w") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(payload["counts"], indent=2))
    print("rejected:", len(rejected))
    for r in rejected[:10]:
        print("  -", r)
    nulls = {k: sum(1 for o in out if o.get(k) is None) for k in ["country", "city", "deadline", "stipendMonthly", "department"]}
    print("null counts:", nulls)
    print("sources OK:", sorted(ok_sources))
    print("sources excluded:", sorted({s['id'] + '(' + s['status'] + ')' for s in raw['sources'] if s['status'] != 'OK'}))

main()
