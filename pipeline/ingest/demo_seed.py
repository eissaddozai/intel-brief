"""
Demo seed data — realistic synthetic items for local testing.
No internet or API required when running: python pipeline/main.py --demo

NOTE: source_id values MUST match sources.yaml exactly.
"""

from datetime import datetime, timezone

def get_seed_items(target_date: datetime) -> list[dict]:
    ts = target_date.strftime('%Y-%m-%dT06:00:00+00:00')
    ts_prev = target_date.strftime('%Y-%m-%dT03:00:00+00:00')
    date_str = target_date.strftime('%d %B %Y')

    return [
        # ── TIER 1 · BATTLESPACE (d1) ────────────────────────────────────────
        {
            'source_id': 'ctpiw_evening',
            'source_name': 'CTP-ISW Evening Report',
            'tier': 1,
            'domains': ['d1'],
            'title': 'CTP-ISW: IRGC ballistic missile salvo targets Haifa port district',
            'text': (
                f'[{date_str}] CTP-ISW assessed that the IRGC launched a salvo of '
                'approximately 18 Shahab-3 variant ballistic missiles at the Haifa port '
                'district at 0218 UTC. Israeli Iron Dome and Arrow-3 batteries intercepted '
                '14 of 18 missiles. Four missiles impacted the industrial waterfront, '
                'damaging a fuel storage facility and wounding seven dock workers.'
            ),
            'full_content': '',
            'url': 'https://www.criticalthreats.org/analysis/iran-war-updates',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'scrape',
        },
        {
            'source_id': 'centcom',
            'source_name': 'CENTCOM Press Releases',
            'tier': 1,
            'domains': ['d1'],
            'title': 'CENTCOM: USS Gravely intercepts four Houthi anti-ship ballistic missiles',
            'text': (
                f'CENTCOM statement [{date_str}]: USS Gravely (DDG-107) operating in the '
                'southern Red Sea successfully intercepted four Houthi anti-ship ballistic '
                'missiles at 2347 UTC. No casualties or damage to vessel reported. '
                'F/A-18 sorties from USS Harry S. Truman conducted follow-on strikes against '
                'Houthi launch infrastructure in Hudaydah governorate.'
            ),
            'full_content': '',
            'url': 'https://www.centcom.mil/MEDIA/NEWS-ARTICLES/',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'scrape',
        },
        {
            'source_id': 'ukmto',
            'source_name': 'UKMTO Maritime Bulletins',
            'tier': 1,
            'domains': ['d1', 'd3'],
            'title': 'UKMTO: Armed drone attack on MV Nordic Hawk, Bab el-Mandeb',
            'text': (
                'UKMTO WARNO 042/2026: MV Nordic Hawk (Liberian-flagged, 74,000 DWT bulk '
                'carrier) reported being struck by armed UAV at position 12°30\'N 043°20\'E '
                'at 0455 UTC. Vessel remains underway. Minor superstructure damage. '
                'Master reports three crew members sustained blast injuries. '
                'Vessel proceeding to Djibouti for assessment. All shipping advised '
                'to maintain heightened vigilance in the area.'
            ),
            'full_content': '',
            'url': 'https://www.ukmto.org/indian-ocean/recent-incidents',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'scrape',
        },
        {
            'source_id': 'ctpiw_morning',
            'source_name': 'CTP-ISW Morning Report',
            'tier': 1,
            'domains': ['d1'],
            'title': 'CTP-ISW: Ground situation — Hezbollah re-infiltrates Blue Line buffer',
            'text': (
                f'CTP-ISW [{date_str} morning]: Hezbollah anti-tank guided missile teams '
                'engaged two IDF Merkava IV tanks near Metula at 0530 local time, destroying '
                'one vehicle and wounding its crew. IDF artillery and Hermes-450 strikes '
                'responded within 20 minutes. Fighting remains confined to the border strip. '
                'CTP-ISW assesses Hezbollah is probing IDF response cadence rather than '
                'initiating a major ground offensive.'
            ),
            'full_content': '',
            'url': 'https://www.criticalthreats.org/analysis/iran-war-updates',
            'timestamp': ts_prev,
            'verification_status': 'confirmed',
            'method': 'scrape',
        },
        # ── TIER 2 · BATTLESPACE (d1) ────────────────────────────────────────
        {
            'source_id': 'bbc_mideast',
            'source_name': 'BBC Middle East',
            'tier': 2,
            'domains': ['d1'],
            'title': 'BBC: Israeli PM convenes emergency security cabinet after Haifa strike',
            'text': (
                'Israeli Prime Minister Netanyahu convened an emergency session of the '
                'security cabinet at 0400 local time following the overnight ballistic '
                'missile attack on Haifa port. Defense Minister Galant confirmed four '
                'impacting missiles and said Israel was "evaluating options."'
            ),
            'full_content': '',
            'url': 'https://www.bbc.com/news/world-middle-east',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'rss',
        },
        {
            'source_id': 'iran_intl',
            'source_name': 'Iran International',
            'tier': 2,
            'domains': ['d1', 'd2'],
            'title': 'Iran International: IRGC Aerospace claims "precision suppression" of Haifa port',
            'text': (
                'IRGC Aerospace Force stated in a Telegram release that the overnight strike '
                'on Haifa constituted a "calibrated response to Zionist aggression" and '
                'claimed all 18 missiles reached their designated targets — a claim at '
                'variance with Israeli military statements. Iran International assesses '
                'the IRGC statement is likely exaggerated for domestic morale purposes.'
            ),
            'full_content': '',
            'url': 'https://www.iranintl.com/en',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'scrape',
        },
        # ── TIER 1 · ESCALATION (d2) ────────────────────────────────────────
        {
            'source_id': 'iaea',
            'source_name': 'IAEA Statements',
            'tier': 1,
            'domains': ['d2'],
            'title': 'IAEA Board of Governors: Iran bars inspectors from Fordow',
            'text': (
                f'IAEA Director General Grossi notified the Board of Governors [{date_str}] '
                'that Iran has suspended IAEA inspector access to the Fordow Fuel Enrichment '
                'Plant effective 0600 UTC. The IAEA\'s continuous monitoring equipment at '
                'Fordow has been disconnected. Grossi stated this constitutes a "serious '
                'breach" of Iran\'s safeguards obligations under the NPT.'
            ),
            'full_content': '',
            'url': 'https://www.iaea.org/feeds/topstories.xml',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'rss',
        },
        # ── TIER 2 · ESCALATION (d2) ────────────────────────────────────────
        {
            'source_id': 'icg',
            'source_name': 'International Crisis Group',
            'tier': 2,
            'domains': ['d2', 'd4'],
            'title': 'ICG: Fordow access suspension raises weaponization breakout risk',
            'text': (
                'ICG analysis: Iran\'s suspension of IAEA access to Fordow removes the '
                'primary international visibility mechanism on Iran\'s highest-enrichment '
                'activities. ICG estimates Iran has sufficient 60% enriched UF6 to produce '
                'one weapon\'s worth of HEU within 10–14 days if political decision made. '
                'Diplomatic off-ramp requires immediate P5+1 engagement.'
            ),
            'full_content': '',
            'url': 'https://www.crisisgroup.org/rss.xml',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'rss',
        },
        {
            'source_id': 'cfr_daily',
            'source_name': 'CFR Daily News Brief',
            'tier': 2,
            'domains': ['d2', 'd4'],
            'title': 'CFR: US strategic bombers deploy to Diego Garcia amid Iran nuclear standoff',
            'text': (
                'The Pentagon confirmed the deployment of six B-52H Stratofortress aircraft '
                'to Diego Garcia in a "routine deterrence patrol." Analysts note the timing '
                'coincides with the Fordow access suspension and assess it as a deliberate '
                'signalling measure directed at Tehran.'
            ),
            'full_content': '',
            'url': '',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'email',
        },
        # ── TIER 1 · ENERGY (d3) ────────────────────────────────────────────
        {
            'source_id': 'centcom',
            'source_name': 'CENTCOM Press Releases',
            'tier': 1,
            'domains': ['d3'],
            'title': 'CENTCOM: Strait of Hormuz transit corridor operating with escort',
            'text': (
                'CENTCOM confirms the Strait of Hormuz transit corridor remains operational '
                'under Combined Maritime Forces escort. Commercial transits reduced to '
                'daylight hours only. Two VLCC tankers diverted to Cape of Good Hope route '
                'following insurance market guidance. Approximate daily throughput: '
                '14 million bpd (vs. normal 21 million bpd).'
            ),
            'full_content': '',
            'url': 'https://www.centcom.mil/MEDIA/NEWS-ARTICLES/',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'scrape',
        },
        # ── TIER 2 · ENERGY (d3) ────────────────────────────────────────────
        {
            'source_id': 'reuters_mideast',
            'source_name': 'Reuters Middle East',
            'tier': 2,
            'domains': ['d3'],
            'title': 'Reuters: Brent crude hits $147/bbl as Hormuz throughput falls',
            'text': (
                'Brent crude futures surged to $147.20 per barrel at open, the highest '
                'since July 2022, as Hormuz throughput constraints and Red Sea diversions '
                'compounded supply anxiety. IEA activated emergency reserves for the '
                'third time in twelve months, releasing 60 million barrels over 30 days. '
                'Saudi Arabia pledged to maximize production within current OPEC+ quota '
                'framework.'
            ),
            'full_content': '',
            'url': 'https://www.reuters.com/world/middle-east/',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'scrape',
        },
        {
            'source_id': 'cnbc_energy',
            'source_name': 'CNBC Energy',
            'tier': 2,
            'domains': ['d3'],
            'title': 'CNBC: LNG spot prices spike 40% as tankers avoid Red Sea',
            'text': (
                'Asian LNG spot prices jumped 40% week-on-week to $32/MMBtu as operators '
                'reroute shipments around the Cape of Good Hope, adding 14 days to voyage '
                'times. South Korea and Japan activated strategic LNG reserves. '
                'European storage at 48% capacity heading into the shoulder season.'
            ),
            'full_content': '',
            'url': 'https://www.cnbc.com/id/19832390/device/rss/rss.html',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'rss',
        },
        # ── TIER 2 · DIPLOMATIC (d4) ────────────────────────────────────────
        {
            'source_id': 'ap_wire',
            'source_name': 'Associated Press',
            'tier': 1,
            'domains': ['d4'],
            'title': 'AP: UN Security Council emergency session fails, Russia/China veto ceasefire',
            'text': (
                'The UN Security Council failed to pass an emergency resolution calling '
                'for an immediate ceasefire after Russia and China exercised their veto. '
                'The US-drafted text received 11 votes in favour with three abstentions. '
                'UK Foreign Secretary and French Foreign Minister issued joint statement '
                'calling on Iran to restore IAEA access within 48 hours.'
            ),
            'full_content': '',
            'url': 'https://feeds.apnews.com/rss/apf-intlnews',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'rss',
        },
        {
            'source_id': 'cfr_daily',
            'source_name': 'CFR Daily News Brief',
            'tier': 2,
            'domains': ['d4'],
            'title': 'CFR: Omani back-channel to Iran described as "active but not productive"',
            'text': (
                'Omani Foreign Minister Al Busaidi briefed EU envoys in Brussels that '
                'Muscat\'s back-channel communication with Tehran is "active but has not '
                'produced concrete progress." Oman has historically served as an '
                'intermediary between the US and Iran. Sources indicate Iran is '
                'conditioning any ceasefire on lifting of all secondary sanctions.'
            ),
            'full_content': '',
            'url': '',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'email',
        },
        {
            'source_id': 'icg',
            'source_name': 'International Crisis Group',
            'tier': 2,
            'domains': ['d4'],
            'title': 'ICG: GCC states divide on Iran policy as UAE-Iran trade links persist',
            'text': (
                'ICG notes GCC states are not unified: UAE has maintained trade and banking '
                'links with Iran worth approximately $25B annually. Qatar maintains gas '
                'cooperation. Saudi Arabia and Bahrain have aligned with US maximum-pressure '
                'posture. ICG warns that coalition fragmentation risks undermining '
                'any multilateral diplomatic initiative.'
            ),
            'full_content': '',
            'url': 'https://www.crisisgroup.org/rss.xml',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'rss',
        },
        # ── TIER 2/3 · CYBER (d5) ────────────────────────────────────────────
        {
            'source_id': 'cisa_advisories',
            'source_name': 'CISA Cybersecurity Advisories',
            'tier': 3,
            'domains': ['d5'],
            'title': 'CISA AA26-063A: Iranian threat actors targeting critical infrastructure OT/ICS',
            'text': (
                'CISA Advisory AA26-063A: Iranian state-sponsored actors (attributed to '
                'IRGC-affiliated group "Volt Sparrow") are actively exploiting '
                'Unitronics PLC vulnerabilities (CVE-2023-6448) in water/wastewater '
                'facilities and energy sector OT networks across North America and Europe. '
                'FBI and CISA recommend immediate patching and network segmentation.'
            ),
            'full_content': '',
            'url': 'https://www.cisa.gov/cybersecurity-advisories/all.xml',
            'timestamp': ts,
            'verification_status': 'claimed',
            'method': 'rss',
        },
        {
            'source_id': 'recorded_future',
            'source_name': 'Recorded Future Research Blog',
            'tier': 3,
            'domains': ['d5'],
            'title': 'Recorded Future: APT35 infrastructure expansion targets Israeli financial sector',
            'text': (
                'Recorded Future Insikt Group identifies new APT35 (Charming Kitten) '
                'C2 infrastructure targeting Israeli banking and telecoms sector. '
                'Spear-phishing lures impersonate Bank Leumi correspondence. '
                'Malware family identified as updated HYPERSCRAPE variant with '
                'credential-harvesting and persistent access capabilities. '
                'High confidence attribution to MOIS.'
            ),
            'full_content': '',
            'url': 'https://www.recordedfuture.com/research/feed',
            'timestamp': ts,
            'verification_status': 'claimed',
            'method': 'rss',
        },
        {
            'source_id': 'netblocks',
            'source_name': 'NetBlocks Internet Observatory',
            'tier': 3,
            'domains': ['d5'],
            'title': 'NetBlocks: Major internet disruption detected across Iran, 60% connectivity loss',
            'text': (
                'NetBlocks Observatory confirms a significant internet disruption affecting '
                'Iran with national connectivity at approximately 40% of normal levels. '
                'Disruption began 0322 UTC, consistent with government-imposed throttling '
                'or infrastructure damage. Providers TIC, MCI, and Rightel all affected. '
                'Social media platforms and VPN traffic suppressed.'
            ),
            'full_content': '',
            'url': 'https://netblocks.org',
            'timestamp': ts,
            'verification_status': 'claimed',
            'method': 'scrape',
        },
        # ── TIER 1 · WAR RISK INSURANCE (d6) ─────────────────────────────────
        {
            'source_id': 'jwc_listed_areas',
            'source_name': 'Joint War Committee Listed Areas',
            'tier': 1,
            'domains': ['d6', 'd3'],
            'title': 'JWC: Listed areas expanded to include full Persian Gulf basin',
            'text': (
                f'Joint War Committee [{date_str}]: Following overnight missile exchanges, '
                'the JWC has expanded the listed area to encompass the entire Persian Gulf '
                'basin including all waters north of 24°N latitude. Previous listed area '
                'covered only the Strait of Hormuz transit corridor. All vessels transiting '
                'the expanded zone now require additional war risk premium notification to '
                'lead underwriters. Effective immediately.'
            ),
            'full_content': '',
            'url': 'https://www.lmalloyds.com/LMA/Underwriting_Committees/Marine_Committees/LMA_JWC/JWC_war_listed_areas.aspx',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'scrape',
        },
        {
            'source_id': 'ig_pic_circulars',
            'source_name': 'International Group of P&I Clubs',
            'tier': 1,
            'domains': ['d6'],
            'title': 'IG P&I Circular 17/2026: War Risk Additional Premium for Persian Gulf transits',
            'text': (
                'The International Group of P&I Clubs has issued Circular 17/2026 advising '
                'all member clubs that additional war risk premiums for Persian Gulf transits '
                'have been revised upward by 0.15% of vessel value (from 0.05% prior). '
                'Circular notes that underwriters are requiring 72-hour advance notification '
                'for all Hormuz transits. Retroactive cover is no longer available.'
            ),
            'full_content': '',
            'url': 'https://www.igpandi.org/news/',
            'timestamp': ts,
            'verification_status': 'confirmed',
            'method': 'scrape',
        },
        # ── TIER 2 · WAR RISK INSURANCE (d6) ─────────────────────────────────
        {
            'source_id': 'hellenicshipping',
            'source_name': 'Hellenic Shipping News',
            'tier': 2,
            'domains': ['d6', 'd3'],
            'title': 'Hellenic Shipping: War risk premiums triple for Gulf-bound tankers',
            'text': (
                'London market war risk premiums for Gulf-bound tankers have tripled in the '
                'past 48 hours following the JWC listed area expansion. Lloyd\'s syndicates '
                'are quoting 0.15-0.20% of hull value for single Hormuz transits, up from '
                '0.05% last week. Several smaller syndicates have withdrawn capacity entirely. '
                'Marsh estimates daily war risk cost for a laden VLCC at $150,000-200,000.'
            ),
            'full_content': '',
            'url': 'https://www.hellenicshippingnews.com/feed/',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'rss',
        },
        {
            'source_id': 'dryad_global',
            'source_name': 'Dryad Global Maritime Security',
            'tier': 2,
            'domains': ['d6', 'd1', 'd3'],
            'title': 'Dryad: Threat level raised to CRITICAL for Persian Gulf and Southern Red Sea',
            'text': (
                'Dryad Global has raised its maritime threat assessment for the Persian Gulf '
                'and Southern Red Sea to CRITICAL (highest level). Assessment notes multiple '
                'concurrent threats: IRGC fast-attack craft activity in the Strait, continued '
                'Houthi ASBM launches in the Bab el-Mandeb, and unattributed mine-laying '
                'reports near Fujairah anchorage. Recommends all non-essential transits be '
                'postponed pending threat re-evaluation.'
            ),
            'full_content': '',
            'url': 'https://www.dryadglobal.com/news',
            'timestamp': ts,
            'verification_status': 'reported',
            'method': 'scrape',
        },
    ]
