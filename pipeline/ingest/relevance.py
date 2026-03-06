"""
Relevance pre-filter for ingested items.

RSS feeds like AP, CNN, BBC, Reuters cover all world news. We only want items
relevant to Iran, the Gulf, and the surrounding conflict space. This module
runs a keyword check before triage and drops items that have no relevance signal.

Tier 1 items are NEVER dropped regardless of keywords — if CTP-ISW or IAEA
publish it, it's relevant by definition.
"""

import re
import logging

log = logging.getLogger(__name__)

# Comprehensive keyword set covering all five domains.
# Lowercase, matched against lowercased title+text.
RELEVANCE_KEYWORDS: frozenset[str] = frozenset([
    # ── Core state actors ───────────────────────────────────────────────────
    'iran', 'iranian', 'irgc', 'tehran', 'khamenei', 'pezeshkian',
    'supreme leader', 'islamic republic', 'revolutionary guard',
    'israel', 'israeli', 'idf', 'netanyahu', 'gallant', 'gantz',
    'mossad', 'shin bet', 'haifa', 'tel aviv', 'jerusalem',
    # ── Proxy forces ────────────────────────────────────────────────────────
    'hezbollah', 'nasrallah', 'hamas', 'islamic jihad',
    'houthi', 'houthis', 'ansar allah', 'ansarallah',
    'hashd', 'pmu', 'popular mobilization',
    'kataib', 'nujaba', 'fatemiyoun',
    # ── Nuclear ─────────────────────────────────────────────────────────────
    'nuclear', 'fordow', 'natanz', 'arak', 'bushehr', 'parchin',
    'enrichment', 'enriched uranium', 'centrifuge', 'uranium hexafluoride',
    'iaea', 'npt', 'safeguards', 'breakout', 'heu', 'highly enriched',
    'jcpoa', 'nuclear deal', 'iran deal', 'p5+1', 'e3',
    # ── Geography — conflict zone ────────────────────────────────────────────
    'hormuz', 'strait of hormuz', 'persian gulf', 'arabian gulf',
    'red sea', 'gulf of aden', 'arabian sea', 'bab el-mandeb',
    'gulf of oman', 'caspian',
    'lebanon', 'lebanese', 'beirut', 'south lebanon', 'blue line',
    'west bank', 'gaza', 'rafah',
    'syria', 'damascus', 'deir ez-zor', 'aleppo',
    'iraq', 'iraqi', 'baghdad', 'erbil', 'mosul', 'basra',
    'yemen', 'yemeni', "sana'a", 'aden', 'hudaydah', 'hodeidah',
    'saudi arabia', 'riyadh', 'neom',
    'uae', 'dubai', 'abu dhabi', 'emirates',
    'qatar', 'doha', 'bahrain', 'manama', 'oman', 'muscat', 'kuwait',
    'djibouti', 'eritrea',
    # ── Military events ─────────────────────────────────────────────────────
    'missile', 'ballistic missile', 'cruise missile', 'hypersonic',
    'shahab', 'fateh', 'zolfaghar', 'emad', 'qiam',
    'drone', 'uav', 'shahed', 'loitering munition',
    'airstrike', 'air strike', 'air raid', 'bombardment',
    'artillery', 'mortar', 'rocket',
    'iron dome', 'arrow-3', 'patriot', 'thaad', 'david sling',
    'f-35', 'f-15', 'f/a-18', 'b-52',
    'irgc aerospace', 'irgc navy', 'quds force',
    'centcom', 'ukmto', 'ctp-isw', 'isw',
    'carrier', 'aircraft carrier', 'destroyer', 'frigate', 'corvette',
    'uss ', 'hms ',
    # ── Maritime ────────────────────────────────────────────────────────────
    'tanker', 'oil tanker', 'vlcc', 'supertanker',
    'container ship', 'bulk carrier', 'maritime incident',
    'naval', 'warno', 'ukmto',
    # ── Energy / economic ───────────────────────────────────────────────────
    'brent', 'wti', 'crude oil', 'oil price',
    'petroleum', 'lng', 'liquefied natural gas', 'natural gas',
    'opec', 'opec+', 'barrel', 'oil supply', 'oil production',
    'iea', 'strategic petroleum reserve', 'spr',
    'energy market', 'oil market', 'refinery',
    'eia ', 'pipeline', 'hormuz closure', 'shipping lane',
    # ── Diplomatic / political ──────────────────────────────────────────────
    'sanctions', 'secondary sanctions', 'oil embargo',
    'ceasefire', 'peace talks', 'negotiations', 'diplomatic',
    'un security council', 'unsc', 'un resolution',
    'g7', 'nato', 'eu foreign policy',
    'state department', 'white house', 'pentagon',
    'secretary of state', 'national security advisor',
    'congress iran', 'senate iran',
    # ── Cyber / information ops ─────────────────────────────────────────────
    'apt33', 'apt34', 'apt35', 'apt39', 'apt42',
    'charming kitten', 'phosphorus', 'muddy water', 'muddywater',
    'oilrig', 'crambus', 'volt typhoon', 'volt sparrow',
    'iranian hacker', 'iranian cyber', 'irgc cyber',
    'iranian malware', 'iranian ransomware',
    'cyberattack', 'cyber attack', 'ics attack', 'ot attack',
    'scada', 'industrial control',
    'disinformation', 'influence operation',
])

# Pre-compile for speed.
# Short keywords (≤4 chars like 'uae', 'uss') get word boundaries to avoid
# false positives in longer words (e.g. 'cause' matching 'uae').
def _kw_to_pattern(kw: str) -> str:
    escaped = re.escape(kw)
    if len(kw) <= 4 and kw.isalpha():
        return rf'\b{escaped}\b'
    return escaped

_PATTERN = re.compile(
    '|'.join(_kw_to_pattern(kw) for kw in sorted(RELEVANCE_KEYWORDS, key=len, reverse=True)),
    re.IGNORECASE,
)


def is_relevant(item: dict) -> bool:
    """
    Return True if the item is relevant to Iran/Gulf conflict space.
    Tier 1 items are always relevant (never filtered).
    """
    if item.get('tier') == 1:
        return True

    haystack = ' '.join([
        item.get('title', ''),
        item.get('text', ''),
        item.get('full_content', ''),
    ])

    return bool(_PATTERN.search(haystack))


def filter_relevant(items: list[dict]) -> list[dict]:
    """
    Filter a list of RawItems to those relevant to Iran/Gulf conflict space.
    Logs how many were dropped.
    """
    before = len(items)
    relevant = [i for i in items if is_relevant(i)]
    dropped = before - len(relevant)
    if dropped:
        log.info(
            'Relevance filter: kept %d / %d items (dropped %d off-topic)',
            len(relevant), before, dropped,
        )
    return relevant
