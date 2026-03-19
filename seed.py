"""
Seed the database with ministries, subjects, and sample articles.
Run once: python seed.py
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.models import Base, Ministry, Subject, Article, ArticleTag, MCQ, MainsQuestion
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
import uuid
from datetime import date

MINISTRIES = [
    ("MoHFW",  "Ministry of Health and Family Welfare",         "Health"),
    ("MEA",    "Ministry of External Affairs",                   "External Affairs"),
    ("MoF",    "Ministry of Finance",                            "Finance"),
    ("MoD",    "Ministry of Defence",                            "Defence"),
    ("MoE",    "Ministry of Education",                          "Education"),
    ("MoEFCC", "Ministry of Environment, Forest & Climate Change","Environment"),
    ("MoRD",   "Ministry of Rural Development",                  "Rural Dev"),
    ("MoLE",   "Ministry of Labour and Employment",              "Labour"),
    ("DST",    "Department of Science and Technology",           "Science & Tech"),
    ("MoNRE",  "Ministry of New and Renewable Energy",           "Renewable Energy"),
    ("MoRTH",  "Ministry of Road Transport and Highways",        "Road Transport"),
    ("MoCI",   "Ministry of Commerce and Industry",              "Commerce"),
    ("DoT",    "Department of Telecommunications",               "Telecom"),
    ("MHA",    "Ministry of Home Affairs",                       "Home Affairs"),
    ("MoPR",   "Ministry of Panchayati Raj",                     "Panchayati Raj"),
]

SUBJECTS = [
    ("polity",       "Polity & Constitution",         "gs2"),
    ("economy",      "Economy & Budget",              "gs3"),
    ("science-tech", "Science & Technology",          "gs3"),
    ("environment",  "Environment & Ecology",         "gs3"),
    ("ir",           "International Relations",       "gs2"),
    ("security",     "Security & Internal Security",  "gs3"),
    ("schemes",      "Schemes & Policies",            "gs2"),
    ("history",      "History & Culture",             "gs1"),
    ("geography",    "Geography",                     "gs1"),
    ("governance",   "Governance & Social Justice",   "gs2"),
]

SAMPLE_ARTICLES = [
    {
        "title": "Cabinet approves National Green Hydrogen Mission — ₹19,744 Cr outlay for 5 MMTPA target by 2030",
        "body": "The Union Cabinet has approved the National Green Hydrogen Mission with a total outlay of ₹19,744 crore. The mission aims to make India a global hub for production, use and export of green hydrogen. The SIGHT programme focuses on electrolyser manufacturing. Target: 5 MMT per annum by 2030, 125 GW renewable energy addition.",
        "source_url": "https://pib.gov.in/green-hydrogen-mission",
        "published_at": date.today(),
        "relevance_score": 5,
        "high_prelims": True,
        "high_mains": True,
        "content_type": "scheme",
        "relevance_note": "New scheme with specific targets, budget & international linkages — UPSC loves this combination.",
        "snippet_what": "National Green Hydrogen Mission; 5 MMTPA by 2030; ₹19,744 Cr; SIGHT programme for electrolyser manufacturing",
        "snippet_why": "Energy security + climate commitments; India's NDC targets; decarbonisation of hard-to-abate sectors",
        "snippet_gs": "gs3",
        "snippet_prelims": True,
        "snippet_pyq": "Similar to 2019 hydrogen fuel question and 2021 green energy missions",
        "ministry": "MoNRE",
        "subjects": ["environment", "schemes"],
        "mcqs": [
            {
                "question": "Consider the following statements about the National Green Hydrogen Mission:\n1. It targets production of 5 MMTPA of green hydrogen by 2030.\n2. The SIGHT programme focuses on solar panel manufacturing.\n3. Its nodal ministry is the Ministry of New & Renewable Energy.\nWhich of the statements given above is/are correct?",
                "options": ["A. 1 and 2 only", "B. 1 and 3 only", "C. 2 and 3 only", "D. 1, 2 and 3"],
                "correct_index": 1,
                "nature": "factual",
                "explanation": "Statement 2 is incorrect — SIGHT (Strategic Interventions for Green Hydrogen Transition) focuses on electrolyser manufacturing, not solar panels. Statements 1 and 3 are correct. This mirrors the UPSC 2021 statement-based format.",
                "pyq_link": "Similar format used in 2019 for National Mission for Clean Ganga (NMCG).",
            },
        ],
        "mains": [
            {
                "question": "Critically analyse the National Green Hydrogen Mission in the context of India's energy security and climate commitments. How does it address the challenge of decarbonising hard-to-abate sectors?",
                "gs_paper": "gs3",
                "word_limit": 250,
            }
        ],
    },
    {
        "title": "SC bench rules on validity of Electoral Bonds Scheme — questions on Article 19(1)(a) and Right to Information",
        "body": "A five-judge Constitution bench of the Supreme Court unanimously struck down the Electoral Bonds Scheme, ruling it violated voters' fundamental right to information under Article 19(1)(a). The bench directed SBI to submit all bond details to the Election Commission of India for public disclosure.",
        "source_url": "https://pib.gov.in/electoral-bonds-sc",
        "published_at": date.today(),
        "relevance_score": 5,
        "high_prelims": True,
        "high_mains": True,
        "content_type": "judgment",
        "relevance_note": "Constitutional law + electoral reforms = guaranteed UPSC territory. Article 19(1)(a) nexus is key Mains argument.",
        "snippet_what": "SC struck down Electoral Bonds; Right to know political funding under Art 19(1)(a); SBI directed to share data with ECI",
        "snippet_why": "Electoral reforms, transparency, constitutional morality — perennial Mains themes",
        "snippet_gs": "gs2",
        "snippet_prelims": True,
        "snippet_pyq": "2017 RTI Act; 2020 Electoral reforms; 2022 Role of ECI",
        "ministry": "MHA",
        "subjects": ["polity", "governance"],
        "mcqs": [
            {
                "question": "With reference to the Supreme Court judgment on Electoral Bonds Scheme, consider the following:\n1. The scheme was struck down on grounds of violating Article 19(1)(a).\n2. The State Bank of India was directed to submit bond details to the Election Commission.\n3. The judgment was given by a three-judge bench.\nWhich of the statements given above is/are correct?",
                "options": ["A. 1 only", "B. 1 and 2 only", "C. 2 and 3 only", "D. 1, 2 and 3"],
                "correct_index": 1,
                "nature": "factual",
                "explanation": "Statement 3 is incorrect — it was a five-judge Constitution bench. Statements 1 and 2 are correct. Article 19(1)(a) guarantees Freedom of Speech including the right to know political funding.",
                "pyq_link": "UPSC 2020 asked about Electoral Bond denominations and issuing authority.",
            },
        ],
        "mains": [
            {
                "question": "The Supreme Court's verdict on Electoral Bonds has reignited debates on political funding transparency in India. Critically examine the judgment in light of constitutional provisions and democratic principles.",
                "gs_paper": "gs2",
                "word_limit": 250,
            }
        ],
    },
]

async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Seed ministries
        min_map = {}
        for code, name, short in MINISTRIES:
            m = Ministry(id=str(uuid.uuid4()), code=code, name=name, short_name=short)
            db.add(m)
            min_map[code] = m

        # Seed subjects
        sub_map = {}
        for slug, label, gs in SUBJECTS:
            s = Subject(id=str(uuid.uuid4()), slug=slug, label=label, gs_paper=gs)
            db.add(s)
            sub_map[slug] = s

        await db.flush()

        # Seed sample articles
        for adata in SAMPLE_ARTICLES:
            article = Article(
                id=str(uuid.uuid4()),
                title=adata["title"],
                body=adata["body"],
                source_url=adata["source_url"],
                published_at=adata["published_at"],
                relevance_score=adata["relevance_score"],
                high_prelims=adata["high_prelims"],
                high_mains=adata["high_mains"],
                content_type=adata["content_type"],
                relevance_note=adata["relevance_note"],
                snippet_what=adata["snippet_what"],
                snippet_why=adata["snippet_why"],
                snippet_gs=adata["snippet_gs"],
                snippet_prelims=adata["snippet_prelims"],
                snippet_pyq=adata["snippet_pyq"],
            )
            db.add(article)
            await db.flush()

            # Ministry tag
            if adata["ministry"] in min_map:
                db.add(ArticleTag(id=str(uuid.uuid4()), article_id=article.id, ministry_id=min_map[adata["ministry"]].id))

            # Subject tags
            for slug in adata["subjects"]:
                if slug in sub_map:
                    db.add(ArticleTag(id=str(uuid.uuid4()), article_id=article.id, subject_id=sub_map[slug].id))

            # MCQs
            for mdata in adata.get("mcqs", []):
                db.add(MCQ(
                    id=str(uuid.uuid4()),
                    article_id=article.id,
                    question=mdata["question"],
                    options=mdata["options"],
                    correct_index=mdata["correct_index"],
                    nature=mdata["nature"],
                    explanation=mdata["explanation"],
                    pyq_link=mdata["pyq_link"],
                    admin_approved=True,
                ))

            # Mains
            for mqdata in adata.get("mains", []):
                db.add(MainsQuestion(
                    id=str(uuid.uuid4()),
                    article_id=article.id,
                    question=mqdata["question"],
                    gs_paper=mqdata["gs_paper"],
                    word_limit=mqdata["word_limit"],
                    admin_approved=True,
                ))

        await db.commit()
        print("Database seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed())
