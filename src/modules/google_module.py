"""
EchoTrace — Google Dorking Module
Recherche avancée avec Google Dorks
"""

import asyncio
import urllib.parse
from typing import List
import aiohttp
from bs4 import BeautifulSoup
from modules.base import BaseModule, OsintResult, random_delay
from core.scorer import compute_result_confidence


class GoogleModule(BaseModule):
    name = "google"
    description = "Recherche Google avancée avec dorks"
    requires = ["pseudo", "nom", "prenom", "email", "entreprise"]
    
    def __init__(self):
        self.search_engines = [
            ("Google", "https://www.google.com/search?q={}", "div.g"),
            ("Bing", "https://www.bing.com/search?q={}", "li.b_algo"),
            ("DuckDuckGo", "https://duckduckgo.com/html/?q={}", "div.result"),
        ]
    
    async def run(self, target_data: dict, session: aiohttp.ClientSession,
                  progress_cb=None) -> List[OsintResult]:
        
        results = []
        queries = self._generate_queries(target_data)
        
        if not queries:
            return results
        
        total_queries = len(queries) * len(self.search_engines)
        completed = 0
        
        for engine_name, engine_url, result_selector in self.search_engines:
            for query in queries:
                try:
                    if progress_cb:
                        progress_cb(
                            f"Recherche {engine_name}: {query[:50]}...",
                            (completed / total_queries) * 100
                        )
                    
                    search_results = await self._search_engine(
                        session, engine_url.format(urllib.parse.quote(query)),
                        engine_name, result_selector
                    )
                    
                    results.extend(search_results)
                    completed += 1
                    
                    await random_delay()
                    
                except Exception as e:
                    print(f"Erreur recherche {engine_name}: {e}")
                    completed += 1
                    continue
        
        return results
    
    def _generate_queries(self, target_data: dict) -> List[str]:
        """Génère des requêtes Google Dorks optimisées."""
        queries = []
        
        pseudo = target_data.get("pseudo", "").strip()
        nom = target_data.get("nom", "").strip()
        prenom = target_data.get("prenom", "").strip()
        email = target_data.get("email", "").strip()
        entreprise = target_data.get("entreprise", "").strip()
        
        # Requêtes username
        if pseudo:
            queries.extend([
                f'"{pseudo}"',
                f'"{pseudo}" site:linkedin.com',
                f'"{pseudo}" site:github.com',
                f'"{pseudo}" site:instagram.com',
                f'"{pseudo}" site:twitter.com',
                f'"{pseudo}" site:reddit.com',
                f'"{pseudo}" site:tiktok.com',
                f'"{pseudo}" site:youtube.com',
                f'"{pseudo}" site:medium.com',
                f'"{pseudo}" "profile"',
                f'"{pseudo}" "about"',
                f'"{pseudo}" "contact"',
            ])
        
        # Requêtes nom complet
        if nom and prenom:
            full_name = f"{prenom} {nom}"
            queries.extend([
                f'"{full_name}"',
                f'"{full_name}" site:linkedin.com',
                f'"{full_name}" site:github.com',
                f'"{full_name}" site:facebook.com',
                f'"{full_name}" "curriculum vitae"',
                f'"{full_name}" "portfolio"',
                f'"{full_name}" "developer"',
                f'"{full_name}" "engineer"',
            ])
        
        # Requêtes email
        if email:
            queries.extend([
                f'"{email}"',
                f'"{email}" site:linkedin.com',
                f'"{email}" site:github.com',
                f'"{email}" "leaked"',
                f'"{email}" "breach"',
                f'"{email}" "pastebin"',
            ])
        
        # Requêtes entreprise
        if entreprise:
            if pseudo:
                queries.extend([
                    f'"{pseudo}" "{entreprise}"',
                    f'"{pseudo}" site:linkedin.com "{entreprise}"',
                ])
            if nom and prenom:
                full_name = f"{prenom} {nom}"
                queries.extend([
                    f'"{full_name}" "{entreprise}"',
                    f'"{full_name}" site:linkedin.com "{entreprise}"',
                ])
        
        # Requêtes avancées avec filetype
        if pseudo:
            queries.extend([
                f'"{pseudo}" filetype:pdf',
                f'"{pseudo}" filetype:doc',
                f'"{pseudo}" filetype:txt',
            ])
        
        return list(set(queries))  # Éliminer les doublons
    
    async def _search_engine(self, session: aiohttp.ClientSession, 
                           search_url: str, engine_name: str, 
                           result_selector: str) -> List[OsintResult]:
        """Effectue une recherche sur un moteur de recherche."""
        results = []
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
            }
            
            async with session.get(
                search_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
                ssl=False
            ) as resp:
                if resp.status != 200:
                    return results
                
                html = await resp.text(errors="ignore")
                soup = BeautifulSoup(html, 'html.parser')
                
                # Parser les résultats
                search_results = soup.select(result_selector)
                
                for result in search_results[:10]:  # Limiter à 10 résultats
                    try:
                        # Extraire titre et URL
                        title_elem = result.find('a') or result.find('h3')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '')
                        
                        # Nettoyer l'URL (Google ajoute parfois des redirections)
                        if url.startswith('/url?'):
                            url = urllib.parse.unquote(url.split('&q=')[1].split('&')[0]) if '&q=' in url else url
                        
                        if not url or url.startswith('#'):
                            continue
                        
                        # Calculer la confiance
                        confidence = compute_result_confidence("google", {
                            "http_200": True,
                            "title_match": len(title) > 10,
                            "cross_link": any(domain in url.lower() for domain in 
                                            ['linkedin.com', 'github.com', 'instagram.com', 
                                             'twitter.com', 'reddit.com', 'youtube.com'])
                        })
                        
                        results.append(OsintResult(
                            module="google",
                            platform=engine_name,
                            url=url,
                            title=title,
                            username="",  # Pas de username direct dans les résultats de recherche
                            confidence=confidence,
                            data={
                                "search_engine": engine_name,
                                "snippet": result.get_text(strip=True)[:200]
                            }
                        ))
                        
                    except Exception:
                        continue
        
        except Exception as e:
            print(f"Erreur recherche {engine_name}: {e}")
        
        return results
