"""
Keyword-based sector classifier for Indian policy items.
Maps policy text (title + description) to one or more development sectors.
No ML dependencies — runs fast in GitHub Actions.
"""

# ─────────────────────────────────────────────────────────────────────────
# Media / news sources. These are newspapers, TV, wires and opinion outlets:
# they carry *coverage* of policy, not primary policy. Every item from one of
# these sources is level == "media" regardless of what its feed config says,
# so the policy-only views (ticker, charts, era comparison) exclude them and
# the media cap governs how much news reaches the homepage. Keyed by
# source_id. This is the single source of truth — the site (data.ts) mirrors
# it. Government press wires (pib_rss) are NOT here; they are primary sources.
# ─────────────────────────────────────────────────────────────────────────
MEDIA_SOURCE_IDS = frozenset({
    # The Hindu group
    "the_hindu_policy", "the_hindu_business", "thehindu_rss", "bl_rss",
    "frontline_mag",
    # Hindustan Times / Mint
    "ht_rss", "hindustan_times", "livemint_rss", "mint_opinion",
    # NDTV
    "ndtv_rss", "ndtv_india",
    # Indian Express
    "indian_express_business", "indian_express_policy",
    # Other papers / TV / wires
    "deccan_chronicle", "republic_world", "scroll", "india_today",
    "indiatoday_rss", "the_wire", "firstpost_india", "news18_india",
    "news18_rss", "the_print", "al_jazeera_india", "outlook_india",
    "asian_age", "tribune_india", "moneycontrol", "ani_news", "pti_news",
    "print_diplomacy",
    # Legal news (report on cases; primary judgments come from the courts)
    "livelaw", "barandbench",
    # Features / govtech / fact-check journalism
    "factchecker", "villagesquare", "govinsider", "ecgov",
    # Exam-prep / current-affairs digests
    "drishti_ias", "drishtiias_rss", "insights_ias",
    # Opinion magazines
    "article14", "caravanmag", "swarajya_mag",
})


def is_media_source(source_id: str) -> bool:
    """True if source_id is a news/media outlet (level should be 'media')."""
    return source_id in MEDIA_SOURCE_IDS


# ─────────────────────────────────────────────────────────────────────────
# Source authority. Who published an item bounds what it can BE: a newspaper
# can never produce a "policy" — only coverage of one; a think tank produces
# analysis, not notifications. The old categorize_item_type() ignored this
# and typed a tattoo-art feature as "policy" because no keyword matched.
#
# Authority is resolved per source_id: explicit `authority` in feeds.json
# wins, then the media list, then the short_name map below (mirrors
# SOURCE_TYPE_MAP in src/lib/data.ts), then default "government" (feeds.json
# is overwhelmingly official sources).
# ─────────────────────────────────────────────────────────────────────────

AUTHORITY_GOVERNMENT = "government"      # ministries, PIB, departments, state govts
AUTHORITY_REGULATOR = "regulator"        # RBI, SEBI, TRAI, IRDAI, ...
AUTHORITY_LEGAL = "legal"                # courts, tribunals, gazettes, India Code
AUTHORITY_PARLIAMENT = "parliament"      # Lok/Rajya Sabha, PRS bill track
AUTHORITY_THINK_TANK = "think_tank"      # research institutes, universities
AUTHORITY_INTERNATIONAL = "international"  # World Bank, UN agencies
AUTHORITY_MEDIA = "media"                # journalism

# Official authorities — these can issue policy instruments.
OFFICIAL_AUTHORITIES = frozenset({
    AUTHORITY_GOVERNMENT, AUTHORITY_REGULATOR, AUTHORITY_LEGAL,
    AUTHORITY_PARLIAMENT,
})

# short_name → authority (only the non-government cases; government is the
# default). Kept in sync with SOURCE_TYPE_MAP in src/lib/data.ts.
_AUTHORITY_BY_SHORT = {
    # Regulators
    'RBI': AUTHORITY_REGULATOR, 'SEBI': AUTHORITY_REGULATOR, 'TRAI': AUTHORITY_REGULATOR,
    'IRDAI': AUTHORITY_REGULATOR, 'CCI': AUTHORITY_REGULATOR, 'CERC': AUTHORITY_REGULATOR,
    'CPCB': AUTHORITY_REGULATOR, 'FSSAI': AUTHORITY_REGULATOR, 'DGFT': AUTHORITY_REGULATOR,
    'CBIC': AUTHORITY_REGULATOR, 'CBDT': AUTHORITY_REGULATOR, 'IBBI': AUTHORITY_REGULATOR,
    'NABARD': AUTHORITY_REGULATOR, 'SIDBI': AUTHORITY_REGULATOR, 'NHB': AUTHORITY_REGULATOR,
    'UGC': AUTHORITY_REGULATOR, 'AICTE': AUTHORITY_REGULATOR, 'NMC': AUTHORITY_REGULATOR,
    'DGCA': AUTHORITY_REGULATOR, 'EPFO': AUTHORITY_REGULATOR, 'ESIC': AUTHORITY_REGULATOR,
    'NPCI': AUTHORITY_REGULATOR, 'PFRDA': AUTHORITY_REGULATOR, 'RERA': AUTHORITY_REGULATOR,
    # Legal
    'India Code': AUTHORITY_LEGAL, 'eGazette': AUTHORITY_LEGAL, 'SCI': AUTHORITY_LEGAL,
    'Law Comm': AUTHORITY_LEGAL, 'SCO': AUTHORITY_LEGAL, 'NLSIU': AUTHORITY_THINK_TANK,
    'Vidhi': AUTHORITY_THINK_TANK,
    'NCLAT': AUTHORITY_LEGAL, 'NCLT': AUTHORITY_LEGAL, 'ITAT': AUTHORITY_LEGAL,
    'TDSAT': AUTHORITY_LEGAL, 'NGT': AUTHORITY_LEGAL, 'Lokpal': AUTHORITY_LEGAL,
    'CVC': AUTHORITY_LEGAL, 'BCI': AUTHORITY_LEGAL, 'WB Gaz': AUTHORITY_LEGAL,
    # Parliament
    'Lok Sabha': AUTHORITY_PARLIAMENT, 'Rajya Sabha': AUTHORITY_PARLIAMENT,
    'PRS Bills': AUTHORITY_PARLIAMENT, 'PRS': AUTHORITY_PARLIAMENT,
    # Think tanks / research
    'ORF': AUTHORITY_THINK_TANK, 'ORF Health': AUTHORITY_THINK_TANK,
    'CPR': AUTHORITY_THINK_TANK, 'ICRIER': AUTHORITY_THINK_TANK,
    'Brookings': AUTHORITY_THINK_TANK, 'Carnegie': AUTHORITY_THINK_TANK,
    'CSDS': AUTHORITY_THINK_TANK, 'EPW': AUTHORITY_THINK_TANK,
    'CEEW': AUTHORITY_THINK_TANK, 'TERI': AUTHORITY_THINK_TANK,
    'CPPR': AUTHORITY_THINK_TANK, 'CUTS': AUTHORITY_THINK_TANK,
    'IIMB': AUTHORITY_THINK_TANK, 'Takshashila': AUTHORITY_THINK_TANK,
    'CSE': AUTHORITY_THINK_TANK, 'CBGA': AUTHORITY_THINK_TANK,
    'IWWAGE': AUTHORITY_THINK_TANK, 'J-PAL': AUTHORITY_THINK_TANK,
    'NCAER': AUTHORITY_THINK_TANK, 'IDFC': AUTHORITY_THINK_TANK,
    'NIPFP': AUTHORITY_THINK_TANK, 'IndiaSpend': AUTHORITY_THINK_TANK,
    'NASSCOM': AUTHORITY_THINK_TANK, 'FICCI': AUTHORITY_THINK_TANK,
    'CII': AUTHORITY_THINK_TANK, 'APU': AUTHORITY_THINK_TANK,
    'RIS': AUTHORITY_THINK_TANK, 'IIHS': AUTHORITY_THINK_TANK,
    'IGIDR': AUTHORITY_THINK_TANK, 'SPRF': AUTHORITY_THINK_TANK,
    'IIPS': AUTHORITY_THINK_TANK, 'GatewayH': AUTHORITY_THINK_TANK,
    'ChathamH': AUTHORITY_THINK_TANK, 'CSIS': AUTHORITY_THINK_TANK,
    'IndiaFound': AUTHORITY_THINK_TANK, 'MP-IDSA': AUTHORITY_THINK_TANK,
    'AI-CPRG': AUTHORITY_THINK_TANK, 'Janaagraha': AUTHORITY_THINK_TANK,
    'Praja': AUTHORITY_THINK_TANK, 'Oxfam': AUTHORITY_THINK_TANK,
    'WiproF': AUTHORITY_THINK_TANK, 'SAV': AUTHORITY_THINK_TANK,
    'India Forum': AUTHORITY_THINK_TANK, 'I4I': AUTHORITY_THINK_TANK,
    # International
    'World Bank': AUTHORITY_INTERNATIONAL, 'UNDP': AUTHORITY_INTERNATIONAL,
    'IMF': AUTHORITY_INTERNATIONAL, 'ADB': AUTHORITY_INTERNATIONAL,
    'UNICEF': AUTHORITY_INTERNATIONAL, 'WHO': AUTHORITY_INTERNATIONAL,
    'ILO': AUTHORITY_INTERNATIONAL, 'FAO': AUTHORITY_INTERNATIONAL,
    'OECD': AUTHORITY_INTERNATIONAL, 'WTO': AUTHORITY_INTERNATIONAL,
    'IFC': AUTHORITY_INTERNATIONAL, 'UNEP': AUTHORITY_INTERNATIONAL,
    'UNDESA': AUTHORITY_INTERNATIONAL, 'UNFPA': AUTHORITY_INTERNATIONAL,
    'UNHCR': AUTHORITY_INTERNATIONAL,
}

# source_id → authority for sources whose short_name is ambiguous.
_AUTHORITY_BY_ID = {
    'prs_legislative': AUTHORITY_PARLIAMENT,
    'prs_bills': AUTHORITY_PARLIAMENT,
    'parliament_lok_sabha': AUTHORITY_PARLIAMENT,
    'parliament_rajya_sabha': AUTHORITY_PARLIAMENT,
    'pib_lok_sabha_secretariat': AUTHORITY_PARLIAMENT,
    'pib_rajya_sabha_secretariat': AUTHORITY_PARLIAMENT,
    'pib_parliamentary_affairs': AUTHORITY_PARLIAMENT,
    'india_code': AUTHORITY_LEGAL,
    'india_code_history': AUTHORITY_LEGAL,
    'egazette': AUTHORITY_LEGAL,
    'delhi_hc': AUTHORITY_LEGAL,
    'azim_premji': AUTHORITY_THINK_TANK,
    'actionaid': AUTHORITY_THINK_TANK,
    'aser': AUTHORITY_THINK_TANK,
    'epod_harvard': AUTHORITY_THINK_TANK,
    'ibef': AUTHORITY_THINK_TANK,
    'idronline': AUTHORITY_THINK_TANK,
    'lse_southasia': AUTHORITY_THINK_TANK,
    'pratham': AUTHORITY_THINK_TANK,
    'savechildren': AUTHORITY_THINK_TANK,
    'india_forum': AUTHORITY_THINK_TANK,
    'ideas_for_india': AUTHORITY_THINK_TANK,
    'adb_india_new': AUTHORITY_INTERNATIONAL,
    'unicef_india': AUTHORITY_INTERNATIONAL,
    'who_india_new': AUTHORITY_INTERNATIONAL,
    'rbi_notifications': AUTHORITY_REGULATOR,
    'up_rera': AUTHORITY_REGULATOR,
    'cdsl': AUTHORITY_REGULATOR,
    'policyradar': AUTHORITY_MEDIA,
}


def get_source_authority(source_id: str, source_config: dict | None = None) -> str:
    """Resolve the authority tier for a source. Order: explicit config
    `authority` → media list → source_id map → short_name map → government."""
    cfg = source_config or {}
    explicit = cfg.get("authority", "")
    if explicit:
        return explicit
    if source_id in MEDIA_SOURCE_IDS:
        return AUTHORITY_MEDIA
    if source_id in _AUTHORITY_BY_ID:
        return _AUTHORITY_BY_ID[source_id]
    short = cfg.get("short_name", "")
    if short in _AUTHORITY_BY_SHORT:
        return _AUTHORITY_BY_SHORT[short]
    if cfg.get("level") == "media" or not cfg.get("india_only", True):
        return AUTHORITY_MEDIA
    return AUTHORITY_GOVERNMENT


# ─────────────────────────────────────────────────────────────────────────
# Document taxonomy. Two dimensions per item:
#
#   kind — what role the document plays in the policy process:
#     instrument   : an enacted/in-force policy artefact (act, rules,
#                    notification, scheme, budget, judgment, named policy)
#     process      : policy in the making (draft for consultation, bill,
#                    parliamentary question reply, committee report, debate)
#     announcement : official communication that is not itself an instrument
#                    (PIB "PM inaugurates…" releases, event coverage)
#     analysis     : research / think-tank / international-body output
#     news         : journalism coverage
#
#   type — the specific document genre (act, bill, draft, question, …).
#
# The kind is bounded by source authority: media can only produce `news`,
# research bodies only `analysis`. Only official sources (government,
# regulator, legal, parliament) can produce instruments and process items.
# ─────────────────────────────────────────────────────────────────────────

KIND_INSTRUMENT = "instrument"
KIND_PROCESS = "process"
KIND_ANNOUNCEMENT = "announcement"
KIND_ANALYSIS = "analysis"
KIND_NEWS = "news"

# Sources whose output is long-form policy writing (essays, journal issues)
# rather than briefs or working papers.
LONGFORM_SOURCE_IDS = frozenset({
    "epw", "india_forum", "ideas_for_india", "seminar_mag", "idronline",
})

_RE_QUESTION = None
_RE_BILL = None


def _tax_regexes():
    """Compile taxonomy regexes lazily (module import stays cheap)."""
    global _RE_QUESTION, _RE_BILL
    if _RE_QUESTION is None:
        import re as _re
        _RE_QUESTION = _re.compile(
            r"(starred question|unstarred question"
            r"|(?:written |a )reply to (?:a )?question"
            r"|in (?:a )?written reply (?:to|in) (?:the )?(?:lok|rajya) sabha"
            r"|question (?:no\.?|number)\s*\d"
            r"|(?:lok|rajya) sabha (?:starred|unstarred|question))"
        )
        _RE_BILL = _re.compile(r"\bbills?\b")
    return _RE_QUESTION, _RE_BILL


def categorize_item(title: str, description: str, source_id: str,
                    source_config: dict | None = None) -> tuple[str, str]:
    """Return (kind, type) for an item, bounded by its source's authority.

    This replaces the old keyword-only categorize_item_type(), whose default
    branch stamped everything without a keyword — including news features and
    university course adverts — as type "policy". Here the publisher decides
    the ceiling: journalism is `news`, research is `analysis`, and only
    official sources can produce instruments or process documents.
    """
    import re

    authority = get_source_authority(source_id, source_config)
    text = f"{title} {description}".lower()
    title_l = title.lower()

    # ── Media → news (with an opinion sub-genre) ──────────────────────────
    if authority == AUTHORITY_MEDIA:
        if re.search(r"\b(opinion|editorial|op-ed|comment(?:ary)?):|\bopinion\b.*\|", title_l):
            return KIND_NEWS, "opinion"
        return KIND_NEWS, "news"

    # ── Research / international → analysis ───────────────────────────────
    if authority in (AUTHORITY_THINK_TANK, AUTHORITY_INTERNATIONAL):
        if source_id in LONGFORM_SOURCE_IDS:
            return KIND_ANALYSIS, "longform"
        if re.search(r"\b(working paper|policy brief|discussion paper|report|"
                     r"survey|study|index|assessment|evaluation)\b", text):
            return KIND_ANALYSIS, "report"
        if re.search(r"\b(essay|long read|longread|perspective)\b", text):
            return KIND_ANALYSIS, "longform"
        return KIND_ANALYSIS, "analysis"

    # ── Official sources: government / regulator / legal / parliament ─────
    # Order matters: process artefacts (draft, bill, question) are checked
    # before instruments so "Draft Rules" lands as draft, not rules.

    # Parliamentary question replies (PIB ministry releases routinely carry
    # "…in a written reply to a question in Lok Sabha").
    re_question, re_bill = _tax_regexes()
    if re_question.search(text):
        return KIND_PROCESS, "question"

    # Drafts and consultations — policy open for public comment.
    if (re.search(r"\bdraft\b", title_l)
            and re.search(r"\b(rules?|policy|notification|regulations?|"
                          r"guidelines?|bill|amendment|code|norms|scheme|"
                          r"framework|standards?)\b", title_l)) \
            or re.search(r"(comments? (?:are )?invited|public comments|"
                         r"consultation paper|pre-legislative|"
                         r"stakeholder (?:comments|consultation)|"
                         r"(?:seeks?|seeking|inviting) (?:public )?comments|"
                         r"last date for (?:submission of )?comments)", text):
        return KIND_PROCESS, "draft"

    # Committee reports and debates.
    if re.search(r"\b(standing committee|parliamentary committee|"
                 r"select committee|joint committee)\b", text) \
            and re.search(r"\breport\b", text):
        return KIND_PROCESS, "committee_report"
    if re.search(r"\bconstituent assembly\b", text):
        return KIND_PROCESS, "debate"

    # Bills before Parliament. Treasury bills are money-market operations,
    # not legislation — they fall through to announcement.
    if re_bill.search(title_l) \
            and not re.search(r"\b(finance bill|treasury bills?|t-bills?|"
                              r"(?:91|182|364)[ -]day)\b", title_l):
        return KIND_PROCESS, "bill"

    # Subordinate legislation: rules / regulations.
    if re.search(r"\b(rules|regulations),?\s*(?:19|20)\d{2}\b", title_l) \
            or re.search(r"\bamendment (rules|regulations)\b", title_l):
        return KIND_INSTRUMENT, "rules"

    # Acts — enacted legislation. "The X (Amendment) Act, 2025", assent,
    # commencement; India Code items are acts by definition. Regulatory
    # directions "under Section N of the X Act" cite an act without being
    # one — the direction guard sends those to `notification` below.
    if source_id in ("india_code", "india_code_history"):
        return KIND_INSTRUMENT, "act"
    if not re.search(r"\b(directions?|circular|notification|order|"
                     r"exclusion|inclusion|under section)\b", title_l) \
            and (re.search(r"\bact,?\s*(?:19|20)\d{2}\b", title_l)
                 or re.search(r"\b(amendment act|receives? (?:the )?president'?s assent|"
                              r"comes? into force|promulgat\w+|ordinance)\b", text)):
        return KIND_INSTRUMENT, "act"

    # Notifications, gazette entries, circulars, directions, orders,
    # schedule inclusions/exclusions (RBI's bank-licensing housekeeping).
    if re.search(r"\b(notification|gazette|circular|office memorandum|"
                 r"master direction|directions?)\b", text) \
            or re.search(r"\border\b", title_l) \
            or re.search(r"\b(exclusion|inclusion) of\b.*\bschedule\b", text):
        return KIND_INSTRUMENT, "notification"

    # Court output from legal sources.
    if authority == AUTHORITY_LEGAL and re.search(
            r"\b(judgment|judgement|verdict|decree|writ petition)\b", text):
        return KIND_INSTRUMENT, "judgment"

    # Budget documents.
    if re.search(r"\b(union budget|budget \d{4}|interim budget|"
                 r"economic survey|finance bill|appropriation|"
                 r"demands? for grants|supplementary demands)\b", text):
        return KIND_INSTRUMENT, "budget"

    # Schemes and missions. "programme"/"program" is deliberately excluded —
    # it matched every workshop and training-camp announcement (TRAI consumer
    # education camps were the whole "scheme" tail of the old dataset).
    if re.search(r"\b(scheme|yojana|mission|abhiyan)\b", text):
        return KIND_INSTRUMENT, "scheme"

    # Explicit named policies ("National Education Policy", "Foreign Trade
    # Policy") — the word must appear in the TITLE from an official source.
    if re.search(r"\bpolicy\b", title_l):
        return KIND_INSTRUMENT, "policy"

    # Official reports / surveys → analysis (a NITI report is analysis, not
    # an instrument, even though the publisher is government).
    if re.search(r"\b(report|survey|study|index|white paper|green paper)\b",
                 title_l):
        return KIND_ANALYSIS, "report"

    # Everything else from an official source is an announcement — a press
    # release, an inauguration, a statement. Honest label; NOT "policy".
    return KIND_ANNOUNCEMENT, "release"


# Legacy type → (kind, type) mapping for curated data (historical seed) whose
# hand-assigned types should be preserved rather than re-derived from text.
LEGACY_TYPE_MAP = {
    "legislation": (KIND_INSTRUMENT, "act"),
    "notification": (KIND_INSTRUMENT, "notification"),
    "scheme": (KIND_INSTRUMENT, "scheme"),
    "budget": (KIND_INSTRUMENT, "budget"),
    "policy": (KIND_INSTRUMENT, "policy"),
    "research": (KIND_ANALYSIS, "report"),
    "announcement": (KIND_ANNOUNCEMENT, "release"),
}

# India-relevance markers. Used to filter items from generalist media RSS
# feeds (Livemint Politics, Hindustan Times, The Hindu National, NDTV India,
# etc.) which routinely include foreign news (NYC mayoral politics, US trade
# moves, UK PMQs) alongside Indian policy. An item is considered
# India-relevant if its title or description contains at least one of these
# high-precision markers.
#
# Kept conservative: the list is bounded to terms that have low collision
# risk with foreign-news content. "Parliament" alone is excluded because
# UK/EU stories use it; "PM" alone is excluded because every country has a
# PM; "Modi" / specific Indian political figures are also excluded since
# they could be referenced in international comparison pieces. State names,
# ministry acronyms, and India-specific institutions are the load-bearing
# signals.

_INDIA_MARKERS_SUBSTR = (
    # Generic identifiers (lowercased substring match)
    "india",  # also catches "indian", "indians", "indianapolis" — see exclusion below
    "bharat",
    # Modi gets a short-form marker because the Indian press routinely
    # refers to the PM as just "Modi" without the first name. Risk of
    # collision with non-Indian "Modi"s (e.g. fashion designer Modi) is
    # negligible in policy/politics RSS.
    "modi",
    # Government idioms used by Indian press
    "modi government", "modi govt",
    "lok sabha", "rajya sabha",
    "centre's", "centre will", "centre has",
    "supreme court of india", "high court of",
    "election commission of india",
    "niti aayog", "planning commission", "finance commission",
    "rajya", "panchayat", "panchayati raj", "gram sabha",
    "tehsil", "zila parishad", "block development",
    "kendriya vidyalaya", "navodaya",
    "ministry of", "department of",
    "gazette of india",
    "press information bureau",
    "reserve bank of india",
    "securities and exchange board of india",
    # State abbreviations as the press uses them
    "u.p.", "m.p.", "a.p.", "t.n.", "w.b.", "j&k", "h.p.", "t.s.",
    "uttar pradesh cm", "madhya pradesh cm",
    # Political party names — high-precision Indian markers
    "indian national congress",
    "bharatiya janata", "aam aadmi party", "shiv sena",
    "all india", "samajwadi party", "biju janata dal",
    "trinamool congress", "telugu desam party",
    "rashtriya janata dal", "akali dal",
    "rashtriya swayamsevak sangh",
    "chief minister",  # Indian-specific political title (other countries use Premier/Governor)
    # Indian-specific schemes / acronyms expanded
    "ayushman bharat", "pradhan mantri",
    "make in india", "atmanirbhar bharat", "digital india",
    "swachh bharat", "skill india", "startup india",
    "smart city mission", "jan dhan",
    # Civil services / boards
    "indian administrative service", "indian police service",
    "indian foreign service", "indian revenue service",
)

_INDIA_MARKERS_TOKEN = (
    # Acronyms / single tokens — matched as whole words.
    # Government / regulators
    "rbi", "sebi", "niti", "gst", "upi", "pmjay", "mgnrega", "nrega",
    "ayushman", "aadhaar", "dpdp", "agnipath", "agniveer", "isro", "drdo",
    "csir", "icmr", "ugc", "aicte", "ncert", "iit", "iim", "iiit", "aiims",
    "nift", "trai", "irda", "irdai", "cbi", "fssai", "cag", "cvc", "lokpal",
    "cbic", "cbdt", "amfi", "nclt", "nbfc", "nhai", "drdo",
    # Political parties (acronyms used as standalone tokens)
    "bjp", "aap", "aiadmk", "dmk", "tmc", "tvk", "tdp", "ysrcp", "bjd",
    "jdu", "jd(u)", "jds", "jd(s)", "rjd", "sp", "bsp", "ncp", "jmm",
    # Roles
    "mla", "mlc",
    # Education boards
    "cbse", "icse", "cisce",
    # Currency / units
    "rupee", "rupees", "lakh", "crore", "lakhs", "crores",
    # Patriotic terms
    "tricolour", "tiranga",
)

# Indian state and union territory names. Normalized to lowercase, ampersands
# and "and" both covered.
_INDIAN_STATES = (
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan",
    "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh",
    "uttarakhand", "uttaranchal", "west bengal",
    # Union territories
    "andaman", "chandigarh", "dadra", "nagar haveli", "daman", "diu",
    "delhi", "jammu and kashmir", "jammu & kashmir", "ladakh",
    "lakshadweep", "puducherry", "pondicherry",
)

# Major Indian cities — generally distinct from foreign city names, but some
# (like "Hyderabad", which also exists in Pakistan) are kept because the
# Indian-press context dominates.
_INDIAN_CITIES = (
    "mumbai", "bombay", "kolkata", "calcutta", "chennai", "madras",
    "bengaluru", "bangalore", "hyderabad", "ahmedabad", "pune", "jaipur",
    "lucknow", "kanpur", "nagpur", "indore", "bhopal", "patna",
    "vadodara", "ghaziabad", "agra", "varanasi", "amritsar",
    "thiruvananthapuram", "trivandrum", "kochi", "ernakulam",
    "coimbatore", "madurai", "tiruchirappalli", "trichy",
    "guwahati", "shillong", "imphal", "kohima",
    "shimla", "dehradun", "ranchi", "raipur", "bhubaneswar", "cuttack",
    "gandhinagar", "surat", "rajkot", "nashik", "aurangabad",
    "vijayawada", "guntur", "visakhapatnam", "vizag",
    "warangal", "tirupati",
    "noida", "gurgaon", "gurugram", "faridabad", "meerut",
    "jodhpur", "udaipur", "kota",
    "panaji", "panjim",
    "siliguri", "darjeeling",
)

# Indian rivers and geographic features that appear in policy reporting.
_INDIAN_GEO = (
    "ganga", "ganges", "yamuna", "godavari", "krishna river",
    "narmada", "kaveri", "cauvery", "brahmaputra",
    "western ghats", "eastern ghats", "deccan", "vindhya",
    "himalaya", "himalayas", "himalayan",
)

# Frequently-named Indian political figures. Last names only would collide
# with foreign names (Gandhi, Patel exist worldwide), so use full names.
_INDIAN_POLITICIANS = (
    "narendra modi", "rahul gandhi", "amit shah", "yogi adityanath",
    "mamata banerjee", "arvind kejriwal", "m k stalin", "mk stalin",
    "sharad pawar", "ajit pawar", "mulayam singh", "akhilesh yadav",
    "mayawati", "shivraj singh chouhan", "nitish kumar",
    "k chandrashekar rao", "kcr",
    "chandrababu naidu", "jagan mohan reddy", "ys jagan",
    "uddhav thackeray", "eknath shinde",
    "pinarayi vijayan", "siddaramaiah", "basavaraj bommai",
    "rajnath singh", "nirmala sitharaman", "piyush goyal",
    "ashwini vaishnaw", "smriti irani",
    "draupadi murmu", "venkaiah naidu", "ram nath kovind",
)

# Names that look India-ish but should NOT count as India markers when they
# appear in a foreign-news context. "Indianapolis" matches "india" as a
# substring — strip those. Likewise "Indiana" the US state, and the West
# Indies cricket team etc.
_FALSE_POSITIVES = (
    "indianapolis", "indiana,",  # comma forces us-state context, leaves "Indian" alone
    "indiana state", "indiana university", "indiana usa",
    "west indies", "british indian ocean territory",
    "east indies",
)


def _normalize_for_relevance(text: str) -> str:
    """Lowercase + strip the known false-positive contexts so the substring
    `india` check doesn't fire on `Indianapolis`. Returns the cleaned text."""
    t = text.lower()
    for fp in _FALSE_POSITIVES:
        t = t.replace(fp, "")
    return t


def _has_token(text: str, token: str) -> bool:
    """Whole-word match of `token` inside `text` (both already lowercased)."""
    import re
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


# Foreign-news markers. Items from generalist media feeds (Livemint, NDTV,
# Hindustan Times, etc.) that hit one of these AND don't hit any India
# marker are non-India news (NYC mayoral politics, US Fed moves, UK PMQs)
# and get dropped. The list is intentionally narrow: only proper nouns that
# are unambiguously not-Indian (foreign city names, foreign institutions,
# foreign-only political figures) and rarely appear in genuine
# India-context coverage. Common nouns like "trade" or "election" stay out
# of this list because they collide with Indian content.
_FOREIGN_MARKERS_SUBSTR = (
    # US cities — phrase forms only, so a bare "Washington" mention in
    # India-US-relations coverage doesn't auto-drop the item
    "new york city", "new york mayor", "new yorkers", "new york state",
    "los angeles", "san francisco", "san jose",
    "chicago mayor", "boston police", "washington dc", "washington d.c.",
    "houston police", "miami beach", "atlanta police", "philadelphia mayor",
    # US institutions
    "white house", "u.s. senate", "u.s. congress",
    "u.s. supreme court", "supreme court of the united states", "scotus",
    "federal reserve", "u.s. department of",
    "u.s. border wall", "border wall",
    # UK
    "10 downing", "downing street", "westminster", "uk parliament",
    "house of commons", "house of lords",
    "rishi sunak", "keir starmer", "boris johnson",
    "british prime minister",
    # EU / continental Europe
    "european union", "eu commission", "european parliament",
    "european central bank", "european hands",
    "german chancellor",
    # Foreign leaders (only those unlikely to appear in India-context)
    "joe biden", "kamala harris", "barack obama",
    "vladimir putin", "emmanuel macron", "olaf scholz",
    "kim jong", "xi jinping",
    # Foreign cities — only the ones unlikely to feature in Indian state news
    "tel aviv", "jerusalem",
    "kuala lumpur", "bangkok", "manila", "jakarta",
    "buenos aires", "rio de janeiro", "sao paulo",
    # Foreign-only conflict phrases (Indian press also covers these, but if
    # there's zero India signal, they belong elsewhere)
    "trump-xi", "russian invasion of",
    "chinese school", "chinese teens",
    "putin says", "putin's", "kyiv",
    "ukraine ceasefire", "ukraine war", "ukrainian forces",
    # Wall Street etc.
    "wall street", "silicon valley",
    # US states that look India-ish (handled as foreign markers because
    # they appear in genuinely-foreign coverage and we want to drop those).
    "indianapolis", "indiana, usa", "indiana state",
)


# Policy-relevance markers. Applied to items from generalist news RSS feeds
# (Hindu, NDTV, HT, IE, Livemint, etc.) — the outlets publish everything
# from cricket to celebrity divorce in the same RSS as real policy coverage,
# and the current filter (length + junk regex) lets it all through. An item
# is "policy-relevant" if it hits at least one of these markers; otherwise
# it's dropped as noise before ingestion.
#
# The list intentionally casts a wide net around policy signalling
# vocabulary — institutional actors, policy artefacts, governance topics.
# False positives (letting some borderline items through) are preferable
# to false negatives (dropping real policy coverage), since the dataset
# is meant to be comprehensive on Indian policy. Common English words
# ("policy", "government") are included because they're extremely
# predictive of policy coverage in news headlines.
_POLICY_MARKERS = (
    # Legislative actors and artefacts
    "bill", "act,", " act ", " act.", "ordinance", "law", "legislation",
    "gazette", "notification", "circular", "rules", "regulation",
    "amendment", "policy", "scheme", "guidelines", "directive",
    "constitutional", "constitution",
    # Executive
    "cabinet", "ministry", "minister", "government", "administration",
    "secretariat", "president", "vice president", "governor", "chief minister",
    "prime minister", "cm ", "pm ", "govt", "centre notif", "centre issu",
    "centre form", "centre asks", "centre approv", "centre orders",
    "centre decid", "central government", "state government",
    # Approvals & inquiries
    "nod ", "panel ", "clearance", "public hearing", "consultation paper",
    # Divestment & PSU
    "divest", "psu ", "ofs ", "stake sale", "disinvestment",
    # Legislative bodies
    "parliament", "lok sabha", "rajya sabha", "vidhan sabha", "assembly",
    "legislative", "parliamentary", "session",
    # Judiciary — institutions only. Bare litigation-process words ("case",
    # "plea", "petition", "verdict", "ruling", "order", "bench", "stay") were
    # removed: they match crime-blotter and routine civil-suit coverage far
    # more often than policy, and were a major source of the news flood.
    "supreme court", "high court", "constitution bench",
    "constitutional bench", "tribunal",
    # Regulators, commissions, and public bodies
    "rbi", "sebi", "trai", "irdai", "cci", "ncw", "nclt", "nclat", "nhrc",
    "cvc", "cag", "cbi", "ed", "election commission", "eci", "upsc",
    "commission ", "regulator", "authority", "bureau", "council ",
    # Institutional roles (usually appear in appointment / decision headlines)
    "chief", "director", "secretary", "commissioner",
    "dg ", "cbdt", "ncrb",
    # Government departments & agencies (space, defence, tech, energy)
    "isro", "drdo", "hal ", "ntpc", "bhel", "coal india", "psb ",
    "barc",
    # Bilateral / international agreements
    "pact", "treaty", "mou ", "bilateral", "trade deal", "defence deal",
    "arms deal", "arms sale", "signed with", "agreement with",
    # Budget/finance
    "budget", "allocation", "subsidy", "grant", "fund", "expenditure",
    "revenue", "deficit", "tax", "gst", "excise", "customs", "tariff",
    "duty", "cess",
    # Governance topics
    "welfare", "reservation", "quota", "affirmative", "mnrega", "mgnrega",
    "pmay", "nrega", "ujjwala", "ayushman", "digital india", "make in india",
    "modi", "manmohan", "vajpayee",
    # Rights & citizens
    "rti", "aadhaar", "citizenship", "human rights", "labour law", "labor law",
    "consumer protection", "posh", "domestic violence",
    # Policy verbs (they usually indicate action-taking)
    "notified", "issued", "announced", "launched", "approved", "cleared",
    "gazetted", "promulgated", "empanelled", "empanelled",
    "sanctioned", "abolished", "repealed", "amended", "notified",
    # Sectors framed as policy
    "public health", "public policy", "public sector", "public interest",
    "environmental clearance", "forest clearance", "environmental impact",
    "climate policy", "energy policy", "trade policy", "foreign policy",
    "tax policy", "monetary policy", "fiscal policy",
    # Elections & political process
    "election", "electoral", "voter", "polling", "constituency",
    "mcc", "poll code", "vvpat", "evm",
    # Reports / documents that shape policy. Bare "report" / "review" /
    # "study" / "survey" were removed (they match routine news of every
    # kind); the specific policy artefacts are kept.
    "audit", "committee", "consultation", "consultation paper",
    "white paper", "green paper", "draft", "economic survey",
    # NOTE: standalone crime-action verbs ("raid", "arrest", "chargesheet",
    # "fir", "probe", "inquiry", "investigation") were deliberately removed.
    # They were the single biggest source of crime-blotter noise — a bare
    # "Man arrested" / "police probe" headline is not policy. Genuine
    # enforcement-of-policy stories still pass via institutional markers
    # (cbi, ed, cvc, cag, election commission, etc.) that remain above.
)


# Spectacle / tabloid-noise markers. Generalist news RSS carries a firehose
# of violent-crime blotter, road accidents, celebrity, and sports coverage
# that has nothing to do with policy but occasionally brushes a policy
# keyword ("minister's son held", "actor's PIL"). If any of these appears,
# the item is dropped outright — this hard-drop runs BEFORE the policy-marker
# check in is_policy_relevant(). Kept deliberately high-precision so it never
# swallows real policy (e.g. "crime" is excluded because "National Crime
# Records Bureau" is a live institution; "suicide" is only matched as
# "commits/dies by suicide" so suicide-prevention policy survives).
_SPECTACLE_SUBSTR = (
    # Violent crime blotter
    "murder", "stabbed", "stabbing", "strangl", "hacked to death",
    "beaten to death", "burnt alive", "burnt to death", "lynch", "molest",
    "sexually abus", "sexual assault", "gang-rape", "gangrape", "dowry death",
    "honour killing", "honor killing", "acid attack", "kidnap", "abduct",
    "beheaded", "dismember", "dead body", "body found", "found dead",
    "commits suicide", "dies by suicide", "died by suicide", "suicide bid",
    "self-immolat", "elopes", "eloped",
    # Accidents (personal, not disaster policy)
    "road crash", "car crash", "hit-and-run", "hit and run", "electrocuted",
    # Celebrity / entertainment
    "bollywood", "tollywood", "kollywood", "box office", "actress",
    "co-star", "web series", "web-series", "goes viral", "viral video",
    "caught on camera", "wheelie", "bike stunt",
    # Sports
    "cricket", "world cup", "batsman", "bowler", "wicket", "football",
    "fifa", "wimbledon", "grand slam", "hockey", "kabaddi",
    # Astrology / lifestyle
    "horoscope", "astrology", "rashifal", "zodiac",
)

# Short / substring-ambiguous spectacle markers matched on word boundaries,
# so "killed" doesn't fire on "skilled", "axe" on "relaxed"/"taxes", "stunt"
# on "stunted growth", "ipl" on "multiple", "odi" on "custodial".
_SPECTACLE_TOKEN = (
    "killed", "kills", "kill", "rape", "raped", "axe", "stunt",
    "ipl", "odi", "t20",
)


def _is_spectacle(text: str) -> bool:
    """True if the (lowercased) text reads as tabloid/crime/sport/celebrity
    noise rather than policy. See _SPECTACLE_SUBSTR / _SPECTACLE_TOKEN."""
    for m in _SPECTACLE_SUBSTR:
        if m in text:
            return True
    for tok in _SPECTACLE_TOKEN:
        if _has_token(text, tok):
            return True
    return False


def is_policy_relevant(title: str, description: str = "") -> bool:
    """Return True if a news-source item looks policy-relevant.

    Applied ONLY to items from generalist news RSS feeds (see NEWS_SOURCE_IDS
    in scripts/fetch_all.py). Official-government sources bypass this check.

    An item passes if any of the curated markers in _POLICY_MARKERS appears
    in the combined title+description. Short markers (<= 3 chars ignoring
    the trailing space, like "ED", "CM", "PM", "PSU", "OFS") are matched
    on whole-word boundaries — otherwise "ED " matches every past-tense
    verb ending "recorded", "circulated", etc. (real regression, 300+
    noise items slipped through).

    Two-stage gate:
      1. Spectacle hard-drop — if the item reads as crime blotter, road
         accident, celebrity, sports, or astrology noise (_is_spectacle),
         it's dropped regardless of any policy keyword it happens to brush.
      2. Policy-marker requirement — the item is kept only if it hits at
         least one curated marker in _POLICY_MARKERS; otherwise dropped.

    This is stricter than the original lenient design: the tracker is a
    policy archive, not a news reader, so an item with no policy signal is
    dropped rather than kept. The marker list was pruned of the generic /
    crime-action keywords that were letting the news firehose through.
    """
    import re

    text = f"{title} {description}".lower()

    # Stage 1: spectacle / tabloid noise — drop outright.
    if _is_spectacle(text):
        return False

    # Stage 2: require at least one policy marker.
    for marker in _POLICY_MARKERS:
        stripped = marker.strip()
        # Short markers get word-boundary matching so "ed " doesn't
        # match "record[ed] " and "cm " doesn't match "10cm".
        if len(stripped) <= 3:
            if re.search(rf"\b{re.escape(stripped)}\b", text):
                return True
        elif marker in text:
            return True
    return False


def is_broadcast_relevant(title: str, description: str = "", level: str = "") -> bool:
    """Defense-in-depth gate for OUTWARD broadcasts (Telegram, newsletter).

    The fetch pipeline already filters mixed-media feeds at ingestion, so
    data/policies.json should be clean. But broadcasting is high-visibility
    and irreversible, so consumers re-check every item before pushing it:

      - Spectacle / tabloid noise is dropped regardless of source. Even an
        official-government feed occasionally carries a lurid title, and we
        never want that going out to subscribers.
      - Media-sourced items (level == "media") must additionally hit a policy
        marker, mirroring fetch_source's gate. Official-government items are
        trusted (they can be genuine policy without a keyword — a gazette
        notification titled with just a number, etc.).

    Returns True if the item is safe to broadcast.
    """
    text = f"{title} {description}".lower()
    if _is_spectacle(text):
        return False
    if level == "media" and not is_policy_relevant(title, description):
        return False
    return True


def is_india_relevant(title: str, description: str = "") -> bool:
    """Return True if the item should be kept in the India-policy dataset.

    Used to gate items ingested from generalist Indian-media feeds (Livemint,
    NDTV India, Hindustan Times, etc.) which carry foreign news in the same
    RSS as Indian policy. Items from official-government sources should NOT
    be passed through this check — they're trusted by their source.

    Logic:
      1. If the text contains any India marker → keep.
      2. Else if the text contains a foreign marker → drop.
      3. Else (neutral, no signal either way) → keep.

    The default-keep on neutral text is deliberate: false negatives (dropping
    real Indian content) are worse than false positives (keeping a few
    foreign articles) for a tracker meant to be comprehensive on Indian
    policy. The foreign-marker list catches the clear-cut cases the
    dataset has shown so far (NYC mayoral politics, US Fed moves, UK PMQs).
    """
    raw = f"{title} {description}".lower()
    # India check runs on text with confusable substrings stripped
    # ("indianapolis" no longer looks like "india"). Foreign check runs on
    # the unmodified lowercased text so the stripped tokens are still
    # available as foreign signals.
    normalized = _normalize_for_relevance(raw)

    # Step 1: positive India signal — keep immediately.
    if _has_india_marker(normalized):
        return True

    # Step 2: foreign signal without an India signal — drop.
    for marker in _FOREIGN_MARKERS_SUBSTR:
        if marker in raw:
            return False

    # Step 3: neutral → keep.
    return True


def _has_india_marker(combined: str) -> bool:
    """Internal: does this lowercased text contain any India marker?"""
    for marker in _INDIA_MARKERS_SUBSTR:
        if marker in combined:
            return True
    for state in _INDIAN_STATES:
        if state in combined:
            return True
    for city in _INDIAN_CITIES:
        if city in combined:
            return True
    for geo in _INDIAN_GEO:
        if geo in combined:
            return True
    for politician in _INDIAN_POLITICIANS:
        if politician in combined:
            return True
    for tok in _INDIA_MARKERS_TOKEN:
        if _has_token(combined, tok):
            return True
    return False

SECTOR_KEYWORDS = {
    "Education": [
        "education", "school", "university", "college", "teacher", "student",
        "literacy", "curriculum", "NEP", "national education policy", "UGC",
        "AICTE", "IIT", "IIM", "NCERT", "midday meal", "scholarship",
        "skill development", "vocational training", "higher education",
        "primary education", "Samagra Shiksha", "learning", "edtech",
        "Atal Tinkering", "NASSCOM", "digital literacy", "anganwadi education"
    ],
    "Health": [
        "health", "hospital", "medical", "disease", "vaccine", "AIIMS",
        "ayushman bharat", "healthcare", "pharma", "drug", "ICMR", "WHO",
        "epidemic", "pandemic", "nutrition", "mental health", "FSSAI",
        "public health", "maternal", "child health", "tuberculosis", "malaria",
        "polio", "immunization", "PMJAY", "Jan Arogya", "NRHM", "wellness",
        "AYUSH", "ayurveda", "telemedicine", "eSanjeevani", "NHA"
    ],
    "Agriculture": [
        "agriculture", "farmer", "crop", "irrigation", "MSP",
        "minimum support price", "APMC", "mandi", "fertilizer", "pesticide",
        "PM-KISAN", "kisan", "horticulture", "fisheries", "dairy",
        "animal husbandry", "food grain", "agri", "seed", "soil",
        "organic farming", "eNAM", "cold storage", "food processing",
        "NABARD", "crop insurance", "PMFBY", "agricultural market"
    ],
    "Climate & Environment": [
        "climate", "environment", "pollution", "carbon", "emission",
        "forest", "wildlife", "biodiversity", "green", "renewable",
        "EIA", "environmental impact", "COP", "Paris Agreement",
        "sustainable development", "waste management", "recycling",
        "air quality", "water pollution", "plastic ban", "conservation",
        "wetland", "mangrove", "desertification", "ozone", "clean air",
        "NAPCC", "solar mission", "climate change", "net zero", "ESG"
    ],
    "Digital & Technology": [
        "digital", "technology", "IT", "software", "cyber", "internet",
        "broadband", "5G", "AI", "artificial intelligence", "blockchain",
        "startup", "data protection", "privacy", "MeitY", "DPDP",
        "Digital India", "UPI", "fintech", "e-governance", "Aadhaar",
        "DigiLocker", "UMANG", "ONDC", "semiconductor", "chip",
        "cloud computing", "data centre", "information technology",
        "IndiaAI", "digital public infrastructure", "DPI", "CERT-In"
    ],
    "Finance & Economy": [
        "finance", "economy", "budget", "tax", "GST", "fiscal",
        "monetary policy", "RBI", "SEBI", "stock", "investment",
        "FDI", "banking", "insurance", "pension", "inflation",
        "GDP", "economic growth", "disinvestment", "privatization",
        "NBFC", "mutual fund", "bond", "treasury", "revenue",
        "expenditure", "fiscal deficit", "PLI", "production linked",
        "Make in India", "Atmanirbhar", "credit", "NPA", "microfinance"
    ],
    "Social Protection": [
        "social protection", "welfare", "subsidy", "BPL", "poverty",
        "ration", "PDS", "public distribution", "food security",
        "MGNREGA", "NREGA", "employment guarantee", "pension scheme",
        "Ujjwala", "PM Garib Kalyan", "Jan Dhan", "DBT",
        "direct benefit transfer", "social security", "Antyodaya",
        "SC", "ST", "OBC", "scheduled caste", "scheduled tribe",
        "backward class", "reservation", "affirmative action",
        "Below Poverty Line", "safety net", "cash transfer"
    ],
    "Gender & Women": [
        "gender", "women", "girl", "female", "maternal", "Beti Bachao",
        "Beti Padhao", "She-Box", "dowry", "domestic violence",
        "sexual harassment", "POSH", "women empowerment", "SHG",
        "self help group", "Mahila", "Nari Shakti", "Sukanya Samriddhi",
        "maternity benefit", "one stop centre", "gender equality",
        "female labour", "CEDAW", "gender budget", "women reservation",
        "menstrual hygiene", "Ujjwala women", "gender mainstreaming"
    ],
    "Urban Development": [
        "urban", "city", "municipal", "smart city", "metro", "AMRUT",
        "PMAY urban", "housing urban", "town planning", "slum",
        "urbanization", "urban transport", "sewage", "municipal waste",
        "building code", "real estate", "RERA", "Swachh Bharat urban",
        "urban local body", "urban governance", "urban flood", "JNNURM",
        "SBM urban", "parking", "pedestrian", "urban renewal"
    ],
    "Rural Development": [
        "rural", "village", "panchayat", "gram", "Pradhan Mantri Gram",
        "PMGSY", "rural road", "PMAY rural", "housing rural",
        "Swachh Bharat gramin", "SBM gramin", "Sansad Adarsh Gram",
        "rural electrification", "Saubhagya", "Deendayal Upadhyaya",
        "DDUGJY", "rural livelihood", "NRLM", "rural employment",
        "tribal area", "block development", "district rural development"
    ],
    "Water & Sanitation": [
        "water", "sanitation", "toilet", "ODF", "open defecation",
        "Jal Jeevan", "drinking water", "water supply", "sewage",
        "Namami Gange", "Ganga", "river cleaning", "watershed",
        "Swachh Bharat", "SBM", "water conservation", "rainwater",
        "groundwater", "dam", "water resource", "irrigation",
        "water quality", "fluoride", "arsenic water", "WASH",
        "water treatment", "desalination", "piped water"
    ],
    "Energy": [
        "energy", "power", "electricity", "solar", "wind", "nuclear",
        "coal", "petroleum", "natural gas", "DISCOMS", "tariff",
        "energy efficiency", "BEE", "LED", "UJALA", "Saubhagya",
        "renewable energy", "green hydrogen", "battery storage",
        "electric vehicle", "EV", "charging infrastructure",
        "energy transition", "thermal power", "hydropower", "biomass",
        "KUSUM", "PM Surya Ghar", "rooftop solar", "grid"
    ],
    "Governance & Reform": [
        "governance", "reform", "transparency", "accountability",
        "RTI", "right to information", "e-governance", "judicial",
        "Supreme Court", "High Court", "administrative reform",
        "civil service", "UPSC", "IAS", "police reform", "federalism",
        "cooperative federalism", "delimitation", "election commission",
        "one nation one election", "lateral entry", "mission karmayogi",
        "anti-corruption", "Lokpal", "ombudsman", "decentralization"
    ],
    "Labour & Employment": [
        "labour", "labor", "employment", "wage", "minimum wage",
        "trade union", "industrial relations", "factory", "EPFO",
        "ESI", "provident fund", "gratuity", "labour code",
        "gig worker", "platform worker", "contract labour",
        "occupational safety", "child labour", "unemployment",
        "job creation", "skilling", "apprenticeship", "NSDC",
        "labour reform", "code on wages", "social security code",
        "industrial dispute", "layoff", "retrenchment"
    ],
    "Housing": [
        "housing", "PMAY", "Pradhan Mantri Awas", "affordable housing",
        "RERA", "real estate", "slum rehabilitation", "homeless",
        "shelter", "urban housing", "rural housing", "construction",
        "building material", "housing finance", "mortgage", "rent",
        "Model Tenancy Act", "housing for all", "EWS housing"
    ],
    "Transport & Infrastructure": [
        "transport", "highway", "railway", "airport", "port",
        "road", "bridge", "logistics", "Bharatmala", "Sagarmala",
        "NHAI", "Indian Railways", "metro rail", "Vande Bharat",
        "aviation", "shipping", "inland waterway", "freight corridor",
        "NIP", "national infrastructure pipeline", "Gati Shakti",
        "PM Gati Shakti", "expressway", "tunnel", "Atal Tunnel"
    ],
    "Defence & Security": [
        "defence", "defense", "military", "army", "navy", "air force",
        "border", "national security", "DRDO", "HAL", "ordnance",
        "Agnipath", "Agniveer", "strategic", "missile", "space",
        "ISRO", "counter terrorism", "internal security", "BSF", "CRPF",
        "coastal security", "Make in India defence", "defence procurement"
    ],
    "Trade & Commerce": [
        "trade", "commerce", "export", "import", "tariff", "customs",
        "WTO", "FTA", "free trade", "foreign trade policy", "DGFT",
        "special economic zone", "SEZ", "MSME", "small enterprise",
        "startup", "ease of doing business", "industrial policy",
        "competition commission", "CCI", "consumer protection",
        "e-commerce", "retail", "GeM", "government e-marketplace"
    ],
    "Science & Innovation": [
        "science", "innovation", "research", "CSIR", "DST", "ISRO",
        "space", "biotechnology", "DBT", "nanotechnology", "genomics",
        "patent", "intellectual property", "R&D", "Atal Innovation",
        "incubator", "accelerator", "deep tech", "quantum computing",
        "national research foundation", "Anusandhan", "scientific",
        "ICAR", "laboratory", "nuclear", "atomic energy"
    ],
    "Tribal & Indigenous": [
        "tribal", "adivasi", "indigenous", "scheduled tribe",
        "forest rights", "FRA", "PESA", "Van Dhan", "tribal area",
        "fifth schedule", "sixth schedule", "tribal welfare",
        "tribal sub plan", "Eklavya school", "minor forest produce",
        "tribal health", "tribal education", "TRIFED", "tribal affairs"
    ],
    "Disability & Inclusion": [
        "disability", "disabled", "PwD", "divyang", "accessibility",
        "inclusive", "RPwD Act", "barrier free", "assistive technology",
        "sign language", "braille", "mental disability", "autism",
        "cerebral palsy", "visual impairment", "hearing impairment",
        "wheelchair", "UDID", "disability certificate", "DEPwD",
        "Sugamya Bharat", "accessible India"
    ],
    "Child Rights & Youth": [
        "child", "children", "juvenile", "POCSO", "child labour",
        "child marriage", "adoption", "child welfare", "ICPS",
        "child protection", "youth", "Nehru Yuva Kendra", "NYKS",
        "adolescent", "Rashtriya Kishor Swasthya", "youth affairs",
        "National Youth Policy", "Khelo India", "sports", "young",
        "student", "higher education youth", "skill youth"
    ]
}


# Aliases for sector names that appear in feeds.json `covers_sectors` hints
# or legacy data but are not canonical SECTOR_KEYWORDS keys. Without this,
# fallback classification leaks raw hint strings ("economy, governance")
# into the dataset, producing junk sector chips and near-empty sector pages.
_SECTOR_ALIASES = {
    "economy": "Finance & Economy",
    "finance": "Finance & Economy",
    "governance": "Governance & Reform",
    "reform": "Governance & Reform",
    "legal": "Governance & Reform",
    "democracy": "Governance & Reform",
    "social-justice": "Social Protection",
    "social justice": "Social Protection",
    "social protection": "Social Protection",
    "digital-technology": "Digital & Technology",
    "digital": "Digital & Technology",
    "technology": "Digital & Technology",
    "climate": "Climate & Environment",
    "environment": "Climate & Environment",
    "health": "Health",
    "education": "Education",
    "agriculture": "Agriculture",
    "gender": "Gender & Women",
    "women": "Gender & Women",
    "labour": "Labour & Employment",
    "employment": "Labour & Employment",
    "energy": "Energy",
    "water": "Water & Sanitation",
    "urban": "Urban Development",
    "rural": "Rural Development",
    "housing": "Housing",
    "trade": "Trade & Commerce",
    "commerce": "Trade & Commerce",
    "defence": "Defence & Security",
    "defense": "Defence & Security",
    "security": "Defence & Security",
    "science": "Science & Innovation",
    "innovation": "Science & Innovation",
    "tribal": "Tribal & Indigenous",
    "disability": "Disability & Inclusion",
    "child": "Child Rights & Youth",
    "children": "Child Rights & Youth",
    "youth": "Child Rights & Youth",
    "transport": "Transport & Infrastructure",
    "infrastructure": "Transport & Infrastructure",
    "nutrition": "Health",
    "foreign policy": "Trade & Commerce",
}


def normalize_sector_names(raw_sectors) -> list[str]:
    """Map free-form sector hints to canonical sector names.

    Accepts a list or a comma-separated string. Unknown values are dropped
    rather than passed through, so junk like "economy, governance" can never
    become a sector chip. Returns a de-duplicated, order-preserving list.
    """
    if not raw_sectors:
        return []
    if isinstance(raw_sectors, str):
        raw_list = [s.strip() for s in raw_sectors.split(",")]
    else:
        raw_list = []
        for entry in raw_sectors:
            raw_list.extend(s.strip() for s in str(entry).split(","))

    canonical_keys = {k.lower(): k for k in SECTOR_KEYWORDS}
    result: list[str] = []
    for raw in raw_list:
        if not raw:
            continue
        key = raw.lower()
        name = canonical_keys.get(key) or _SECTOR_ALIASES.get(key)
        if name and name not in result:
            result.append(name)
    return result


def classify_policy(title: str, description: str = "", source_sectors=None) -> list[str]:
    """
    Classify a policy item into one or more sectors based on keyword matching.
    Returns a list of matched sector names, sorted by relevance (match count).
    """
    text = f"{title} {description}".lower()
    scores: dict[str, int] = {}

    for sector, keywords in SECTOR_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[sector] = score

    if not scores:
        # If source has known sectors, use those as fallback — normalized so
        # raw hint strings never leak into the dataset as sector names.
        if source_sectors and source_sectors != "all":
            normalized = normalize_sector_names(source_sectors)
            if normalized:
                return normalized[:3]
        return ["Governance & Reform"]  # default fallback

    # Return top sectors (up to 3), sorted by match count
    sorted_sectors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [s[0] for s in sorted_sectors[:3]]


def get_sector_slug(sector: str) -> str:
    """Convert sector name to URL-friendly slug."""
    return sector.lower().replace(" & ", "-").replace(" ", "-")


def get_all_sectors() -> list[str]:
    """Return all sector names."""
    return list(SECTOR_KEYWORDS.keys())
