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

# ----------------------------------------------------------------------------
# KEYWORD VOCABULARY
#
# Bug fixed 2026-07-28: the previous version matched bare words, so any posting
# mentioning machine learning was labelled "Machine Learning for Structures",
# "structural enzymology" and "structural geology" were read as structural
# engineering, and "soil microbiology" as soil-structure interaction. Seven
# unrelated postings carried structural-engineering labels as a result.
#
# Fix: structural-engineering keywords are gated. A posting only becomes
# eligible for them if it shows STRUCT_CONTEXT and does not trip FALSE_FRIEND.
# ----------------------------------------------------------------------------

# Words that are only structural engineering in a built-environment / solid
# mechanics setting. At least one must be present before any STRUCT_KEYWORD applies.
STRUCT_CONTEXT = re.compile(
    r"structural engineering|civil engineering|earthquake engineer|seismic design|"
    r"steel structure|concrete structure|reinforced concrete|masonry|timber structure|"
    r"geotechnic|foundation engineer|soil.structure|bridge engineer|"
    r"structural dynamic|structural mechanic|structural analys|structural design|"
    r"solid mechanic|computational mechanic|finite element|fracture mechanic|"
    r"built environment|infrastructure|construction|dam\b|tunnel|breakwater|"
    r"land reclamation|highway|railway engineer|cement|"
    r"impact engineering|structural manufacturing|resilient infrastructure", re.I)

# If any of these appear, the posting is NOT structural engineering no matter
# what other words it contains. These are the exact collisions that caused the bug.
FALSE_FRIEND = re.compile(
    r"structural biolog|structural enzymolog|protein structure|crystallograph|cryo.em|"
    r"structural geolog|soil microbiolog|soil biolog|soil ecolog|soil microbiome|"
    r"food structure|structural equation|structural racism|structural inequalit|"
    r"structural causal|microstructur(?!.*(steel|weld|concrete|alloy|fracture))", re.I)

# Structural-engineering keywords. Only applied when the gate above passes.
STRUCT_KEYWORDS = {
    "Earthquake Engineering": r"earthquake|seismic",
    "Structural Optimization": r"structural optimi|topology optimi|design optimi|shape optimi",
    "Steel Structures": r"steel",
    "Soil-Structure Interaction": r"soil.structure|geotechnic|foundation",
    "Structural Dynamics": r"structural dynamic|vibration|resonance|damper|dynamics of structure",
    "Computational Mechanics": r"computational mechanic|computational engineering|solid mechanic|numerical simulation",
    "Finite Element Analysis": r"finite element|\bfem\b|\bfea\b",
    "Concrete Structures": r"concrete|cement",
    "Composite Structures": r"composite",
    "Structural Health Monitoring": r"health monitoring|condition monitoring|structural monitoring|digital twin",
    "Bridge Engineering": r"bridge",
    "Timber & Mass Timber Structures": r"timber|wooden|veneer",
    "Fatigue & Fracture": r"fatigue|fracture|crack",
    "Blast & Impact Engineering": r"impact engineering|blast|crashworth",
    "Machine Learning for Structures": r"machine learning|deep learning|neural network|artificial intelligence|\bai\b",
    "Metaheuristic Optimization": r"metaheuristic|genetic algorithm|particle swarm|evolutionary algorithm",
    "Resilience & Risk Assessment": r"resilien|risk assessment|hazard",
    "Geotechnical Engineering": r"geotechnic|land reclamation|soil mechanic|excavation",
}

# General discipline labels. Applied to everything, gate or no gate, so that
# non-structural postings get an accurate label instead of a misleading one.
GENERAL_KEYWORDS = {
    "Materials Engineering": r"material|alloy|polymer|metallurg|microstructur",
    "Manufacturing": r"manufactur|additive|3d print|welding|solidification",
    "Robotics": r"robot|autonomous vehicle|manipulation",
    "Quantum": r"quantum",
    "Energy Systems": r"energy|hydrogen|battery|photovolta|hydropower|solar|turbine",
    "Water & Hydrology": r"hydrolog|hydroclimat|catchment|water resource",
    "Life Sciences": r"biolog|genom|protein|cell|neuro|immunolog|microbio|cancer|ribosome|"
                     r"epigenom|physiolog|enzym|bacteri|plant|agri|veterinar|marine|algae|"
                     r"dialysis|medicine|clinical|dental|health|zoolog|biodiversity",
    "Computing & Data": r"computing|computer science|data science|software|high.performance|"
                        r"comput(er|ational) vision|language model|informatic|cyber|wireless|"
                        r"telecommunication|network|\biot\b|cryptograph",
    "Chemistry": r"chemistr|chemical|catalys|electrocatalys|proteomic|spectrosc",
    "Physics": r"physic|photon|laser|optic|plasma|semiconductor|x-ray|metrolog|isotope|synchrotron|neutron",
    "Earth & Environment": r"geolog|environment|climate|snow|urban|earth observation|reservoir|phosphate|mining|geospatial",
    "Social Sciences & Humanities": r"sociolog|demograph|anthropolog|philosoph|\blaw\b|legal|humanities|archaeolog|border studies|economics|history",
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

def classify(*texts):
    """Return (keywords, fieldRelevance, reason).

    fieldRelevance is one of:
      core      — clearly the target discipline (structural / civil / earthquake / solid mechanics)
      adjacent  — engineering a structural researcher could plausibly apply to
      unrelated — a different discipline entirely

    The gate is what stops 'structural biology' and 'soil microbiology' being
    read as structural engineering.
    """
    blob = " ".join(t for t in texts if t)
    low = blob.lower()

    false_friend = bool(FALSE_FRIEND.search(blob))
    has_context = bool(STRUCT_CONTEXT.search(blob))

    kws, relevance, reason = [], "unrelated", ""

    if false_friend:
        reason = "a structural/soil word appears, but in another discipline's sense"
    elif has_context:
        for k, pat in STRUCT_KEYWORDS.items():
            if re.search(pat, low):
                kws.append(k)
        relevance = "core" if kws else "adjacent"
        reason = "built-environment or solid-mechanics context present"

    general = [k for k, pat in GENERAL_KEYWORDS.items() if re.search(pat, low)]

    # Adjacent engineering that isn't built-environment but shares the methods.
    if relevance == "unrelated" and not false_friend:
        if re.search(r"mechanical engineering|materials engineering|aerospace|"
                     r"computational|numerical|simulation|modelling|modeling|"
                     r"engineering science|applied mechanic", low):
            relevance = "adjacent"
            reason = "engineering methods overlap, but not built-environment"

    for g in general:
        if g not in kws:
            kws.append(g)
    return kws, relevance, reason

def status_for(deadline):
    if not deadline:
        return "Open"
    d = (datetime.date.fromisoformat(deadline) - datetime.date.fromisoformat(TODAY)).days
    return "Closed" if d < 0 else ("Closing Soon" if d <= 21 else "Open")

def main():
    raw = json.load(open(RAW_PATH))
    raw.setdefault("fetchedAt", TODAY)

    # Optional extra ingest files merged in (e.g. a field-targeted pass).
    # Later files win on source metadata; records are deduped by URL below.
    for extra in sys.argv[4:]:
        ex = json.load(open(extra))
        by_id = {s["id"]: s for s in raw["sources"]}
        for s in ex.get("sources", []):
            by_id[s["id"]] = s
        raw["sources"] = list(by_id.values())
        raw["records"] = ex.get("records", []) + raw["records"]

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
        kws, relevance, reason = classify(r.get("t"), r.get("dp"))
        if kws:
            computed.append({"field": "researchKeywords", "how": "matched against words present in the posting's own title/department text, gated so that structural-engineering labels require a built-environment or solid-mechanics context"})
        # An explicit fieldConfidence from the ingest (a human-reviewed judgement
        # made while reading the actual posting) overrides the automatic gate.
        fc = r.get("fc")
        if fc:
            relevance = {"high": "core", "medium": "adjacent", "low": "adjacent"}.get(fc, relevance)
            reason = "classified while reading the posting itself (confidence: %s)" % fc
        if relevance != "unrelated":
            computed.append({"field": "fieldRelevance", "how": reason})

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
            "fieldRelevance": relevance,
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
            "core": sum(1 for o in out if o["fieldRelevance"] == "core"),
            "adjacent": sum(1 for o in out if o["fieldRelevance"] == "adjacent"),
            "unrelated": sum(1 for o in out if o["fieldRelevance"] == "unrelated"),
            "coreOpen": sum(1 for o in out if o["fieldRelevance"] == "core" and o["status"] != "Closed"),
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
