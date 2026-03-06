"""
Domain classifier — tags each RawItem with one or more domain IDs
based on source registry defaults and keyword matching.
"""

import logging

log = logging.getLogger(__name__)

# Domain keyword rules — each domain has a set of keywords.
# Items matching keywords are tagged to that domain even if not in registry.
#
# Guidelines for adding keywords:
#   - Prefer specific multi-word phrases over single common words
#   - Single-word keywords must be domain-distinctive (not shared across domains)
#   - Short ambiguous terms ('gas', 'price', 'ship') go in _CONTEXT_REQUIRED below
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    'd1': [
        'missile', 'rocket', 'strike', 'airstrike', 'air strike',
        'artillery', 'hezbollah', 'houthi', 'pmf', 'kataib', 'ballistic',
        'casualt', 'killed', 'wounded', 'bomb', 'drone', 'uav', 'naval',
        'warship', 'carrier', 'centcom', 'sortie', 'air force',
        'brigade', 'battalion', 'front', 'theatre', 'kalibr', 'fattah',
        'shahab', 'iron dome', 'arrow-3', 'patriot',
        'irgc', 'idf', 'combat', 'troops', 'offensive', 'defensive operation',
    ],
    'd2': [
        'escalat', 'de-escalat', 'threshold', 'red line', 'tripwire',
        'nuclear', 'enrichment', 'natanz', 'fordow', 'iaea', 'inspector',
        'breakout', 'uranium', 'centrifuge', 'proliferat', 'deterren',
        'ceasefire', 'mediat', 'negotiat', 'pause', 'halt',
        'regime change', 'succession', 'khamenei', 'irgc command',
    ],
    'd3': [
        'oil', 'crude', 'brent', 'wti', 'barrel', 'petroleum',
        'natural gas', 'lng', 'pipeline', 'refin', 'strait of hormuz',
        'tanker', 'ukmto',
        'commodity', 'oil market', 'kpler', 'aramco', 'opec',
        'oil price', 'energy market', 'petroleum reserve', 'energy sector',
    ],
    'd4': [
        'diplomat', 'minister', 'foreign minister', 'secretary of state',
        'state department', 'white house', 'president', 'prime minister',
        'nato', 'european union', 'united nations', 'un security council',
        'security council resolution', 'sanction', 'alliance',
        'qatar', 'oman', 'saudi arabia', 'uae', 'turkey', 'erdogan',
        'russia', 'china', 'back-channel', 'ambassador', 'envoy',
        'witkoff', 'blinken', 'austin', 'congress', 'senate', 'g7',
    ],
    'd5': [
        'cyber', 'hack', 'malware', 'ransomware', 'ddos', 'phishing',
        'apt', 'charming kitten', 'phosphorus', 'tortoiseshell',
        'disinformation', 'psyop', 'information operation', 'propaganda',
        'deepfake', 'internet disruption', 'netblocks',
        'scada', 'ics', 'infrastructure attack',
        'hacktivist', 'cyber avenger', 'deface',
    ],
    'd6': [
        # JWC / listed areas
        'joint war committee', 'jwc', 'listed area', 'breach area',
        'war risk area', 'conwartime', 'voywar',
        # War risk premiums & pricing
        'war risk premium', 'war risk rate', 'war risk insurance', 'hull war', 'additional war risk',
        'awrp', 'war risk surcharge', 'war peril', 'marine war risk',
        # Underwriter / capacity signals
        "lloyd's war", "lloyd's syndicate", 'marine syndicate', 'underwriting capacity',
        'war exclusion', 'war risk exclusion', 'capacity withdrawal', 'line reduction',
        'market hardening', 'market softening', 'reinsurance capacity',
        # P&I clubs
        'p&i club', 'p&i circular', 'protection and indemnity', 'defence club',
        'steamship mutual', 'north of england', 'standard club', 'uk p&i',
        'gard p&i', 'skuld', 'west of england p&i', 'britannia p&i',
        # Broker / market commentary
        'war risk broker', 'marine insurance market', 'marine underwriter',
        'marsh marine', 'willis marine', 'aon marine', 'gallagher marine',
        # Reinsurance
        'munich re marine', 'swiss re marine', 'reinsurance war', 'retrocession',
        # High risk area designations
        'high risk area', 'best management practices', 'bmp6',
        'gulf of aden hra', 'red sea insurance', 'hormuz insurance',
        # Maritime security-insurance nexus
        'ship seized insurance', 'vessel seizure claim', 'constructive total loss',
        'war loss', 'hull war claim', 'ransom payment', 'k&fr',
        # Vessel operations impact
        'voyage diversion', 'route avoidance', 'ais diversion', 'blank sailing',
        'war risk bonus', 'hardship pay',
        # Cargo insurance
        'cargo war risk', 'cargo insurance premium', 'marine cargo',
        # Industry bodies
        'bimco war', 'intertanko war', 'intercargo war', 'iumi',
    ],
}

# Context-gated single words: only count when a context phrase is also present
_CONTEXT_REQUIRED: dict[str, list[str]] = {
    'ship':     ['war risk', 'p&i', 'hull war', 'marine insurance', 'maritime'],
    'vessel':   ['war risk', 'p&i', 'hull war', 'insurance', 'seized'],
    'market':   ['oil market', 'energy market', 'insurance market', 'war risk'],
    'energy':   ['energy market', 'energy sector', 'energy security', 'oil', 'lng'],
    'maritime': ['war risk', 'insurance', 'p&i', 'shipping', 'ukmto'],
    'insurance':['war risk', 'p&i', 'marine', 'hull', 'reinsurance'],
}


def _domain_match(text_lower: str, keywords: list[str]) -> bool:
    """
    Return True if text matches a domain keyword.
    Context-gated keywords in _CONTEXT_REQUIRED require a context word present too.
    """
    for kw in keywords:
        if kw in text_lower:
            ctx = _CONTEXT_REQUIRED.get(kw)
            if ctx and not any(c in text_lower for c in ctx):
                continue
            return True
    return False


def classify_item(item: dict) -> dict:
    """
    Add a 'tagged_domains' field to a RawItem based on source registry
    and keyword matching. Returns modified item copy.
    """
    item = dict(item)
    text_lower = (item.get('text', '') + ' ' + item.get('title', '')).lower()

    # Start with domains from source registry
    registry_domains: set[str] = set(item.get('domains', []))

    # Add domains from keyword matching
    keyword_domains: set[str] = set()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if _domain_match(text_lower, keywords):
            keyword_domains.add(domain)

    # Final tagged_domains = union of registry and keyword hits
    tagged = registry_domains | keyword_domains
    item['tagged_domains'] = sorted(tagged)

    # Diagnostic: items tagged to 5+ domains are often noise or very broad reports
    if len(tagged) >= 5:
        log.debug(
            'Item tagged to %d domains (possible noise): %s — %s',
            len(tagged), item.get('source_id', '?'), item.get('title', '')[:80],
        )

    return item


def classify_items(raw_items: list[dict]) -> list[dict]:
    """Classify all items. Returns list with 'tagged_domains' field added."""
    classified = [classify_item(item) for item in raw_items]

    # Log distribution
    domain_counts: dict[str, int] = {}
    untagged = 0
    for item in classified:
        domains = item.get('tagged_domains', [])
        if not domains:
            untagged += 1
            log.debug(
                'Untagged item (no domain match): %s — %s',
                item.get('source_id', '?'), item.get('title', '')[:80],
            )
        for d in domains:
            domain_counts[d] = domain_counts.get(d, 0) + 1

    log.info('Domain distribution: %s', domain_counts)
    if untagged:
        log.info('%d item(s) matched no domain and will not appear in any section', untagged)

    # Warn if any domain has < 3 items
    for domain in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']:
        count = domain_counts.get(domain, 0)
        if count < 3:
            log.warning('Domain %s has only %d items — brief section may be thin', domain, count)

    return classified
