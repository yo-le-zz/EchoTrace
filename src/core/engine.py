"""
EchoTrace — Core Engine
Orchestrateur principal pour les analyses OSINT
"""

import asyncio
import json
import time
from typing import List, Dict, Optional, Callable
import aiohttp
from modules.base import BaseModule, OsintResult
from modules.username_module import UsernameModule
from modules.google_module import GoogleModule
from modules.image_module import ImageModule
from modules.email_module import EmailModule
from modules.phone_module import PhoneModule
from database.db import save_target, start_search, finish_search, save_result, get_results
from core.scorer import is_input_valid, compute_input_score
from config.settings import SETTINGS


class EchoTraceEngine:
    """Moteur principal d'EchoTrace."""
    
    def __init__(self):
        self.modules: List[BaseModule] = [
            UsernameModule(),
            GoogleModule(),
            ImageModule(),
            EmailModule(),
            PhoneModule(),
        ]
        self.running = False
        self.current_target_id = None
        
    def get_available_modules(self, target_data: dict) -> List[BaseModule]:
        """Retourne les modules qui peuvent s'exécuter avec les données fournies."""
        available = []
        for module in self.modules:
            if module.can_run(target_data):
                available.append(module)
        return available
    
    async def validate_input(self, target_data: dict) -> tuple[bool, str]:
        """Valide les données d'entrée."""
        valid, score, message = is_input_valid(target_data)
        return valid, message
    
    async def run_analysis(self, target_data: dict, 
                          progress_cb: Optional[Callable] = None) -> Dict:
        """
        Lance une analyse complète sur la cible.
        Retourne un dictionnaire avec les résultats.
        """
        if self.running:
            raise RuntimeError("Une analyse est déjà en cours.")
        
        # Validation
        valid, message = await self.validate_input(target_data)
        if not valid:
            return {
                "success": False,
                "error": message,
                "results": [],
                "target_id": None
            }
        
        self.running = True
        start_time = time.time()
        
        try:
            # Sauvegarder la cible
            input_score = compute_input_score(target_data)
            self.current_target_id = save_target(
                target_data, 
                input_score, 
                target_data.get("label", "")
            )
            
            # Récupérer les modules disponibles
            available_modules = self.get_available_modules(target_data)
            
            if progress_cb:
                progress_cb("Démarrage de l'analyse...", 0)
            
            all_results = []
            total_modules = len(available_modules)
            
            # Exécuter les modules en parallèle avec asyncio.gather
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=SETTINGS.max_concurrent * 2),
                timeout=aiohttp.ClientTimeout(total=SETTINGS.request_timeout)
            ) as session:
                
                # Créer les tâches pour chaque module
                tasks = []
                search_ids = {}
                
                for i, module in enumerate(available_modules):
                    # Démarrer le tracking de recherche
                    search_id = start_search(
                        self.current_target_id,
                        module.name,
                        json.dumps(target_data)
                    )
                    search_ids[module.name] = search_id
                    
                    # Créer la tâche pour ce module
                    task = asyncio.create_task(
                        self._run_module_with_tracking(
                            module, target_data, session, search_id, progress_cb, i, total_modules
                        )
                    )
                    tasks.append(task)
                
                # Exécuter toutes les tâches simultanément
                if progress_cb:
                    progress_cb("Exécution des modules en parallèle...", 10)
                
                results_list = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Traiter les résultats
                for i, result in enumerate(results_list):
                    if isinstance(result, Exception):
                        module_name = available_modules[i].name
                        print(f"Erreur module {module_name}: {result}")
                        finish_search(search_ids[module_name], "error")
                    else:
                        all_results.extend(result)
            
            # Récupérer tous les résultats depuis la DB
            db_results = get_results(self.current_target_id)
            
            duration = time.time() - start_time
            
            if progress_cb:
                progress_cb("Analyse terminée!", 100)
            
            return {
                "success": True,
                "target_id": self.current_target_id,
                "input_score": input_score,
                "duration": duration,
                "modules_run": len(available_modules),
                "results_count": len(db_results),
                "results": [r for r in db_results],
                "summary": self._generate_summary(db_results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Erreur lors de l'analyse: {str(e)}",
                "results": [],
                "target_id": self.current_target_id
            }
        finally:
            self.running = False
            self.current_target_id = None
    
    def _generate_summary(self, results: List[Dict]) -> Dict:
        """Génère un résumé des résultats."""
        if not results:
            return {"platforms": [], "high_confidence": 0, "total": 0}
        
        platforms = {}
        high_confidence = 0
        
        for result in results:
            platform = result["platform"]
            confidence = result["confidence"]
            
            if platform not in platforms:
                platforms[platform] = 0
            platforms[platform] += 1
            
            if confidence >= 0.8:
                high_confidence += 1
        
        return {
            "platforms": sorted(platforms.items(), key=lambda x: x[1], reverse=True),
            "high_confidence": high_confidence,
            "total": len(results),
            "avg_confidence": sum(r["confidence"] for r in results) / len(results)
        }
    
    async def _run_module_with_tracking(self, module, target_data, session, search_id, progress_cb, module_index, total_modules):
        """Exécute un module avec tracking et gestion d'erreurs."""
        try:
            if progress_cb:
                progress_cb(
                    f"Module: {module.description}",
                    10 + (module_index / total_modules) * 80
                )
            
            # Exécuter le module
            module_results = await module.run(target_data, session, progress_cb)
            
            # Sauvegarder les résultats
            results_dicts = []
            for result in module_results:
                save_result(
                    self.current_target_id,
                    search_id,
                    result.module,
                    result.platform,
                    result.url,
                    result.title,
                    result.username,
                    result.confidence,
                    result.data
                )
                results_dicts.append(result.to_dict())
            
            # Marquer la recherche comme terminée
            finish_search(search_id, "done")
            
            return results_dicts
            
        except Exception as e:
            finish_search(search_id, "error")
            raise e
    
    def stop_analysis(self):
        """Arrête l'analyse en cours."""
        self.running = False


# Instance globale
ENGINE = EchoTraceEngine()
