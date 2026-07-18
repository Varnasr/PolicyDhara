"""
India- and policy-relevance filters for generalist-media items.

⚠️  CANONICAL SOURCE: scripts/classifier.py — this module is a verbatim port
of that file's relevance logic so the published `policydhara` package filters
news the same way the live pipeline does. If you change one, change both
(tests/test_policydhara.py and tests/test_pipeline.py lock the shared cases).

Provides: is_policy_relevant, is_india_relevant, is_broadcast_relevant.
"""

from __future__ import annotations

import re

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
