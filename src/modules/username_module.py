"""
EchoTrace — Username Search Module
Vérifie la présence d'un pseudo sur ~70 plateformes publiques.
"""

import asyncio
from typing import List
import aiohttp
from modules.base import BaseModule, OsintResult, random_delay
from core.scorer import compute_result_confidence, score_username_similarity


# ─── Sites database ───────────────────────────────────────────────────────────
# Format: (platform, url_template, check_type, false_positive_string)
# check_type: "status_200" | "body_not_contains" | "body_contains"

SITES = [
    # Réseaux sociaux
    ("GitHub",       "https://github.com/{}",                           "status_200",         "Not Found"),
    ("Reddit",       "https://www.reddit.com/user/{}",                  "body_not_contains",  "Sorry, nobody on Reddit goes by that name"),
    ("Twitter/X",    "https://twitter.com/{}",                          "body_not_contains",  "This account doesn\u2019t exist"),
    ("Instagram",    "https://www.instagram.com/{}/",                   "status_200",         "Page Not Found"),
    ("TikTok",       "https://www.tiktok.com/@{}",                      "body_not_contains",  "Couldn\u2019t find this account"),
    ("YouTube",      "https://www.youtube.com/@{}",                     "status_200",         ""),
    ("Twitch",       "https://www.twitch.tv/{}",                        "body_not_contains",  "Sorry. Unless you\u2019ve got a time machine"),
    ("Pinterest",    "https://www.pinterest.com/{}/",                   "status_200",         ""),
    ("Snapchat",     "https://www.snapchat.com/add/{}",                 "body_not_contains",  "Sorry, we couldn\u2019t find"),
    ("LinkedIn",     "https://www.linkedin.com/in/{}/",                 "status_200",         ""),

    # Dev / Tech
    ("GitLab",       "https://gitlab.com/{}",                           "status_200",         ""),
    ("Bitbucket",    "https://bitbucket.org/{}",                        "status_200",         ""),
    ("HackerNews",   "https://news.ycombinator.com/user?id={}",         "body_contains",      "created"),
    ("Stack Overflow","https://stackoverflow.com/users/{}",             "status_200",         ""),
    ("Dev.to",       "https://dev.to/{}",                               "status_200",         ""),
    ("Codepen",      "https://codepen.io/{}",                           "status_200",         ""),
    ("Replit",       "https://replit.com/@{}",                          "status_200",         ""),
    ("NPM",          "https://www.npmjs.com/~{}",                       "status_200",         ""),
    ("PyPI",         "https://pypi.org/user/{}/",                       "status_200",         ""),
    ("Pastebin",     "https://pastebin.com/u/{}",                       "status_200",         ""),

    # Gaming
    ("Steam",        "https://steamcommunity.com/id/{}",                "body_not_contains",  "The specified profile could not be found"),
    ("Roblox",       "https://www.roblox.com/user.aspx?username={}",    "body_not_contains",  "Page cannot be found"),
    ("Minecraft",    "https://api.mojang.com/users/profiles/minecraft/{}","status_200",        ""),
    ("Chess.com",    "https://www.chess.com/member/{}",                 "status_200",         ""),
    ("Lichess",      "https://lichess.org/@/{}",                        "status_200",         ""),

    # Créativité
    ("Behance",      "https://www.behance.net/{}",                      "status_200",         ""),
    ("Dribbble",     "https://dribbble.com/{}",                         "status_200",         ""),
    ("ArtStation",   "https://www.artstation.com/{}",                   "status_200",         ""),
    ("DeviantArt",   "https://www.deviantart.com/{}",                   "status_200",         ""),
    ("Wattpad",      "https://www.wattpad.com/user/{}",                 "status_200",         ""),
    ("Soundcloud",   "https://soundcloud.com/{}",                       "status_200",         ""),

    # Forums / Communautés
    ("Medium",       "https://medium.com/@{}",                          "status_200",         ""),
    ("Tumblr",       "https://{}.tumblr.com",                           "status_200",         ""),
    ("Quora",        "https://www.quora.com/profile/{}",                "status_200",         ""),
    ("Disqus",       "https://disqus.com/by/{}/",                       "status_200",         ""),
    ("Gravatar",     "https://en.gravatar.com/{}",                      "status_200",         ""),
    ("About.me",     "https://about.me/{}",                             "status_200",         ""),

    # Tech / OSINT friendly
    ("HaveIBeenPwned", "https://haveibeenpwned.com/account/{}",         "status_200",         ""),
    ("Keybase",      "https://keybase.io/{}",                           "status_200",         ""),
    ("Telegram",     "https://t.me/{}",                                 "body_not_contains",  "If you have Telegram"),
    ("Linktree",     "https://linktr.ee/{}",                            "status_200",         ""),

    # Streaming / Média
    ("Vimeo",        "https://vimeo.com/{}",                            "status_200",         ""),
    ("Dailymotion",  "https://www.dailymotion.com/{}",                  "status_200",         ""),
    ("Spotify",      "https://open.spotify.com/user/{}",                "status_200",         ""),
    ("Last.fm",      "https://www.last.fm/user/{}",                     "status_200",         ""),

    # Autre
    ("Flickr",       "https://www.flickr.com/people/{}",               "status_200",         ""),
    ("Ebay",         "https://www.ebay.fr/usr/{}",                      "status_200",         ""),
    ("Etsy",         "https://www.etsy.com/shop/{}",                    "status_200",         ""),
    ("ProductHunt",  "https://www.producthunt.com/@{}",                 "status_200",         ""),
    ("AngelList",    "https://angel.co/u/{}",                           "status_200",         ""),
    ("Crunchbase",   "https://www.crunchbase.com/person/{}",            "status_200",         ""),
]


class UsernameModule(BaseModule):
    name = "username"
    description = "Recherche de pseudo sur 50+ plateformes publiques"
    requires = ["pseudo"]

    async def run(self, target_data: dict, session: aiohttp.ClientSession,
                  progress_cb=None) -> List[OsintResult]:
        
        username = target_data.get("pseudo", "").strip()
        if not username:
            return []

        # Générer les variations de username
        username_variations = self._generate_username_variations(username)
        
        results = []
        total = len(SITES) * len(username_variations)
        
        # Découper en batches pour éviter de flood
        batch_size = 15
        completed = 0
        
        for variation in username_variations:
            if progress_cb:
                progress_cb(
                    f"Test variation: {variation}",
                    completed / total * 100
                )
            
            # Traiter les sites par batch
            for i in range(0, len(SITES), batch_size):
                batch = SITES[i:i+batch_size]
                tasks = [
                    self._check_site(session, variation, platform, url_tpl, check_type, fp)
                    for platform, url_tpl, check_type, fp in batch
                ]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for res in batch_results:
                    if isinstance(res, OsintResult):
                        # Ajouter la variation testée dans les données
                        res.data["tested_username"] = variation
                        res.data["original_username"] = username
                        results.append(res)
                    completed += 1
                
                if progress_cb:
                    progress_cb(
                        f"Vérification username : {completed}/{total}",
                        completed / total * 100
                    )
                await asyncio.sleep(0.2)
        
        return results
    
    def _generate_username_variations(self, username: str) -> List[str]:
        """Génère des variations de username pour augmenter les chances de trouver des comptes."""
        variations = [username]  # Original
        
        # Remplacer les caractères communs
        replacements = {
            'a': ['4', '@', 'a'],
            'e': ['3', '€', 'e'],
            'i': ['1', '!', 'i'],
            'o': ['0', 'o'],
            's': ['5', '$', 's'],
            't': ['7', 't'],
            'l': ['1', 'l'],
            'z': ['2', 'z']
        }
        
        # Variations avec remplacements
        for char, repls in replacements.items():
            if char in username.lower():
                for repl in repls:
                    if repl != char:
                        variations.append(username.lower().replace(char, repl))
        
        # Variations avec séparateurs
        if '_' in username:
            variations.append(username.replace('_', '-'))
            variations.append(username.replace('_', ''))
        elif '-' in username:
            variations.append(username.replace('-', '_'))
            variations.append(username.replace('-', ''))
        
        # Variations avec préfixes/suffixes communs
        common_prefixes = ['_', '-', 'x', 'xx', 'the', 'real']
        common_suffixes = ['_', '-', 'x', 'xx', 'official', 'real', ' verified']
        
        for prefix in common_prefixes:
            if not username.startswith(prefix):
                variations.append(prefix + username)
        
        for suffix in common_suffixes:
            if not username.endswith(suffix):
                variations.append(username + suffix)
        
        # Variations de casse
        if username.islower():
            variations.append(username.upper())
        elif username.isupper():
            variations.append(username.lower())
        else:
            variations.append(username.lower())
            variations.append(username.upper())
        
        # Éliminer les doublons et limiter à un nombre raisonnable
        return list(set(variations[:20]))  # Limiter à 20 variations max

    async def _check_site(self, session, username, platform, url_tpl,
                           check_type, false_positive) -> OsintResult | None:
        
        url = url_tpl.format(username)
        
        try:
            async with session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
                    "Accept-Language": "fr-FR,fr;q=0.9",
                },
                timeout=aiohttp.ClientTimeout(total=8),
                allow_redirects=True,
                ssl=False
            ) as resp:
                status = resp.status
                text = ""
                
                if check_type in ("body_not_contains", "body_contains"):
                    try:
                        text = await resp.text(errors="ignore")
                    except Exception:
                        text = ""
                
                found = False
                
                if check_type == "status_200":
                    found = status == 200
                elif check_type == "body_not_contains":
                    found = status == 200 and (not false_positive or false_positive not in text)
                elif check_type == "body_contains":
                    found = status == 200 and false_positive in text
                
                if found:
                    confidence = compute_result_confidence("username", {
                        "username_exact": True,
                        "http_200": status == 200,
                        "profile_exists": True,
                    })
                    return OsintResult(
                        module="username",
                        platform=platform,
                        url=url,
                        title=f"@{username} sur {platform}",
                        username=username,
                        confidence=confidence,
                        data={"http_status": status}
                    )
        except Exception:
            pass
        
        return None