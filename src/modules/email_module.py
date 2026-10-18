"""
EchoTrace — Email Analysis Module
Vérification des domaines et recherche de breaches
"""

import asyncio
import re
from typing import List
import aiohttp
from modules.base import BaseModule, OsintResult, random_delay
from core.scorer import compute_result_confidence


class EmailModule(BaseModule):
    name = "email"
    description = "Analyse d'email: domaine, breaches, et vérifications"
    requires = ["email"]
    
    def __init__(self):
        self.email_domains = [
            "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
            "protonmail.com", "icloud.com", "mail.com", "aol.com"
        ]
    
    async def run(self, target_data: dict, session: aiohttp.ClientSession,
                  progress_cb=None) -> List[OsintResult]:
        
        email = target_data.get("email", "").strip()
        if not email or "@" not in email:
            return []
        
        results = []
        
        if progress_cb:
            progress_cb("Analyse de l'email...", 10)
        
        # Extraire le domaine
        domain = email.split("@")[-1].lower()
        
        # Vérifier les services de breach
        breach_results = await self._check_breaches(session, email, progress_cb)
        results.extend(breach_results)
        
        # Vérifier le domaine
        domain_results = await self._analyze_domain(session, domain, progress_cb)
        results.extend(domain_results)
        
        # Chercher l'email publiquement
        search_results = await self._search_email_public(session, email, progress_cb)
        results.extend(search_results)
        
        return results
    
    async def _check_breaches(self, session: aiohttp.ClientSession, email: str, 
                           progress_cb=None) -> List[OsintResult]:
        """Vérifie si l'email apparaît dans des breaches connues."""
        results = []
        
        # Simulation de vérification HIBP
        if progress_cb:
            progress_cb("Vérification des breaches...", 30)
        
        try:
            # Utiliser l'API publique HIBP (rate limitée)
            url = f"https://haveibeenpwned.com/api/v2/breachedaccount/{email}"
            
            async with session.get(
                url,
                headers={
                    "User-Agent": "EchoTrace-OSINT/1.0",
                    "Accept": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        confidence = compute_result_confidence("email", {
                            "email_match": True,
                            "breach_found": True,
                            "breach_count": len(data)
                        })
                        
                        results.append(OsintResult(
                            module="email",
                            platform="HaveIBeenPwned",
                            url="https://haveibeenpwned.com/",
                            title=f"{len(data)} breaches trouvés",
                            username="",
                            confidence=confidence,
                            data={
                                "breaches": data,
                                "email": email,
                                "breach_count": len(data)
                            }
                        ))
                elif resp.status == 404:
                    # Email non trouvé dans les breaches
                    confidence = compute_result_confidence("email", {
                        "email_match": True,
                        "breach_found": False
                    })
                    
                    results.append(OsintResult(
                        module="email",
                        platform="HaveIBeenPwned",
                        url="https://haveibeenpwned.com/",
                        title="Aucun breach trouvé",
                        username="",
                        confidence=confidence * 0.7,  # Confiance plus faible si pas de breach
                        data={
                            "email": email,
                            "breach_count": 0
                        }
                    ))
        except Exception as e:
            print(f"Erreur vérification breaches: {e}")
        
        await random_delay()
        return results
    
    async def _analyze_domain(self, session: aiohttp.ClientSession, domain: str,
                          progress_cb=None) -> List[OsintResult]:
        """Analyse le domaine de l'email."""
        results = []
        
        if progress_cb:
            progress_cb("Analyse du domaine...", 60)
        
        # Vérifier si c'est un domaine email connu
        if domain in self.email_domains:
            confidence = compute_result_confidence("email", {
                "email_match": True,
                "known_domain": True
            })
            
            results.append(OsintResult(
                module="email",
                platform=f"Email Provider ({domain})",
                url=f"https://{domain}",
                title=f"Fournisseur email: {domain}",
                username="",
                confidence=confidence * 0.8,
                data={
                    "domain": domain,
                    "provider_type": "email"
                }
            ))
        
        # Vérifier les informations WHOIS basiques
        try:
            whois_url = f"https://www.whois.com/whois/{domain}"
            async with session.get(
                whois_url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    confidence = compute_result_confidence("email", {
                        "email_match": True,
                        "domain_info": True
                    })
                    
                    results.append(OsintResult(
                        module="email",
                        platform="WHOIS",
                        url=whois_url,
                        title=f"Informations WHOIS: {domain}",
                        username="",
                        confidence=confidence * 0.6,
                        data={
                            "domain": domain,
                            "whois_available": True
                        }
                    ))
        except Exception as e:
            print(f"Erreur WHOIS: {e}")
        
        await random_delay()
        return results
    
    async def _search_email_public(self, session: aiohttp.ClientSession, email: str,
                               progress_cb=None) -> List[OsintResult]:
        """Cherche l'email publiquement sur le web."""
        results = []
        
        if progress_cb:
            progress_cb("Recherche publique de l'email...", 80)
        
        # Échapper l'email pour la recherche
        escaped_email = f'"{email}"'
        
        # Requêtes de recherche pour l'email
        search_queries = [
            escaped_email,
            f'{escaped_email} "profile"',
            f'{escaped_email} "contact"',
            f'{escaped_email} "about"',
            f'{escaped_email} site:linkedin.com',
            f'{escaped_email} site:github.com',
            f'{escaped_email} site:twitter.com'
        ]
        
        for i, query in enumerate(search_queries):
            try:
                search_url = f"https://duckduckgo.com/html/?q={query}"
                async with session.get(
                    search_url,
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text(errors="ignore")
                        
                        # Parser simple des résultats
                        if "results" in text.lower():
                            confidence = compute_result_confidence("email", {
                                "email_match": True,
                                "public_mention": True
                            })
                            
                            results.append(OsintResult(
                                module="email",
                                platform="Public Search",
                                url=search_url,
                                title=f"Email trouvé publiquement: {email}",
                                username="",
                                confidence=confidence * 0.5,
                                data={
                                    "email": email,
                                    "search_query": query,
                                    "public_mention": True
                                }
                            ))
                            break  # Arrêter après première trouvaison
                
                if progress_cb:
                    progress_cb(f"Recherche {i+1}/{len(search_queries)}", 80 + (i/len(search_queries)) * 20)
                
                await random_delay()
            except Exception as e:
                print(f"Erreur recherche email: {e}")
        
        return results
