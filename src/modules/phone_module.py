"""
EchoTrace — Phone Number Analysis Module
Validation et recherche de numéros de téléphone
"""

import asyncio
import re
from typing import List
import aiohttp
from modules.base import BaseModule, OsintResult, random_delay
from core.scorer import compute_result_confidence


class PhoneModule(BaseModule):
    name = "phone"
    description = "Analyse de numéro: validation, format, et recherche publique"
    requires = ["telephone"]
    
    def __init__(self):
        self.country_codes = {
            '+33': 'France', '+1': 'USA/Canada', '+44': 'UK',
            '+49': 'Allemagne', '+34': 'Espagne', '+39': 'Italie',
            '+41': 'Suisse', '+31': 'Pays-Bas', '+32': 'Belgique'
        }
    
    async def run(self, target_data: dict, session: aiohttp.ClientSession,
                  progress_cb=None) -> List[OsintResult]:
        
        phone = target_data.get("telephone", "").strip()
        if not phone:
            return []
        
        results = []
        
        if progress_cb:
            progress_cb("Analyse du numéro de téléphone...", 10)
        
        # Valider et normaliser le numéro
        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return results
        
        # Analyser le format
        format_info = self._analyze_phone_format(normalized_phone)
        
        if format_info:
            confidence = compute_result_confidence("phone", {
                "phone_valid": True,
                "format_detected": True
            })
            
            results.append(OsintResult(
                module="phone",
                platform="Phone Validation",
                url="",
                title=f"Numéro valide: {normalized_phone}",
                username="",
                confidence=confidence * 0.8,
                data={
                    "original_phone": phone,
                    "normalized_phone": normalized_phone,
                    "country": format_info.get("country", "Inconnu"),
                    "type": format_info.get("type", "Inconnu"),
                    "carrier": format_info.get("carrier", "Inconnu")
                }
            ))
        
        # Recherche publique du numéro
        search_results = await self._search_phone_public(session, normalized_phone, progress_cb)
        results.extend(search_results)
        
        return results
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalise un numéro de téléphone."""
        # Enlever les caractères non numériques sauf +
        phone = re.sub(r'[^\d+]', '', phone)
        
        # S'assurer qu'il commence par +
        if not phone.startswith('+'):
            # Ajouter le code pays par défaut (France)
            if len(phone) == 9:  # Format français sans indicatif
                phone = '+33' + phone[1:]  # Enlever le 0 du début
            elif len(phone) == 10 and phone.startswith('0'):  # Format français avec 0
                phone = '+33' + phone[1:]
            else:
                return ""  # Format non reconnu
        
        return phone
    
    def _analyze_phone_format(self, phone: str) -> dict:
        """Analyse le format du numéro pour déterminer le pays et le type."""
        info = {}
        
        # Extraire le code pays
        match = re.match(r'^(\+\d{1,3})(\d+)$', phone)
        if match:
            country_code, number = match.groups()
            info["country"] = self.country_codes.get(country_code, f"Inconnu ({country_code})")
            info["country_code"] = country_code
            
            # Déterminer le type selon la longueur
            if country_code == '+33':  # France
                if len(number) == 9 and number.startswith('6'):
                    info["type"] = "Mobile"
                    info["carrier"] = "Opérateur mobile français"
                elif len(number) == 9 and number.startswith(('1', '2', '3', '4', '5')):
                    info["type"] = "Fixe"
                    info["carrier"] = "Opérateur fixe français"
                else:
                    info["type"] = "Inconnu"
                    info["carrier"] = "Inconnu"
            elif country_code == '+1':  # USA/Canada
                if len(number) == 10:
                    info["type"] = "Amérique du Nord"
                    info["carrier"] = "Opérateur américain/canadien"
                else:
                    info["type"] = "Inconnu"
                    info["carrier"] = "Inconnu"
            else:
                info["type"] = "International"
                info["carrier"] = "Opérateur international"
        
        return info
    
    async def _search_phone_public(self, session: aiohttp.ClientSession, phone: str,
                                progress_cb=None) -> List[OsintResult]:
        """Cherche le numéro publiquement sur le web."""
        results = []
        
        if progress_cb:
            progress_cb("Recherche publique du numéro...", 70)
        
        # Enlever l'indicatif pays pour la recherche
        search_phone = phone.replace('+33', '0').replace('+1', '').replace('+44', '0')
        
        # Requêtes de recherche pour le numéro
        search_queries = [
            f'"{phone}"',
            f'"{search_phone}" "contact"',
            f'"{search_phone}" "directory"',
            f'"{search_phone}" "annuaire"',
            f'"{search_phone}" site:linkedin.com',
            f'"{search_phone}" site:facebook.com'
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
                        if any(term in text.lower() for term in ["results", "directory", "annuaire"]):
                            confidence = compute_result_confidence("phone", {
                                "phone_match": True,
                                "public_mention": True
                            })
                            
                            results.append(OsintResult(
                                module="phone",
                                platform="Public Search",
                                url=search_url,
                                title=f"Numéro trouvé publiquement: {phone}",
                                username="",
                                confidence=confidence * 0.4,
                                data={
                                    "phone": phone,
                                    "search_query": query,
                                    "public_mention": True
                                }
                            ))
                            break  # Arrêter après première trouvaison
                
                if progress_cb:
                    progress_cb(f"Recherche {i+1}/{len(search_queries)}", 70 + (i/len(search_queries)) * 30)
                
                await random_delay()
            except Exception as e:
                print(f"Erreur recherche téléphone: {e}")
        
        return results
