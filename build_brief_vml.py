"""
build_brief_vml.py — Generate the CSE Intelligence Brief as an HTML/VML Word document.

Usage:
    python3 build_brief_vml.py [--date YYYY-MM-DD]

Output:
    briefs/CSE_Intel_Brief_YYYYMMDD.doc

The analyst edits the CONTENT VARIABLES section below, then runs this script.
Word opens .doc files containing HTML + VML extensions natively, enabling true
dark-background rendering with gradient fills — something python-docx cannot achieve.

LAYOUT RULES (enforced throughout):
  - ALL layout via <table> — Word strips div/flex/grid/position
  - bgcolor attribute on every <td> — CSS background-color is stripped by Word
  - border attribute on <table> — CSS borders are stripped by Word
  - cellspacing=0 cellpadding=0 on every table
"""

import argparse
import os
import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT VARIABLES — edit these each cycle
# ═══════════════════════════════════════════════════════════════════════════════

CYCLE_DATE       = "4 March 2026"
CYCLE_NUM        = "004"
CYCLE_ID         = "CSE-BRIEF-004-20260304"
TIMESTAMP_UTC    = "06:00 UTC, 4 March 2026"
CLASSIFICATION   = "PROTECTED B"
TLP              = "TLP:AMBER"
ANALYST_UNIT     = "CSE Conflict Assessment Unit"
REGION           = "Iran · Gulf Region · Eastern Mediterranean"
THREAT_LEVEL     = "SEVERE"
THREAT_TRAJ      = "ESCALATING ↑"
CONFLICT_DAY     = "Day 89"

# Threat status strip — 8 cells: label / value pairs
STATUS_CELLS = [
    ("THREAT LEVEL",       "SEVERE",     "#c0392b"),
    ("TRAJECTORY",         "ESCALATING ↑", "#d68910"),
    ("BRENT CRUDE",        "$118 / bbl",  "#d68910"),
    ("HORMUZ STATUS",      "OPEN · RESTRICTED", "#d68910"),
    ("IR CONNECTIVITY",    "61%",         "#d68910"),
    ("UKMTO INCIDENTS",    "43 this cycle", "#c0392b"),
    ("CONFLICT DAY",       "Day 89",      "#00d4ff"),
    ("NEXT CYCLE",         "18:30 UTC",   "#5a7a8a"),
]

# ── EXECUTIVE SUMMARY ─────────────────────────────────────────────────────────
EXECUTIVE_PARAS = [
    (
        "The overnight period of 3–4 March saw one of the most consequential exchanges "
        "since hostilities began in December 2025. The Islamic Revolutionary Guard Corps "
        "(IRGC) launched its largest single salvo against Israeli territory to date — 18 "
        "Shahab-3 extended-range ballistic missiles aimed at the Haifa port district — of "
        "which four reached their targets despite a largely effective Israeli intercept "
        "effort. The physical damage was limited, but the penetration rate underscores a "
        "trajectory that Israeli planners cannot indefinitely absorb without responding."
    ),
    (
        "The nuclear dimension sharpened considerably when Iran suspended IAEA inspector "
        "access to the Fordow Fuel Enrichment Plant and disconnected continuous monitoring "
        "equipment on site — removing the last meaningful international visibility mechanism "
        "over its highest-enrichment activities. The International Crisis Group estimates "
        "that Iran's current 60 per cent enriched stockpile is sufficient to produce one "
        "weapon's worth of highly enriched uranium within ten to fourteen days if Tehran "
        "chose to proceed, a timeline now unobservable from outside the facility (ICG, "
        "4 March). The American response was the deployment of six B-52H aircraft to Diego "
        "Garcia — a move timed too precisely to be coincidental."
    ),
    (
        "Taken together, the overnight salvo, the Fordow suspension, and the sustained "
        "Houthi maritime harassment campaign — the 43rd recorded incident of this cycle — "
        "describe a conflict that is broadening rather than approaching resolution. Brent "
        "crude held near $118 per barrel on 4 March, and shipping war-risk premiums in the "
        "Gulf of Aden have widened to levels comparable to the worst of the 2019–2020 "
        "escalation cycle. The diplomatic path, meanwhile, remains blocked: a French and "
        "British draft resolution at the Security Council calling for a ceasefire and "
        "restored IAEA access is expected to meet Russian and Chinese vetoes."
    ),
]

# ── KEY JUDGMENTS ─────────────────────────────────────────────────────────────
KEY_JUDGMENTS = [
    {
        "num": "KJ-1",
        "domain": "D1",
        "confidence": "HIGH",
        "conf_color": "#1e8449",
        "text": (
            "Iran's demonstrated capacity to land ordnance within Haifa port despite "
            "multi-layered Israeli air defences, and the finite magazine of Israel's "
            "Arrow-3 batteries, make an Israeli decision to strike IRGC missile production "
            "and storage infrastructure in the coming days more rather than less likely."
        ),
        "basis": "CTP-ISW, 3 March evening; open-source satellite imagery",
    },
    {
        "num": "KJ-2",
        "domain": "D2",
        "confidence": "HIGH",
        "conf_color": "#1e8449",
        "text": (
            "Iran's suspension of IAEA monitoring at Fordow has materially reduced the "
            "effective international warning time before a possible weapons-grade uranium "
            "production cycle. The loss of real-time visibility is irreversible until "
            "inspector access is restored, which requires diplomatic progress not currently "
            "in prospect."
        ),
        "basis": "IAEA Board notification, 4 March; ICG analysis, 4 March",
    },
    {
        "num": "KJ-3",
        "domain": "D3",
        "confidence": "MODERATE",
        "conf_color": "#d68910",
        "text": (
            "Brent crude is likely to remain above $110 per barrel through at least "
            "the end of March, with the primary risk to the upside being any sustained "
            "interdiction of Hormuz traffic. A full Hormuz closure would push prices well "
            "above $150 per barrel — a scenario the available evidence does not yet support, "
            "but cannot exclude."
        ),
        "basis": "Goldman Sachs energy desk, 3 March; IEA statement, 3 March",
    },
    {
        "num": "KJ-4",
        "domain": "D4",
        "confidence": "MODERATE",
        "conf_color": "#d68910",
        "text": (
            "The B-52H deployment to Diego Garcia is best read as a coercive signal "
            "directed at Tehran rather than as immediate preparation for strikes on Iranian "
            "nuclear sites, though the two interpretations are not mutually exclusive and "
            "the window between signalling and action may be narrowing."
        ),
        "basis": "CFR Daily Brief, 4 March; Pentagon statement, 3 March",
    },
    {
        "num": "KJ-5",
        "domain": "D5",
        "confidence": "MODERATE",
        "conf_color": "#d68910",
        "text": (
            "Iranian cyber operations targeting North American and European critical "
            "infrastructure, and Israeli financial and telecommunications networks, are "
            "being run in parallel with the missile campaign — a pattern consistent with "
            "Tehran seeking to deter Western intervention by raising the cost of involvement "
            "rather than seeking immediate operational disruption."
        ),
        "basis": "CISA AA26-063A, 3 March; Recorded Future Insikt Group, 3 March",
    },
]

# ── D1 BATTLESPACE ────────────────────────────────────────────────────────────
D1_QUESTION = (
    "What was the character and outcome of armed exchanges across all theatres "
    "in the 24 hours to 06:00 UTC, 4 March, and what do they indicate about "
    "the near-term operational trajectory?"
)
D1_KEY_JUDGMENT = (
    "The overnight salvo against Haifa — the largest single IRGC missile attack on "
    "Israeli territory to date — achieved a penetration rate of roughly 22 per cent "
    "despite multi-layered defences, a result that will sustain Israeli pressure for "
    "a decisive counter-strike on IRGC missile infrastructure even as the physical "
    "damage from four impacting warheads remains commercially rather than militarily "
    "significant."
)
D1_CONFIDENCE = "HIGH"
D1_CONF_COLOR = "#1e8449"

D1_PARAS = [
    (
        "Shortly after midnight on 3 March, beginning at approximately 02:18 UTC, the IRGC "
        "Aerospace Force launched a salvo of approximately 18 Shahab-3 extended-range "
        "ballistic missiles toward the Haifa port district. Israel's Iron Dome and Arrow-3 "
        "batteries intercepted 14 of the 18 incoming missiles — a broadly effective "
        "performance by any historical standard, though the four missiles that reached the "
        "industrial waterfront ignited fires at a fuel storage facility and wounded seven "
        "dock workers (CTP-ISW, 3 March evening). No fatalities have been confirmed and "
        "port operations are reported to have resumed by early afternoon."
    ),
    (
        "The significance of the exchange lies less in the physical damage, which is "
        "commercially disruptive but strategically limited, than in what the penetration "
        "rate reveals about the arithmetic of Israeli air defence. Arrow-3 batteries carry "
        "a finite inventory, and the IRGC has demonstrated that it understands the "
        "relationship between salvo size and interceptor saturation. Each successful "
        "penetration compounds the political pressure on Israeli officials to act against "
        "the source of the missiles rather than continue to absorb them. A parallel salvo "
        "of Fateh-313 rockets struck the northern communities of Kiryat Shmona and Metulla "
        "in the early morning hours, causing structural damage but no reported casualties "
        "(IDF Spokesperson, 4 March)."
    ),
    (
        "In the southern maritime theatre, USS Gravely (DDG-107) intercepted four Houthi "
        "anti-ship ballistic missiles in the southern Red Sea at 23:47 UTC, with F/A-18 "
        "sorties from USS Harry S. Truman conducting follow-on strikes against launch "
        "infrastructure in Hudaydah governorate within the hour (CENTCOM, 4 March). A "
        "separate Houthi attack on MV Nordic Hawk — a Liberian-flagged 74,000-DWT bulk "
        "carrier — struck the vessel with an armed UAV at approximately 04:55 UTC at "
        "position 12°30'N 043°20'E, wounding three crew members (UKMTO WARNO 042/2026). "
        "The vessel proceeded to Djibouti under its own power. The attack was the 43rd "
        "UKMTO-recorded maritime incident of the current cycle, confirming that Houthi "
        "maritime operations have not been materially degraded by sustained counter-battery "
        "strikes."
    ),
    (
        "Along the Lebanese border, Hezbollah anti-tank guided missile teams destroyed one "
        "IDF Merkava IV tank near Metula and damaged a second at approximately 05:30 local "
        "time. IDF artillery and Hermes-450 strikes responded within 20 minutes. CTP-ISW "
        "assessed that the engagement pattern is more consistent with reconnaissance-by-fire "
        "tactics — testing Israeli response cadence — than with the opening moves of a "
        "broader ground offensive (CTP-ISW, 4 March morning). The assessment is plausible, "
        "though the distance between tactical probing and miscalculated escalation has "
        "historically been small on this border."
    ),
    (
        "Kataib Hezbollah, operating from Iraqi territory, launched a drone swarm against "
        "Al-Asad Air Base in Anbar province overnight, wounding two US service members and "
        "damaging a maintenance facility (Reuters, 4 March). The attack was the sixth "
        "recorded Iraqi proxy strike on coalition positions this cycle."
    ),
]

D1_OPS_TABLE = {
    "caption": "RECORDED EXCHANGES · 03–04 MARCH 2026",
    "headers": ["THEATRE", "ACTOR", "INCIDENT", "OUTCOME", "SOURCE"],
    "rows": [
        ["Israel · Haifa",    "IRGC",             "18× Shahab-3 salvo, 02:18 UTC",            "14 intercepted; 4 impact port area, 7 wounded",    "CTP-ISW T1"],
        ["Israel · North",    "IRGC / Hezbollah", "Fateh-313 rockets, Kiryat Shmona/Metulla",  "Structural damage, no casualties confirmed",        "IDF Spokesperson T1"],
        ["Red Sea",           "Houthi",           "4× ASBM intercept by USS Gravely, 23:47 UTC","0 casualties; Truman F/A-18 strikes follow",        "CENTCOM T1"],
        ["Gulf of Aden",      "Houthi",           "UAV strike on MV Nordic Hawk, 04:55 UTC",   "3 crew wounded; vessel proceeds to Djibouti",       "UKMTO T1"],
        ["Lebanon · Metula",  "Hezbollah",        "ATGM strike on Merkava IV tank, 05:30 local","1 tank destroyed, 1 damaged; IDF response <20 min","CTP-ISW T1"],
        ["Iraq · Al-Asad AB", "Kataib Hezbollah", "Drone swarm, overnight",                    "2 US wounded; maintenance facility damaged",         "Reuters T2"],
    ],
}

# ── D2 NUCLEAR ────────────────────────────────────────────────────────────────
D2_QUESTION = (
    "What does Iran's suspension of IAEA monitoring at Fordow mean for the "
    "trajectory of its nuclear programme, and what warning time remains available "
    "to policymakers?"
)
D2_KEY_JUDGMENT = (
    "Iran's disconnection of IAEA monitoring equipment at Fordow on 4 March removes "
    "the last meaningful international verification mechanism at its most hardened "
    "enrichment facility — materially shortening the actionable warning time before "
    "a possible weapons-grade production cycle to an interval now unobservable "
    "from outside."
)
D2_CONFIDENCE = "HIGH"
D2_CONF_COLOR = "#1e8449"

D2_PARAS = [
    (
        "IAEA Director General Rafael Grossi notified the Board of Governors on 4 March "
        "that Iran had suspended inspector access to the Fordow Fuel Enrichment Plant "
        "effective 06:00 UTC and had disconnected the IAEA's continuous monitoring "
        "equipment on site. Grossi described the action as a 'serious breach' of Iran's "
        "safeguards obligations under the Nuclear Non-Proliferation Treaty (IAEA Board "
        "notification, 4 March)."
    ),
    (
        "The significance of this step is substantial. Fordow, built into a mountain "
        "near Qom and designed to withstand conventional air attack, is the facility where "
        "Iran has concentrated its 60 per cent enriched uranium production — a purity "
        "only a few further centrifuge steps removed from weapons-grade material. The "
        "International Crisis Group estimates that Iran's existing stockpile of 60 per cent "
        "enriched uranium hexafluoride is sufficient to produce one weapon's worth of "
        "highly enriched uranium within ten to fourteen days if Tehran committed to the "
        "process (ICG, 4 March). With monitoring equipment disconnected, that interval is "
        "now essentially undetectable from outside."
    ),
    (
        "The disconnection of monitoring equipment does not itself confirm that Iran is "
        "currently enriching toward weapons grade; the action is consistent with several "
        "motivations, including a desire to create negotiating ambiguity, domestic political "
        "signalling, or actual preparation for an accelerated enrichment cycle. The problem "
        "is that these interpretations are no longer distinguishable in real time. The "
        "practical effect is that the international community has lost the early-warning "
        "function that IAEA presence at Fordow provided, and that the gap in knowledge "
        "cannot be remedied until inspector access is restored — an outcome requiring "
        "diplomatic progress not currently in prospect."
    ),
    (
        "The question of physical damage to Iranian nuclear infrastructure from Israeli "
        "strikes earlier in the conflict also bears on this assessment. Open-source "
        "satellite imagery and reporting from CTP-ISW and Alma Research suggest that "
        "Natanz surface facilities suffered significant damage in strikes on 15 and "
        "22 February, but that Fordow's deeply buried cascade halls remain largely intact "
        "— which is partly why Iran's decision to concentrate monitoring resistance there "
        "rather than at Natanz carries the weight it does."
    ),
]

# ── D3 ENERGY / ECONOMIC ──────────────────────────────────────────────────────
D3_QUESTION = (
    "How is the conflict affecting global energy markets and Hormuz transit, "
    "and what are the near-term implications for Canadian economic interests?"
)
D3_KEY_JUDGMENT = (
    "Brent crude is holding near $118 per barrel, sustained by Houthi maritime "
    "harassment, war-risk premium widening in the Gulf of Aden, and the Fordow "
    "suspension as a new escalation factor. Goldman Sachs revised its near-term "
    "forecast upward on 3 March and a sustained price above $110 appears more "
    "probable than a correction, absent a ceasefire or diplomatic breakthrough."
)
D3_CONFIDENCE = "MODERATE"
D3_CONF_COLOR = "#d68910"

D3_PARAS = [
    (
        "Brent crude opened at approximately $118 per barrel on 4 March, representing "
        "a roughly 40 per cent increase since conflict operations began in late 2025. "
        "The overnight UAV attack on MV Nordic Hawk was the 43rd UKMTO-recorded maritime "
        "incident of the current cycle and contributed to further widening of war-risk "
        "insurance premiums in the Gulf of Aden, now running at approximately 0.75 per "
        "cent of vessel value per single transit — comparable to the worst periods of the "
        "2019–2020 Houthi escalation (Lloyd's Market Association, 3 March)."
    ),
    (
        "Shipping companies are responding by rerouting LNG and crude tankers around the "
        "Cape of Good Hope, adding between ten and fourteen days to transit times from the "
        "Gulf to European ports. This rerouting is not logistically crippling, but it "
        "reduces effective supply availability and pressures European LNG import "
        "infrastructure that entered the winter season with lower-than-average storage "
        "buffers. The International Energy Agency noted on 3 March that European gas "
        "storage stands at 47 per cent capacity — below the five-year seasonal average — "
        "and that sustained Red Sea disruption without compensating spot LNG shipments "
        "will tighten supply through spring (IEA, 3 March)."
    ),
    (
        "For Canadian producers, the sustained elevation of the Brent benchmark is "
        "financially favourable in the short term, with Western Canadian Select trading "
        "at an unusually narrow discount of approximately $12/bbl — considerably tighter "
        "than its historical average of $18–20/bbl — reflecting strong demand for "
        "non-Gulf crude. The Bank of Canada's March 3 Financial Stability Report flagged "
        "sustained energy price elevation as a key variable in its second-quarter inflation "
        "modelling, estimating a pass-through to retail fuel of approximately 60 per cent "
        "of the Brent increase."
    ),
    (
        "The Strait of Hormuz remains open to commercial traffic as of 06:00 UTC on "
        "4 March. Iran has historically used the threat of Hormuz closure as diplomatic "
        "leverage, and the IRGC Navy has increased patrol activity in the strait over the "
        "past fortnight, but no physical interdiction of traffic has been recorded. The "
        "risk of closure rises materially if Israel conducts strikes inside Iranian "
        "territory — an assessment consistent across Goldman Sachs, Wood Mackenzie, and "
        "independent Persian Gulf security analysts."
    ),
]

D3_MARKET_TABLE = {
    "caption": "KEY ENERGY INDICATORS · 04 MARCH 2026",
    "headers": ["INDICATOR", "VALUE", "CHANGE (24H)", "TREND", "SOURCE"],
    "rows": [
        ["Brent Crude",              "$118.40 / bbl",   "+$1.80",   "↑",  "ICE Futures, 04 Mar"],
        ["WTI Crude",                "$115.30 / bbl",   "+$1.60",   "↑",  "NYMEX, 04 Mar"],
        ["Western Canadian Select",  "$106.40 / bbl",   "+$1.50",   "↑",  "Platts, 04 Mar"],
        ["Henry Hub Natural Gas",    "$4.82 / MMBtu",   "+$0.12",   "↑",  "NYMEX, 04 Mar"],
        ["Gulf of Aden War-Risk",    "0.75% hull value", "+0.05pp", "↑",  "Lloyd's MIF, 03 Mar"],
        ["Hormuz Status",            "OPEN — restricted patrols", "—", "→", "UKMTO / CENTCOM"],
        ["EU Gas Storage",           "47% capacity",    "-2pp wk",  "↓",  "GIE AGSI+, 03 Mar"],
        ["Cape Rerouting Premium",   "+$2.1M / voyage", "+$0.3M",  "↑",  "Kpler est., 03 Mar"],
    ],
}

# ── D4 DIPLOMATIC / POLITICAL ─────────────────────────────────────────────────
D4_QUESTION = (
    "What are the current positions of the key state actors, and are there "
    "meaningful signals of a change in the diplomatic trajectory?"
)
D4_KEY_JUDGMENT = (
    "The B-52H deployment to Diego Garcia and the Israeli security cabinet's "
    "deliberate strategic ambiguity following the Haifa strikes have not resolved "
    "the central question of whether Washington and Jerusalem are coordinating toward "
    "strikes on Iranian nuclear infrastructure — or whether these are coercive signals "
    "intended to induce Iranian restraint. The evidence does not yet distinguish "
    "between the two."
)
D4_CONFIDENCE = "MODERATE"
D4_CONF_COLOR = "#d68910"

D4_PARAS = [
    (
        "Israeli Prime Minister Netanyahu convened an emergency session of the security "
        "cabinet at 04:00 local time on 4 March following the overnight strikes on Haifa. "
        "Defence Minister Galant confirmed that four missiles had impacted Israeli territory "
        "and stated that Israel was 'evaluating options' — a formulation that neither "
        "commits to nor forecloses a counter-strike on Iranian territory (BBC Middle East, "
        "4 March). The Israeli security cabinet has employed this language with notable "
        "consistency across the past six weeks; the pattern suggests deliberate strategic "
        "ambiguity rather than genuine indecision, though the cumulative pressure of "
        "continued missile penetrations may alter the calculation over time."
    ),
    (
        "The Pentagon announced on 3 March the deployment of six B-52H Stratofortress "
        "aircraft to Diego Garcia in what it described as a 'routine deterrence patrol.' "
        "The timing — within hours of the Fordow access suspension — was noted by analysts "
        "across the Council on Foreign Relations, the Atlantic Council, and allied "
        "governments as unlikely to be coincidental (CFR Daily Brief, 4 March). The B-52H "
        "carries conventional munitions capable of striking hardened underground facilities, "
        "including the Massive Ordnance Penetrator, though whether those weapons are "
        "currently co-located with the aircraft at Diego Garcia has not been confirmed from "
        "open sources."
    ),
    (
        "At the United Nations, France and the United Kingdom circulated a draft resolution "
        "to the Security Council on 3 March calling for an immediate ceasefire and the "
        "restoration of IAEA access to all Iranian nuclear sites. Russia and China are "
        "expected to exercise their vetoes — as they have with the two preceding draft "
        "resolutions this year — leaving the international community without a multilateral "
        "mechanism for resolution. The diplomatic impasse reduces available options to "
        "unilateral or small-coalition actions, none of which Iran's leadership is likely "
        "to view as face-saving on the Fordow question."
    ),
    (
        "Iran's domestic political environment adds a complicating variable. Iran "
        "International and RFI Persian both reported on 3 March that the Supreme Leader's "
        "office had convened an expanded session of the Supreme National Security Council — "
        "a meeting not routinely disclosed — which is consistent with significant internal "
        "deliberation over the Fordow decision and its diplomatic consequences. Whether "
        "this deliberation reflects preparation for further escalation, a search for an "
        "off-ramp, or routine crisis management cannot be determined from available "
        "reporting."
    ),
]

D4_ACTOR_TABLE = {
    "caption": "ACTOR POSITIONS · 04 MARCH 2026",
    "headers": ["ACTOR", "CURRENT POSTURE", "CHANGE SINCE CYCLE 003", "ASSESSMENT"],
    "rows": [
        ["Iran (Tehran)",    "Suspended IAEA monitoring; IRGC missile campaign ongoing",  "Significant escalation", "Seeking domestic validation; testing Western red lines"],
        ["Israel (Cabinet)", "Evaluating options; strategic ambiguity maintained",         "Unchanged language, rising pressure", "Counter-strike planning likely accelerating"],
        ["United States",    "B-52H deployment to Diego Garcia; sanctions pressure",       "New deterrence signalling", "Signalling military option; not yet decided"],
        ["Russia",           "Blocking UNSC resolution; no direct military involvement",   "Unchanged",              "Preserving influence with Tehran; not a co-belligerent"],
        ["China",            "Blocking UNSC; maintaining commercial ties with Iran",       "Unchanged",              "Economic interest in stability; reluctant spoiler"],
        ["EU/France/UK",     "UNSC draft resolution; diplomatic pressure on Iran",         "Active but blocked",     "Diplomatically engaged; limited coercive capacity"],
        ["Saudi Arabia",     "Non-belligerent; oil supply management; private concern",    "Unchanged",              "Monitoring Hormuz risk; quietly relieved at Iran pressure"],
        ["UAE",              "Non-belligerent; Dubai markets under pressure",              "Slight deterioration",   "Vulnerable to spillover; seeking private diplomatic role"],
    ],
}

# ── D5 CYBER / IO ─────────────────────────────────────────────────────────────
D5_QUESTION = (
    "What Iranian or proxy-affiliated cyber and information operations were active "
    "in the 24 hours to 06:00 UTC, 4 March, and what do the patterns suggest "
    "about Tehran's broader intent?"
)
D5_KEY_JUDGMENT = (
    "Iranian cyber operations targeting North American and European critical "
    "infrastructure — running concurrently with APT35's credential-harvesting "
    "campaign against Israeli banking and telecoms — are consistent with a "
    "strategy of raising the cost of Western involvement through infrastructure "
    "disruption risk rather than seeking immediate operational effect."
)
D5_CONFIDENCE = "MODERATE"
D5_CONF_COLOR = "#d68910"

D5_PARAS = [
    (
        "CISA published Advisory AA26-063A on 3 March attributing active exploitation "
        "of Unitronics programmable logic controller vulnerabilities (CVE-2023-6448) to "
        "IRGC-affiliated actors designated 'Volt Sparrow.' The targets include water and "
        "wastewater treatment facilities and energy-sector operational technology networks "
        "in the United States, Canada, and several European countries. CISA assessed the "
        "campaign as ongoing and recommended immediate patching and network segmentation "
        "(CISA AA26-063A, 3 March). The vulnerability was first publicly disclosed in "
        "late 2023 following a series of Iranian-linked attacks on Israeli-manufactured "
        "control systems in US municipal water facilities — a pattern now apparently "
        "being extended in scope."
    ),
    (
        "Recorded Future's Insikt Group separately identified new command-and-control "
        "infrastructure associated with APT35 — widely attributed to Iran's Ministry of "
        "Intelligence and Security — targeting Israeli banking and telecommunications "
        "companies through spear-phishing correspondence impersonating Bank Leumi "
        "communications. The malware identified is an updated HYPERSCRAPE variant with "
        "credential-harvesting and persistent-access capabilities (Recorded Future, "
        "3 March). The architecture of the campaign — establishing persistent access "
        "rather than triggering immediate disruption — is consistent with pre-positioning "
        "for a future disruptive operation timed to coincide with a moment of maximum "
        "Israeli vulnerability."
    ),
    (
        "On the information operations side, the IRGC Aerospace Force published a Telegram "
        "statement claiming that all 18 missiles in the overnight Haifa salvo reached their "
        "designated targets — a claim directly contradicted by Israeli military statements "
        "and inconsistent with observed damage patterns. Iran International assessed the "
        "statement as likely produced for domestic consumption to sustain public support "
        "for the conflict rather than as a serious factual claim (Iran International, "
        "4 March). The gap between operational reality and public framing in Iranian state "
        "communications has widened consistently over the past eight weeks, suggesting "
        "that domestic legitimacy maintenance has become an increasingly significant "
        "driver of the IRGC's communications strategy."
    ),
    (
        "Separately, NetBlocks reported on 4 March that Iranian internet connectivity "
        "stood at 61 per cent of baseline — a level consistent with partial throttling "
        "rather than a full blackout, and down from 78 per cent recorded at the start "
        "of the current cycle. The reduction is likely related to infrastructure damage "
        "from earlier strikes on communications relay stations in the Tehran region, "
        "though deliberate domestic restriction by Iranian authorities cannot be excluded "
        "as a complementary explanation (NetBlocks, 4 March)."
    ),
]

D5_INCIDENT_TABLE = {
    "caption": "CYBER / IO INCIDENTS · 03–04 MARCH 2026",
    "headers": ["INCIDENT", "ACTOR", "TARGET", "VECTOR", "STATUS", "SOURCE"],
    "rows": [
        ["Unitronics PLC exploitation",    "Volt Sparrow (IRGC-affiliate)", "NA/EU water, energy OT", "CVE-2023-6448",              "ACTIVE",    "CISA AA26-063A T3"],
        ["APT35 Bank Leumi phishing",      "APT35 / MOIS",                  "Israeli banking/telecoms",  "Spear-phish → HYPERSCRAPE", "ACTIVE",    "Recorded Future T3"],
        ["IRGC Telegram IO campaign",      "IRGC Aerospace Force",          "Iranian domestic audience", "State Telegram channel",    "ONGOING",   "Iran International T2"],
        ["IR internet throttling",         "Gov / infrastructure damage",   "Iranian population",        "ISP-level restriction",     "61% baseline", "NetBlocks T3"],
        ["GPS/AIS spoofing — Gulf",        "Unknown (IRGC-consistent)",     "Gulf shipping",             "GNSS jamming",              "CONTINUING", "UKMTO / MarineTraffic T2"],
    ],
}

# ── 72-HOUR OUTLOOK ───────────────────────────────────────────────────────────
OUTLOOK_TABLE = {
    "caption": "72-HOUR OUTLOOK · TO 07 MARCH 2026",
    "headers": ["SCENARIO", "PROBABILITY", "PRINCIPAL INDICATOR", "ASSESSMENT"],
    "rows": [
        [
            "Israeli counter-strike on IRGC missile infrastructure inside Iran",
            "40–55%",
            "Israeli cabinet breaks strategic ambiguity; US green-light signals",
            "The penetration rate from the Haifa salvo has materially increased the "
            "pressure to act. A strike within 72 hours would be premature by historical "
            "Israeli patterns, but not outside precedent.",
        ],
        [
            "Continuation of current exchange rhythm — salvo and counter-intercept — "
            "without escalation to strikes on Iranian territory",
            "35–45%",
            "No Israeli cabinet announcement; IRGC does not repeat salvo size",
            "The most likely path if both sides are managing the pace of escalation. "
            "Houthi maritime operations continue regardless.",
        ],
        [
            "Iranian attempt to close or restrict Hormuz passage in response to "
            "Israeli or US military action",
            "10–20%",
            "Trigger: Israeli or US strike inside Iranian territory",
            "Iran has historically treated Hormuz closure as an extreme measure "
            "with severe economic self-harm. It remains a genuine option under "
            "sufficient pressure. Probability rises sharply if strikes occur.",
        ],
    ],
}

# ── WARNING INDICATORS ────────────────────────────────────────────────────────
WARNING_INDICATORS = [
    {
        "id": "WI-01",
        "indicator": "Israeli security cabinet formally authorises strikes on Iranian territory",
        "domain": "D1",
        "status": "WATCHING",
        "status_color": "#d68910",
        "change": "ELEVATED",
        "detail": "Cabinet using 'evaluating options' language. Pressure increasing after Haifa penetrations.",
    },
    {
        "id": "WI-02",
        "indicator": "Iran restores IAEA access to Fordow",
        "domain": "D2",
        "status": "NOT TRIGGERED",
        "status_color": "#5a7a8a",
        "change": "NEW (inverted tripwire)",
        "detail": "Restoration would signal diplomatic off-ramp. Absence sustains escalatory pressure.",
    },
    {
        "id": "WI-03",
        "indicator": "IRGC Navy physically impedes commercial traffic in Strait of Hormuz",
        "domain": "D3",
        "status": "WATCHING",
        "status_color": "#d68910",
        "change": "ELEVATED",
        "detail": "Patrol activity up; no interdiction yet. Probability rises materially on Israeli/US strikes.",
    },
    {
        "id": "WI-04",
        "indicator": "US confirms B-52H weapons manifest includes Massive Ordnance Penetrator",
        "domain": "D4",
        "status": "WATCHING",
        "status_color": "#d68910",
        "change": "NEW",
        "detail": "Confirmation would shift Diego Garcia deployment from signalling to preparation.",
    },
    {
        "id": "WI-05",
        "indicator": "CISA elevates critical infrastructure alert to Emergency Directive",
        "domain": "D5",
        "status": "WATCHING",
        "status_color": "#d68910",
        "change": "NEW",
        "detail": "Current advisory (AA26-063A) is non-binding. Emergency Directive would indicate active compromise of US systems.",
    },
    {
        "id": "WI-06",
        "indicator": "Iran internet connectivity drops below 30% (full blackout threshold)",
        "domain": "D5",
        "status": "WATCHING",
        "status_color": "#d68910",
        "change": "ELEVATED",
        "detail": "Currently at 61%. Full blackout historically precedes or accompanies significant domestic events.",
    },
]

# ── COLLECTION GAPS ───────────────────────────────────────────────────────────
COLLECTION_GAPS = [
    {
        "id": "CG-01",
        "domain": "D2",
        "severity": "CRITICAL",
        "sev_color": "#c0392b",
        "gap": "Real-time visibility into Fordow enrichment activities following IAEA monitoring disconnection.",
        "significance": (
            "Without inspector access or functioning monitoring equipment, it is not "
            "possible to determine whether Iran has initiated an accelerated enrichment "
            "cycle. This gap cannot be remedied from open sources."
        ),
    },
    {
        "id": "CG-02",
        "domain": "D1",
        "severity": "SIGNIFICANT",
        "sev_color": "#d68910",
        "gap": "Israeli cabinet deliberations and any formal authorisation of retaliatory strikes.",
        "significance": (
            "The Israeli security cabinet is meeting in restricted session. Open-source "
            "reporting captures only statements released after decisions are made."
        ),
    },
    {
        "id": "CG-03",
        "domain": "D3",
        "severity": "SIGNIFICANT",
        "sev_color": "#d68910",
        "gap": "Hormuz vessel traffic data disaggregated by flag state and cargo type.",
        "significance": (
            "UKMTO and MarineTraffic provide incident reports but not aggregate throughput "
            "statistics in near real-time. The extent of voluntary traffic diversion versus "
            "forced rerouting is unclear."
        ),
    },
    {
        "id": "CG-04",
        "domain": "D4",
        "severity": "SIGNIFICANT",
        "sev_color": "#d68910",
        "gap": "Content and outcome of the Supreme National Security Council session reported on 3 March.",
        "significance": (
            "The expanded SNSC session was not officially disclosed by Iran. Its agenda "
            "and any decisions taken are unknown from open sources."
        ),
    },
    {
        "id": "CG-05",
        "domain": "D5",
        "severity": "MINOR",
        "sev_color": "#5a7a8a",
        "gap": "Attribution confidence for GPS/AIS spoofing events in the Gulf.",
        "significance": (
            "UKMTO and MarineTraffic have recorded consistent spoofing events but "
            "technical attribution to IRGC versus Houthi-aligned actors remains unclear."
        ),
    },
]

# ── SOURCE REGISTRY ───────────────────────────────────────────────────────────
SOURCES_USED = [
    ("CTP-ISW Evening Report (3 Mar)",     "T1", "D1, D2"),
    ("CTP-ISW Morning Report (4 Mar)",     "T1", "D1"),
    ("CENTCOM Press Release (4 Mar)",      "T1", "D1, D3"),
    ("UKMTO WARNO 042/2026 (4 Mar)",       "T1", "D1, D3"),
    ("IDF Spokesperson (4 Mar)",           "T1", "D1"),
    ("IAEA Board Notification (4 Mar)",    "T1", "D2"),
    ("Reuters (4 Mar)",                    "T1", "D1, D4"),
    ("ICG Analysis (4 Mar)",               "T2", "D2, D4"),
    ("CFR Daily Brief (4 Mar)",            "T2", "D4"),
    ("BBC Middle East (4 Mar)",            "T2", "D4"),
    ("Goldman Sachs Energy Desk (3 Mar)",  "T2", "D3"),
    ("IEA Statement (3 Mar)",              "T2", "D3"),
    ("Iran International (4 Mar)",         "T2", "D1, D5"),
    ("NetBlocks (4 Mar)",                  "T3", "D5"),
    ("CISA AA26-063A (3 Mar)",             "T3", "D5"),
    ("Recorded Future Insikt Group (3 Mar)","T3","D5"),
    ("Lloyd's Market Association (3 Mar)", "T2", "D3"),
    ("Kpler Estimate (3 Mar)",             "T2", "D3"),
    ("Bank of Canada FSR (3 Mar)",         "T2", "D3"),
]

CAVEATS_TEXT = (
    "This brief is produced manually by the CSE Conflict Assessment Unit from open-source "
    "reporting. It is not a signals intelligence or classified product. Tier 1 sources "
    "(AP, Reuters, CTP-ISW, CENTCOM, IAEA, UKMTO, IDF Spokesperson) constitute the "
    "factual floor; claims appearing only in Tier 2 or Tier 3 sources are identified as "
    "reported or assessed rather than confirmed. Iranian state media (PressTV, IRNA, Mehr, "
    "Fars, Tasnim) are not used as independent evidence; where referenced, their content "
    "is attributed explicitly as Iranian government assertion. Confidence designations "
    "(HIGH / MODERATE / LOW) reflect corroboration depth and source tier, not certainty. "
    "This document is intended for internal analytical use only."
)


# ═══════════════════════════════════════════════════════════════════════════════
# HTML/VML GENERATOR — do not edit below this line
# ═══════════════════════════════════════════════════════════════════════════════

def _esc(s: str) -> str:
    """Escape HTML special characters."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _cell(content: str, bg: str = "#141820", fg: str = "#dde6f0",
          pad: int = 8, bold: bool = False, font: str = "Trebuchet MS, Arial, sans-serif",
          size: str = "10pt", align: str = "left", valign: str = "top",
          colspan: int = 1) -> str:
    b_open  = "<b>" if bold else ""
    b_close = "</b>" if bold else ""
    cs = f' colspan="{colspan}"' if colspan > 1 else ""
    return (
        f'<td bgcolor="{bg}" valign="{valign}" align="{align}"{cs} '
        f'style="padding:{pad}px;font-family:{font};font-size:{size};color:{fg};">'
        f'{b_open}{content}{b_close}</td>'
    )


def _divider(color: str = "#1e2d3d", height: int = 1) -> str:
    return (
        f'<table width="100%" cellspacing="0" cellpadding="0" border="0">'
        f'<tr><td bgcolor="{color}" height="{height}" style="font-size:1px;line-height:1px;">&nbsp;</td></tr>'
        f'</table>'
    )


def _spacer(h: int = 8) -> str:
    return (
        f'<table width="100%" cellspacing="0" cellpadding="0" border="0">'
        f'<tr><td bgcolor="#0d0f14" height="{h}" style="font-size:1px;line-height:1px;">&nbsp;</td></tr>'
        f'</table>'
    )


def _section_header(num: str, title: str, question: str,
                    kj_text: str, confidence: str, conf_color: str,
                    accent_bg: str) -> str:
    """Colored domain section header with number, title, question bar, and key judgment."""
    return f"""
{_spacer(12)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="{accent_bg}" style="padding:10px 12px;">
      <table width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td bgcolor="{accent_bg}" style="font-family:Courier New,monospace;font-size:11pt;color:#dde6f0;font-weight:bold;">
            <b>{_esc(num)} &nbsp; {_esc(title)}</b>
          </td>
          <td bgcolor="{accent_bg}" align="right" style="font-family:Courier New,monospace;font-size:9pt;font-weight:bold;color:{conf_color};">
            <b>{_esc(confidence)}&nbsp;CONFIDENCE</b>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td bgcolor="#0a1520" style="padding:7px 12px;font-family:Trebuchet MS,Arial,sans-serif;font-size:9pt;color:#5a7a8a;font-style:italic;">
      {_esc(question)}
    </td>
  </tr>
  <tr>
    <td bgcolor="#0d1625" style="padding:10px 12px;border-left:3px solid #00d4ff;">
      <span style="font-family:Trebuchet MS,Arial,sans-serif;font-size:10pt;color:#00d4ff;font-weight:bold;">
        KEY JUDGMENT &nbsp;&#9656;&nbsp;
      </span>
      <span style="font-family:Trebuchet MS,Arial,sans-serif;font-size:10pt;color:#dde6f0;">
        {_esc(kj_text)}
      </span>
    </td>
  </tr>
</table>
{_divider("#1e2d3d")}
"""


def _prose_para(text: str) -> str:
    return f"""<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#141820" style="padding:9px 16px;font-family:Trebuchet MS,Arial,sans-serif;font-size:10pt;color:#dde6f0;line-height:1.55;">
      {_esc(text)}
    </td>
  </tr>
</table>
{_divider("#1a2030", 1)}"""


def _data_table(table_def: dict, accent_color: str = "#1a4a5a") -> str:
    caption  = table_def["caption"]
    headers  = table_def["headers"]
    rows     = table_def["rows"]
    col_w    = f"{100 // len(headers)}%"

    hdr_cells = "".join(
        f'<td bgcolor="{accent_color}" style="padding:6px 8px;font-family:Courier New,monospace;'
        f'font-size:8pt;color:#00d4ff;font-weight:bold;white-space:nowrap;">'
        f'<b>{_esc(h)}</b></td>'
        for h in headers
    )

    row_html = ""
    for i, row in enumerate(rows):
        bg = "#141820" if i % 2 == 0 else "#111620"
        cells = "".join(
            f'<td bgcolor="{bg}" style="padding:5px 8px;font-family:Trebuchet MS,Arial,sans-serif;'
            f'font-size:9pt;color:#dde6f0;vertical-align:top;">{_esc(str(v))}</td>'
            for v in row
        )
        row_html += f"<tr>{cells}</tr>\n"

    return f"""
{_spacer(6)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#0a1520" style="padding:5px 12px;font-family:Courier New,monospace;font-size:8pt;color:#5a7a8a;letter-spacing:1px;">
      {_esc(caption)}
    </td>
  </tr>
</table>
<table width="100%" cellspacing="1" cellpadding="0" border="0" bgcolor="#1e2d3d">
  <tr>{hdr_cells}</tr>
  {row_html}
</table>
{_spacer(6)}"""


def build_document() -> str:
    parts = []

    # ── DOCTYPE + HEAD ─────────────────────────────────────────────────────────
    parts.append(f"""<!DOCTYPE html>
<html xmlns:v="urn:schemas-microsoft-com:vml"
      xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8">
<meta name="Generator" content="CSE Intelligence Brief Generator">
<xml>
  <o:DocumentProperties>
    <o:Company>CSE Conflict Assessment Unit</o:Company>
    <o:Category>Intelligence Brief</o:Category>
  </o:DocumentProperties>
  <w:WordDocument>
    <w:DisplayBackgroundShape/>
    <w:View>Print</w:View>
    <w:Zoom>90</w:Zoom>
    <w:DoNotOptimizeForBrowser/>
  </w:WordDocument>
</xml>
<style>
  v\\:* {{ behavior: url(#default#VML); display: inline-block; }}
  o\\:* {{ behavior: url(#default#VML); display: inline-block; }}

  @page Section1 {{
    size: 8.5in 11in;
    margin: 0.45in 0.55in 0.45in 0.55in;
    mso-header-margin: 0.25in;
    mso-footer-margin: 0.25in;
  }}

  body {{
    font-family: 'Trebuchet MS', Arial, sans-serif;
    font-size: 10pt;
    color: #dde6f0;
    background-color: #0d0f14;
    mso-div-section: Section1;
    margin: 0;
    padding: 0;
  }}

  table {{
    border-collapse: collapse;
    mso-table-layout-alt: fixed;
    width: 100%;
  }}

  p {{ margin: 0; padding: 0; }}
</style>
</head>
<body>
""")

    # ── VML PAGE BACKGROUND ────────────────────────────────────────────────────
    parts.append("""<o:background fillcolor="#0d0f14">
  <v:fill type="solid" color="#0d0f14"/>
</o:background>
""")

    # ── TOP CLASSIFICATION BAR ─────────────────────────────────────────────────
    parts.append(f"""<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#7b0000" align="center" style="padding:5px 0;">
      <b style="font-family:Courier New,monospace;font-size:9pt;color:#ffffff;letter-spacing:3px;">
        {_esc(CLASSIFICATION)} &nbsp;&#47;&#47;&nbsp; {_esc(TLP)} &nbsp;&#47;&#47;&nbsp; NOT FOR FURTHER DISTRIBUTION
      </b>
    </td>
  </tr>
</table>
""")

    # ── VML GRADIENT HEADER ────────────────────────────────────────────────────
    parts.append(f"""<v:rect style="width:100%;height:130pt;display:block;" filled="t" stroked="f">
  <v:fill type="gradient" color="#0d0f14" color2="#091a28" focus="100%" angle="90"/>
  <v:textbox style="mso-fit-shape-to-text:t;" inset="0,0,0,0">
    <table width="100%" cellspacing="0" cellpadding="0" border="0">
      <tr>
        <td style="padding:20px 18px 4px 18px;">
          <table width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="font-family:Courier New,monospace;font-size:9pt;color:#5a7a8a;letter-spacing:2px;">
                {_esc(ANALYST_UNIT.upper())} &nbsp;&#47;&#47;&nbsp; {_esc(REGION)}
              </td>
              <td align="right" style="font-family:Courier New,monospace;font-size:9pt;color:#5a7a8a;">
                CYCLE {_esc(CYCLE_NUM)} &nbsp;&#47;&#47;&nbsp; {_esc(CONFLICT_DAY)}
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:0 18px 6px 18px;">
          <span style="font-family:Courier New,monospace;font-size:22pt;color:#dde6f0;font-weight:bold;letter-spacing:2px;">
            <b>CSE INTELLIGENCE BRIEF</b>
          </span>
        </td>
      </tr>
      <tr>
        <td style="padding:0 18px 4px 18px;">
          <span style="font-family:Trebuchet MS,Arial,sans-serif;font-size:11pt;color:#00d4ff;">
            Iran War File &nbsp;&#8212;&nbsp; Daily Conflict Assessment
          </span>
        </td>
      </tr>
      <tr>
        <td style="padding:0 18px 14px 18px;">
          <table width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td style="font-family:Courier New,monospace;font-size:9pt;color:#5a7a8a;">
                {_esc(TIMESTAMP_UTC)} &nbsp;&#47;&#47;&nbsp; {_esc(CLASSIFICATION)} &nbsp;&#47;&#47;&nbsp; {_esc(TLP)}
              </td>
              <td align="right" style="font-family:Courier New,monospace;font-size:9pt;color:#c0392b;font-weight:bold;">
                <b>THREAT LEVEL: {_esc(THREAT_LEVEL)}</b>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </v:textbox>
</v:rect>
""")

    # ── THREAT STATUS STRIP ────────────────────────────────────────────────────
    cell_w = f"{100 // len(STATUS_CELLS)}%"
    status_cells = "".join(
        f'<td bgcolor="#141820" align="center" width="{cell_w}" style="padding:8px 4px;border-right:1px solid #1e2d3d;">'
        f'<div style="font-family:Courier New,monospace;font-size:11pt;color:{color};font-weight:bold;"><b>{_esc(val)}</b></div>'
        f'<div style="font-family:Courier New,monospace;font-size:7pt;color:#5a7a8a;letter-spacing:1px;margin-top:3px;">{_esc(lbl)}</div>'
        f'</td>'
        for lbl, val, color in STATUS_CELLS
    )
    parts.append(f"""<table width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#1e2d3d">
  <tr>{status_cells}</tr>
</table>
{_divider("#00d4ff", 2)}
""")

    # ── EXECUTIVE SUMMARY ──────────────────────────────────────────────────────
    parts.append(f"""{_spacer(10)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#0d0f14" style="padding:4px 12px 8px 12px;">
      <span style="font-family:Courier New,monospace;font-size:10pt;color:#00d4ff;font-weight:bold;letter-spacing:2px;">
        <b>EXECUTIVE SUMMARY</b>
      </span>
    </td>
  </tr>
</table>
""")
    for para in EXECUTIVE_PARAS:
        parts.append(_prose_para(para))
    parts.append(_spacer(8))

    # ── KEY JUDGMENTS TABLE ────────────────────────────────────────────────────
    parts.append(f"""<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#0d0f14" style="padding:4px 12px 8px 12px;">
      <span style="font-family:Courier New,monospace;font-size:10pt;color:#00d4ff;font-weight:bold;letter-spacing:2px;">
        <b>KEY JUDGMENTS</b>
      </span>
    </td>
  </tr>
</table>
<table width="100%" cellspacing="1" cellpadding="0" border="0" bgcolor="#1e2d3d">
  <tr>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:50px;"><b>REF</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:40px;"><b>DOM</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:70px;"><b>CONFIDENCE</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;"><b>JUDGMENT</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:160px;"><b>BASIS</b></td>
  </tr>
""")
    for i, kj in enumerate(KEY_JUDGMENTS):
        bg = "#141820" if i % 2 == 0 else "#111620"
        parts.append(
            f'  <tr>'
            f'<td bgcolor="{bg}" style="padding:7px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;white-space:nowrap;"><b>{_esc(kj["num"])}</b></td>'
            f'<td bgcolor="{bg}" style="padding:7px 8px;font-family:Courier New,monospace;font-size:8pt;color:#5a7a8a;">{_esc(kj["domain"])}</td>'
            f'<td bgcolor="{bg}" style="padding:7px 8px;font-family:Courier New,monospace;font-size:8pt;color:{kj["conf_color"]};font-weight:bold;"><b>{_esc(kj["confidence"])}</b></td>'
            f'<td bgcolor="{bg}" style="padding:7px 8px;font-family:Trebuchet MS,Arial,sans-serif;font-size:9pt;color:#dde6f0;">{_esc(kj["text"])}</td>'
            f'<td bgcolor="{bg}" style="padding:7px 8px;font-family:Trebuchet MS,Arial,sans-serif;font-size:8pt;color:#5a7a8a;font-style:italic;">{_esc(kj["basis"])}</td>'
            f'</tr>\n'
        )
    parts.append("</table>\n")
    parts.append(_divider("#00d4ff", 2))

    # ── D1 BATTLESPACE ─────────────────────────────────────────────────────────
    parts.append(_section_header(
        "01", "BATTLESPACE", D1_QUESTION, D1_KEY_JUDGMENT,
        D1_CONFIDENCE, D1_CONF_COLOR, "#3d0a0a"
    ))
    for para in D1_PARAS:
        parts.append(_prose_para(para))
    parts.append(_data_table(D1_OPS_TABLE, "#2d0a0a"))

    # ── D2 NUCLEAR ─────────────────────────────────────────────────────────────
    parts.append(_section_header(
        "02", "NUCLEAR · ESCALATION", D2_QUESTION, D2_KEY_JUDGMENT,
        D2_CONFIDENCE, D2_CONF_COLOR, "#1a0a3d"
    ))
    for para in D2_PARAS:
        parts.append(_prose_para(para))

    # ── D3 ENERGY / ECONOMIC ───────────────────────────────────────────────────
    parts.append(_section_header(
        "03", "ENERGY · ECONOMIC", D3_QUESTION, D3_KEY_JUDGMENT,
        D3_CONFIDENCE, D3_CONF_COLOR, "#0a1e3d"
    ))
    for para in D3_PARAS:
        parts.append(_prose_para(para))
    parts.append(_data_table(D3_MARKET_TABLE, "#0a1e3d"))

    # ── D4 DIPLOMATIC ──────────────────────────────────────────────────────────
    parts.append(_section_header(
        "04", "DIPLOMATIC · POLITICAL", D4_QUESTION, D4_KEY_JUDGMENT,
        D4_CONFIDENCE, D4_CONF_COLOR, "#0a2d1a"
    ))
    for para in D4_PARAS:
        parts.append(_prose_para(para))
    parts.append(_data_table(D4_ACTOR_TABLE, "#0a2d1a"))

    # ── D5 CYBER / IO ──────────────────────────────────────────────────────────
    parts.append(_section_header(
        "05", "CYBER · INFORMATION OPERATIONS", D5_QUESTION, D5_KEY_JUDGMENT,
        D5_CONFIDENCE, D5_CONF_COLOR, "#0a2d35"
    ))
    for para in D5_PARAS:
        parts.append(_prose_para(para))
    parts.append(_data_table(D5_INCIDENT_TABLE, "#0a2d35"))

    # ── 72-HOUR OUTLOOK ────────────────────────────────────────────────────────
    parts.append(_divider("#00d4ff", 2))
    parts.append(f"""{_spacer(10)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#0d0f14" style="padding:4px 12px 8px 12px;">
      <span style="font-family:Courier New,monospace;font-size:10pt;color:#00d4ff;font-weight:bold;letter-spacing:2px;">
        <b>72-HOUR OUTLOOK</b>
      </span>
    </td>
  </tr>
</table>
""")
    parts.append(_data_table(OUTLOOK_TABLE, "#1a2d3a"))

    # ── WARNING INDICATORS ─────────────────────────────────────────────────────
    parts.append(f"""{_spacer(8)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#0d0f14" style="padding:4px 12px 8px 12px;">
      <span style="font-family:Courier New,monospace;font-size:10pt;color:#00d4ff;font-weight:bold;letter-spacing:2px;">
        <b>WARNING INDICATORS</b>
      </span>
    </td>
  </tr>
</table>
<table width="100%" cellspacing="1" cellpadding="0" border="0" bgcolor="#1e2d3d">
  <tr>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:55px;"><b>ID</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:40px;"><b>DOM</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;"><b>INDICATOR</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:110px;"><b>STATUS</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:80px;"><b>CHANGE</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:200px;"><b>DETAIL</b></td>
  </tr>
""")
    for i, wi in enumerate(WARNING_INDICATORS):
        bg = "#141820" if i % 2 == 0 else "#111620"
        parts.append(
            f'  <tr>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;"><b>{_esc(wi["id"])}</b></td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#5a7a8a;">{_esc(wi["domain"])}</td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Trebuchet MS,Arial,sans-serif;font-size:9pt;color:#dde6f0;">{_esc(wi["indicator"])}</td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:{wi["status_color"]};font-weight:bold;"><b>{_esc(wi["status"])}</b></td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#d68910;">{_esc(wi["change"])}</td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Trebuchet MS,Arial,sans-serif;font-size:8pt;color:#5a7a8a;font-style:italic;">{_esc(wi["detail"])}</td>'
            f'</tr>\n'
        )
    parts.append("</table>\n")

    # ── COLLECTION GAPS ────────────────────────────────────────────────────────
    parts.append(f"""{_spacer(8)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#0d0f14" style="padding:4px 12px 8px 12px;">
      <span style="font-family:Courier New,monospace;font-size:10pt;color:#00d4ff;font-weight:bold;letter-spacing:2px;">
        <b>COLLECTION GAPS</b>
      </span>
    </td>
  </tr>
</table>
<table width="100%" cellspacing="1" cellpadding="0" border="0" bgcolor="#1e2d3d">
  <tr>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:55px;"><b>ID</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:40px;"><b>DOM</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:70px;"><b>SEVERITY</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;"><b>GAP</b></td>
    <td bgcolor="#1a4a5a" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;"><b>SIGNIFICANCE</b></td>
  </tr>
""")
    for i, cg in enumerate(COLLECTION_GAPS):
        bg = "#141820" if i % 2 == 0 else "#111620"
        parts.append(
            f'  <tr>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;"><b>{_esc(cg["id"])}</b></td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:#5a7a8a;">{_esc(cg["domain"])}</td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Courier New,monospace;font-size:8pt;color:{cg["sev_color"]};font-weight:bold;"><b>{_esc(cg["severity"])}</b></td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Trebuchet MS,Arial,sans-serif;font-size:9pt;color:#dde6f0;">{_esc(cg["gap"])}</td>'
            f'<td bgcolor="{bg}" style="padding:6px 8px;font-family:Trebuchet MS,Arial,sans-serif;font-size:9pt;color:#5a7a8a;font-style:italic;">{_esc(cg["significance"])}</td>'
            f'</tr>\n'
        )
    parts.append("</table>\n")

    # ── SOURCE REGISTRY ────────────────────────────────────────────────────────
    parts.append(f"""{_spacer(8)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#0d0f14" style="padding:4px 12px 8px 12px;">
      <span style="font-family:Courier New,monospace;font-size:10pt;color:#00d4ff;font-weight:bold;letter-spacing:2px;">
        <b>SOURCES CONSULTED THIS CYCLE</b>
      </span>
    </td>
  </tr>
</table>
<table width="100%" cellspacing="1" cellpadding="0" border="0" bgcolor="#1e2d3d">
  <tr>
    <td bgcolor="#1a4a5a" style="padding:5px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;"><b>SOURCE</b></td>
    <td bgcolor="#1a4a5a" style="padding:5px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:40px;"><b>TIER</b></td>
    <td bgcolor="#1a4a5a" style="padding:5px 8px;font-family:Courier New,monospace;font-size:8pt;color:#00d4ff;font-weight:bold;width:80px;"><b>DOMAINS</b></td>
  </tr>
""")
    for i, (src, tier, doms) in enumerate(SOURCES_USED):
        bg = "#141820" if i % 2 == 0 else "#111620"
        t_color = "#1e8449" if tier == "T1" else ("#d68910" if tier == "T2" else "#5a7a8a")
        parts.append(
            f'  <tr>'
            f'<td bgcolor="{bg}" style="padding:5px 8px;font-family:Trebuchet MS,Arial,sans-serif;font-size:9pt;color:#dde6f0;">{_esc(src)}</td>'
            f'<td bgcolor="{bg}" style="padding:5px 8px;font-family:Courier New,monospace;font-size:8pt;color:{t_color};font-weight:bold;"><b>{_esc(tier)}</b></td>'
            f'<td bgcolor="{bg}" style="padding:5px 8px;font-family:Courier New,monospace;font-size:8pt;color:#5a7a8a;">{_esc(doms)}</td>'
            f'</tr>\n'
        )
    parts.append("</table>\n")

    # ── CAVEATS ────────────────────────────────────────────────────────────────
    parts.append(f"""{_spacer(8)}
<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#141820" style="padding:10px 14px;border-left:3px solid #5a7a8a;">
      <span style="font-family:Courier New,monospace;font-size:8pt;color:#5a7a8a;font-weight:bold;letter-spacing:1px;">
        <b>METHODOLOGY &amp; CAVEATS</b>
      </span><br/>
      <span style="font-family:Trebuchet MS,Arial,sans-serif;font-size:9pt;color:#5a7a8a;font-style:italic;">
        {_esc(CAVEATS_TEXT)}
      </span>
    </td>
  </tr>
</table>
{_spacer(10)}
""")

    # ── FOOTER CLASSIFICATION BAR ──────────────────────────────────────────────
    parts.append(f"""<table width="100%" cellspacing="0" cellpadding="0" border="0">
  <tr>
    <td bgcolor="#7b0000" style="padding:4px 0;">
      <table width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td bgcolor="#7b0000" align="center" style="font-family:Courier New,monospace;font-size:9pt;color:#ffffff;letter-spacing:2px;">
            <b>{_esc(CLASSIFICATION)} &nbsp;&#47;&#47;&nbsp; {_esc(TLP)}</b>
          </td>
        </tr>
        <tr>
          <td bgcolor="#7b0000" align="center" style="font-family:Courier New,monospace;font-size:8pt;color:#cc8888;padding-bottom:4px;">
            {_esc(CYCLE_ID)} &nbsp;&#47;&#47;&nbsp; {_esc(TIMESTAMP_UTC)} &nbsp;&#47;&#47;&nbsp; {_esc(ANALYST_UNIT)}
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
""")

    parts.append("</body>\n</html>")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate CSE Intelligence Brief (.doc)")
    parser.add_argument("--date", default=None, help="Date string for filename (YYYYMMDD)")
    args = parser.parse_args()

    date_str = args.date or datetime.date.today().strftime("%Y%m%d")
    out_dir  = os.path.join(os.path.dirname(__file__), "briefs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"CSE_Intel_Brief_{date_str}.doc")

    html = build_document()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"Written: {out_path}  ({size_kb:.1f} KB)")
    print(f"Open in Microsoft Word or LibreOffice Writer.")


if __name__ == "__main__":
    main()
