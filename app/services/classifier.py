"""
Rule-based classifier for auto-tagging articles.
Fast, offline, no model dependencies.
Can be upgraded to a fine-tuned BERT classifier later.
"""
from typing import Tuple, List, Optional
import re

# ── Keyword maps ──────────────────────────────────────────────────────────────

CONTENT_TYPE_RULES = [
    (["scheme", "yojana", "mission", "programme", "initiative", "pm scheme"],  "scheme"),
    (["report", "committee", "panel", "commission", "taskforce"],              "report"),
    (["judgment", "verdict", "order", "sc rules", "hc rules", "bench"],        "judgment"),
    (["agreement", "mou", "treaty", "bilateral", "partnership", "pact"],       "agreement"),
    (["policy", "act", "bill", "amendment", "ordinance"],                      "policy"),
    (["index", "ranking", "report card", "scorecard"],                         "index"),
]

PRELIMS_TRIGGERS = [
    "scheme", "mission", "yojana", "act", "amendment", "mou", "treaty",
    "index", "ranking", "summit", "committee", "g20", "brics", "sco",
    "isro", "drdo", "quantum", "satellite", "supreme court", "constitution",
    "sdg", "unfccc", "cop", "who", "wto", "imf", "world bank",
]

MAINS_TRIGGERS = [
    "governance", "policy", "reform", "challenge", "analysis", "implication",
    "bilateral", "foreign policy", "economy", "growth", "sustainable",
    "social", "welfare", "poverty", "inequality", "education", "health",
    "security", "defence", "internal", "environment", "climate",
]

SUBJECT_RULES = [
    ("polity", [
        "constitution", "parliament", "lok sabha", "rajya sabha", "election",
        "electoral", "supreme court", "high court", "fundamental rights",
        "directive principles", "amendment", "article ", "preamble",
        "federalism", "governor", "president", "cabinet", "bill passed",
    ], "gs2"),
    ("economy", [
        "gdp", "inflation", "rbi", "repo rate", "monetary policy", "budget",
        "fiscal deficit", "gst", "tax", "trade deficit", "export", "import",
        "fdi", "msme", "banking", "insurance", "sebi", "ibc", "insolvency",
        "economic survey", "union budget", "revenue", "expenditure",
    ], "gs3"),
    ("science-tech", [
        "quantum", "ai ", "artificial intelligence", "machine learning",
        "isro", "drdo", "satellite", "rocket", "mission moon", "gaganyaan",
        "nuclear", "missile", "5g", "6g", "semiconductor", "biotech",
        "genome", "crispr", "nanotechnology", "robotics", "drone",
    ], "gs3"),
    ("environment", [
        "climate", "biodiversity", "forest", "wildlife", "endangered",
        "pollution", "carbon", "emission", "net zero", "renewable energy",
        "solar", "wind", "electric vehicle", "ev", "mangrove", "coral",
        "unfccc", "cop", "paris agreement", "ndc", "green hydrogen",
        "plastic", "waste", "water crisis", "glacier", "deforestation",
    ], "gs3"),
    ("ir", [
        "bilateral", "foreign minister", "mea", "embassy", "consulate",
        "g20", "g7", "brics", "sco", "asean", "saarc", "quad",
        "un ", "united nations", "security council", "nato", "eu ",
        "china", "pakistan", "usa", "russia", "india-", "treaty",
        "summit ", "diplomatic",
    ], "gs2"),
    ("security", [
        "defence", "military", "army", "navy", "air force", "drdo",
        "terrorism", "naxal", "ltte", "insurgency", "border dispute",
        "lac", "loc", "cyber attack", "cyber security", "coast guard",
        "internal security", "nsg", "para military",
    ], "gs3"),
    ("schemes", [
        "pm ", "pradhan mantri", "yojana", "abhiyan", "mission",
        "welfare scheme", "direct benefit", "dbt", "jan dhan",
        "ayushman bharat", "pmay", "pmgsy", "mgnrega", "swachh bharat",
        "digital india", "skill india", "make in india", "startup india",
    ], "gs2"),
    ("history", [
        "heritage", "culture", "museum", "monument", "archaeological",
        "unesco", "freedom fighter", "independence", "partition",
        "ancient", "medieval", "colonial", "tribal culture", "folk",
    ], "gs1"),
    ("geography", [
        "geography", "river", "mountain", "himalayas", "plateau",
        "cyclone", "earthquake", "flood", "drought", "disaster",
        "climate zone", "monsoon", "tectonic", "watershed", "delta",
    ], "gs1"),
    ("governance", [
        "governance", "transparency", "accountability", "rtl", "rti",
        "e-governance", "digital india", "panchayati raj", "urban local",
        "decentralization", "corruption", "lokpal", "ombudsman",
        "police reform", "judicial reform", "niti aayog",
    ], "gs2"),
]

def classify_article(title: str, body: str) -> dict:
    text = (title + " " + (body or "")).lower()

    # Content type
    content_type = "update"
    for keywords, ctype in CONTENT_TYPE_RULES:
        if any(kw in text for kw in keywords):
            content_type = ctype
            break

    # Subjects (up to 3)
    matched_subjects = []
    for slug, keywords, gs_paper in SUBJECT_RULES:
        if any(kw in text for kw in keywords):
            matched_subjects.append((slug, gs_paper))
        if len(matched_subjects) >= 3:
            break

    # Relevance score (1-5)
    score = 2
    high_value_terms = [
        "scheme", "mission", "supreme court", "treaty", "g20", "budget",
        "amendment", "act", "yojana", "bilateral", "isro", "quantum",
        "nuclear", "index", "ranking", "committee report",
    ]
    score += sum(1 for t in high_value_terms if t in text)
    score = min(score, 5)

    # Prelims / Mains flags
    high_prelims = (
        score >= 4 or
        any(t in text for t in PRELIMS_TRIGGERS[:15])
    )
    high_mains = (
        any(t in text for t in MAINS_TRIGGERS[:10]) or
        content_type in ["scheme", "policy", "judgment"]
    )

    # Relevance note
    subject_labels = [s[0].replace("-", " & ").title() for s, _ in matched_subjects[:2]]
    relevance_note = ""
    if subject_labels:
        relevance_note = f"Relevant to {', '.join(subject_labels)}."
    if high_prelims:
        relevance_note += " High Prelims relevance — key data points likely."
    if high_mains:
        relevance_note += " Good Mains angle available."

    return {
        "content_type": content_type,
        "subjects": matched_subjects,
        "relevance_score": score,
        "high_prelims": high_prelims,
        "high_mains": high_mains,
        "relevance_note": relevance_note.strip(),
    }
