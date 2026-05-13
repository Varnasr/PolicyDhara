"""
Keyword-based sector classifier for Indian policy items.
Maps policy text (title + description) to one or more development sectors.
No ML dependencies — runs fast in GitHub Actions.
"""

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
        # If source has known sectors, use those as fallback
        if source_sectors and source_sectors != "all":
            if isinstance(source_sectors, list):
                return source_sectors[:3]
            return [source_sectors]
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
