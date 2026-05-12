"""Static reference data we curate ourselves.

gzwtacmap.com renders the dynamic stuff (tasks/keys/places). For traders and
factions we keep a hand-curated dossier so the bot still has rich answers
even when the scraper has nothing yet, and so we can add lore the website
doesn't expose.
"""
from __future__ import annotations

TRADERS: list[dict] = [
    {
        "name": "Handshake",
        "callsign": "Lewis Pell",
        "role": "Operations / Public liaison",
        "faction": "PMC (any)",
        "bio": (
            "Manages the region's operations, public image, and the dirty hands-on tasks. "
            "First contact for new operators arriving on Lamang."
        ),
        "specialties": ["Tier-1 ops", "Public image", "Hostile Group Intel"],
    },
    {
        "name": "Gunny",
        "callsign": "Anton Jackson",
        "role": "Quartermaster",
        "faction": "PMC (any)",
        "bio": "Former USMC. Quartermaster — ammunition, guns, basic gear. Knows the quartermaster's pain.",
        "specialties": ["Weapons", "Ammo crates", "Loadouts"],
    },
    {
        "name": "Lab Rat",
        "callsign": "Jie",
        "role": "Medical / Bio-research",
        "faction": "PMC (any)",
        "bio": "Friendly at first; will drag you into UNLRA medical-supply runs that turn into bio-hazard ops fast.",
        "specialties": ["Medkits", "Pharmaceuticals", "UNLRA contracts"],
    },
    {
        "name": "Artisan",
        "callsign": "Laya Hoang",
        "role": "Mechanic / Engineer",
        "faction": "PMC (any)",
        "bio": "Knows everything about machines and the way they break. Modding, repairs, vehicle parts.",
        "specialties": ["Mods", "Tools", "Mechanical parts"],
    },
    {
        "name": "Banshee",
        "callsign": "—",
        "role": "Survival / Black market",
        "faction": "PMC (any)",
        "bio": "Resourceful — has all the goods you actually need to survive. Backchannel supplier.",
        "specialties": ["Survival kit", "Rare items", "Off-book trades"],
    },
]


FACTIONS: list[dict] = [
    # ---- PMCs (playable) ----
    {
        "name": "Lamang Recovery Initiative (LRI)",
        "type": "pmc",
        "hq": "LRI Base — northwest Lamang",
        "aor": "Across Lamang",
        "threat": "—",
        "bio": "Humanitarian-leaning PMC focused on recovery and stabilization operations.",
    },
    {
        "name": "Mithras Security Systems",
        "type": "pmc",
        "hq": "Mithras Base — southeast Lamang",
        "aor": "Across Lamang",
        "threat": "—",
        "bio": "Corporate-focused security firm; assets and intelligence specialists.",
    },
    {
        "name": "Crimson Shield International (CSI)",
        "type": "pmc",
        "hq": "CSI Base — central Lamang",
        "aor": "Across Lamang",
        "threat": "—",
        "bio": "Hard-line PMC, kinetic operations and high-risk extractions.",
    },
    # ---- Hostile groups ----
    {
        "name": "Lotus Circle",
        "type": "hostile",
        "hq": "Hunter's Paradise",
        "aor": "Hunter's Paradise + nearby jungles",
        "threat": "Mid",
        "bio": "Vietnamese organized-crime syndicate; claims Hunter's Paradise as personal turf.",
    },
    {
        "name": "Naga Pirates",
        "type": "hostile",
        "hq": "Ban Pa / Tiger Bay coastline",
        "aor": "Coastal villages, fishing huts, cargo docks",
        "threat": "Mid-High",
        "bio": "Malay pirate group exploiting the chaos; controls Ban Pa and the Tiger Bay viewpoint.",
    },
    {
        "name": "Viper Tactical Services",
        "type": "hostile",
        "hq": "Pha Lang Airfield",
        "aor": "Pha Lang Airfield + Fort Narith",
        "threat": "High",
        "bio": "Highly lethal Thai PMC; locked down the airfield, uses suppressive fire and flanking tactics.",
    },
    {
        "name": "Lamang Liberation Army (LLA)",
        "type": "hostile",
        "hq": "Inland villages",
        "aor": "Kiu Vongsa + interior",
        "threat": "Low-Mid",
        "bio": "Insurgent militia with deep village ties — easier kills, but rarely alone.",
    },
    {
        "name": "Sifa Syndicate",
        "type": "hostile",
        "hq": "—",
        "aor": "Smuggling routes",
        "threat": "Mid",
        "bio": "Smuggling network funneling weapons and contraband across Lamang.",
    },
]


# Common region names used as filter values.
REGIONS = [
    "Hunter's Paradise",
    "Kiu Vongsa",
    "Ban Pa",
    "Tiger Bay",
    "Sawmill",
    "Pha Lang Airfield",
    "Fort Narith",
    "Blue Lagoon",
    "Midnight Sapphire",
    "YBL-1",
]

# Group ids we know and what they represent (from gzwtacmap.com URLs).
GROUPS = {
    "1": "Landing Zones",
    "38": "Combat Outposts",
}
