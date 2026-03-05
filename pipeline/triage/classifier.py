"""
Domain classifier — tags each RawItem with one or more domain IDs
based on source registry defaults and keyword matching.
"""

import logging
import re

log = logging.getLogger(__name__)

# Domain keyword rules — each domain has a set of keywords.
# Items matching keywords are tagged to that domain even if not in registry.
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    'd1': [
        'missile', 'rocket', 'strike', 'attack', 'irgc', 'idf', 'airstrike',
        'artillery', 'hezbollah', 'houthi', 'pmf', 'kataib', 'ballistic',
        'casualt', 'killed', 'wounded', 'bomb', 'drone', 'uav', 'naval',
        'warship', 'carrier', 'centcom', 'sortie', 'air force', 'army',
        'brigade', 'battalion', 'front', 'theatre', 'kalibr', 'fattah',
        'shahab', 'iron dome', 'arrow-3', 'patriot',
        # Kurdish/Turkish battlespace
        'pkk', 'pjak', 'hpg', 'ypg', 'sdf', 'peshmerga',
        'operation claw', 'operation pence', 'turkish airstrike', 'turkish strike',
        'qandil', 'sinjar', 'duhok', 'zakho', 'kobane', 'manbij',
        'kdpi', 'komala', 'irgc strike kurdish',
    ],
    'd2': [
        'escalat', 'de-escalat', 'threshold', 'red line', 'tripwire',
        'nuclear', 'enrichment', 'natanz', 'fordow', 'iaea', 'inspector',
        'breakout', 'uranium', 'centrifuge', 'proliferat', 'deterren',
        'ceasefire', 'peace', 'mediat', 'negotiat', 'pause', 'halt',
        'regime change', 'succession', 'khamenei', 'irgc command',
    ],
    'd3': [
        'oil', 'crude', 'brent', 'wti', 'barrel', 'petroleum', 'energy',
        'gas', 'lng', 'natural gas', 'pipeline', 'refin', 'hormuz',
        'strait', 'tanker', 'ship', 'vessel', 'maritime', 'ukmto',
        'sanctions', 'supply chain', 'commodity', 'price', 'market',
        'goldman', 'insurance', "lloyd's", 'kpler', 'aramco', 'opec',
        'canadian', 'tsx', 'cad', 'wen', 'western canadian',
    ],
    'd4': [
        'diplomat', 'minister', 'foreign', 'secretary', 'state department',
        'white house', 'president', 'prime minister', 'nato', 'eu ', 'un ',
        'united nations', 'security council', 'sanction', 'alliance',
        'qatar', 'oman', 'saudi', 'uae', 'turkey', 'erdogan', 'russia',
        'china', 'back-channel', 'negotiat', 'ambassador', 'envoy',
        'witkoff', 'blinken', 'austin', 'congress', 'senate', 'g7',
        # Kurdish/Turkish diplomatic dimension
        'krg', 'kurdistan regional', 'barzani', 'erbil government',
        'hdp', 'dem parti', 'dem party', 'pkk negotiations',
        'us-turkey', 'turkey-us', 'nato-turkey', 'sdf arming',
        'kdpi expulsion', 'komala expulsion', 'krg-baghdad',
        'puk political', 'kdp political',
    ],
    'd5': [
        'cyber', 'hack', 'malware', 'ransomware', 'ddos', 'phishing',
        'apt', 'charming kitten', 'phosphorus', 'tortoiseshell',
        'disinformation', 'psyop', 'information operation', 'propaganda',
        'deepfake', 'blackout', 'internet disruption', 'netblocks',
        'scada', 'ics', 'infrastructure attack', 'social media',
        'telegram', 'hacktivist', 'cyber avenger', 'deface',
    ],
    'd6': [
        # JWC / listed areas
        'joint war committee', 'jwc', 'listed area', 'breach area',
        'war risk area', 'conwartime', 'voywar',
        # War risk premiums & pricing
        'war risk premium', 'war risk rate', 'hull war', 'additional war risk',
        'awrp', 'war risk surcharge', 'war peril', 'marine war',
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
        'high risk area', ' hra ', 'best management practices', 'bmp6',
        'gulf of aden hra', 'red sea insurance', 'hormuz insurance',
        # Maritime security-insurance nexus
        'ship seized insurance', 'vessel seizure claim', 'constructive total loss',
        ' ctl ', 'war loss', 'hull war claim', 'ransom payment', 'k&fr',
        # Vessel operations impact
        'voyage diversion', 'route avoidance', 'ais diversion', 'blank sailing',
        'crew bonus', 'war risk bonus', 'hardship pay',
        # Cargo insurance
        'cargo war risk', 'cargo insurance premium', 'marine cargo',
        # Industry bodies
        'bimco war', 'intertanko war', 'intercargo war', 'iumi',
    ],
}


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
        if any(kw in text_lower for kw in keywords):
            keyword_domains.add(domain)

    # Final tagged_domains = union of registry and keyword hits
    tagged = registry_domains | keyword_domains
    item['tagged_domains'] = sorted(tagged)

    return item


def classify_items(raw_items: list[dict]) -> list[dict]:
    """Classify all items. Returns list with 'tagged_domains' field added."""
    classified = [classify_item(item) for item in raw_items]

    # Log distribution
    domain_counts: dict[str, int] = {}
    for item in classified:
        for d in item.get('tagged_domains', []):
            domain_counts[d] = domain_counts.get(d, 0) + 1

    log.info('Domain distribution: %s', domain_counts)

    # Warn if any domain has < 3 items
    for domain in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6']:
        count = domain_counts.get(domain, 0)
        if count < 3:
            log.warning('Domain %s has only %d items — brief section may be thin', domain, count)

    return classified
