"""Moteur principal : orchestre les modules OSINT, vérifie les profils et enregistre les résultats."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Callable

from echotrace.config.settings import get_settings
from echotrace.core.compare import diff_results
from echotrace.core.identity import target_key
from echotrace.core.scorer import compute_input_score, is_input_valid
from echotrace.core.verify import verify_rows
from echotrace.database import db
from echotrace.modules import build_modules
from echotrace.modules.base import BaseModule, ProgressCallback
from echotrace.network import create_session

log = logging.getLogger(__name__)

HIGH_CONFIDENCE = 0.8
# Part de la barre de progression réservée aux modules ; le reste va à la vérification des profils.
MODULES_SHARE = 85.0

ResultCallback = Callable[[list[dict]], None]


def build_summary(results: list[dict]) -> dict:
    """Résumé chiffré d'une liste de résultats (format de la base de données)."""
    platforms = Counter(r["platform"] for r in results)
    modules = Counter(r["module"] for r in results)
    return {
        "total": len(results),
        "high_confidence": sum(1 for r in results if r["confidence"] >= HIGH_CONFIDENCE),
        "avg_confidence": sum(r["confidence"] for r in results) / len(results) if results else 0.0,
        "platforms": platforms.most_common(),
        "modules": modules.most_common(),
    }


def default_label(target_data: dict) -> str:
    """Nom lisible d'une cible pour l'historique."""
    full_name = " ".join(filter(None, (target_data.get("prenom"), target_data.get("nom"))))
    pseudo = (target_data.get("pseudo") or "").splitlines()[:1]
    for candidate in (target_data.get("label"), full_name, pseudo[0] if pseudo else "",
                      target_data.get("email"), target_data.get("telephone")):
        if candidate:
            return str(candidate)
    return "Sans nom"


class EchoTraceEngine:
    """Lance les modules applicables en parallèle et persiste leurs résultats."""

    def __init__(self, modules: list[BaseModule] | None = None) -> None:
        self.modules: list[BaseModule] = modules or build_modules()
        self.running = False
        self.current_target_id: int | None = None
        # Renseignés pendant une analyse pour permettre stop_analysis() depuis un autre thread.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: list[asyncio.Task] = []

    def get_available_modules(self, target_data: dict) -> list[BaseModule]:
        """Modules qui peuvent s'exécuter avec les données fournies."""
        return [module for module in self.modules if module.can_run(target_data)]

    async def validate_input(self, target_data: dict) -> tuple[bool, str]:
        valid, _score, message = is_input_valid(target_data)
        return valid, message

    async def run_analysis(
        self,
        target_data: dict,
        progress_cb: ProgressCallback | None = None,
        result_cb: ResultCallback | None = None,
        purpose: str = "",
    ) -> dict:
        """Lance une analyse complète et retourne un dictionnaire de résultats.

        `progress_cb(message, pourcentage)` et `result_cb(lignes)` peuvent être appelés depuis
        ce thread ; `result_cb` reçoit les résultats de chaque module dès qu'il a terminé.
        """
        if self.running:
            raise RuntimeError("Une analyse est déjà en cours.")

        valid, message = await self.validate_input(target_data)
        if not valid:
            return {"success": False, "error": message, "results": [], "target_id": None}

        self.running = True
        started = time.time()
        target_id: int | None = None
        settings = get_settings()

        def emit(text: str, percent: float) -> None:
            if progress_cb:
                progress_cb(text, percent)

        try:
            db.cache_clean()
            input_score = compute_input_score(target_data)
            key = target_key(target_data)
            ignored = db.ignored_urls(key)
            target_id = self.current_target_id = db.save_target(
                target_data, input_score, default_label(target_data), purpose, key
            )
            modules = self.get_available_modules(target_data)
            emit("Démarrage de l'analyse...", 0)

            # Chaque module rapporte sa propre progression ; la barre globale en est la moyenne.
            progress = {module.name: 0.0 for module in modules}
            errors: dict[str, str] = {}

            def module_callback(module: BaseModule) -> ProgressCallback:
                def callback(text: str, percent: float) -> None:
                    progress[module.name] = max(progress[module.name], min(percent, 100.0))
                    overall = 2 + sum(progress.values()) / max(len(progress), 1) * (MODULES_SHARE - 2) / 100
                    emit(f"[{module.name}] {text}", overall)
                return callback

            self._loop = asyncio.get_running_loop()
            async with create_session() as session:
                self._tasks = [
                    asyncio.create_task(
                        self._run_module(module, target_data, session, target_id, module_callback(module),
                                         errors, ignored, result_cb)
                    )
                    for module in modules
                ]
                outcomes = await asyncio.gather(*self._tasks, return_exceptions=True)
                cancelled = any(isinstance(o, asyncio.CancelledError) for o in outcomes)

                if settings.verify_profiles and not cancelled:
                    self._tasks = [asyncio.create_task(verify_rows(
                        session, db.get_results(target_id), target_data,
                        lambda text, pct: emit(text, MODULES_SHARE + pct * (98 - MODULES_SHARE) / 100)))]
                    try:
                        await self._tasks[0]
                    except asyncio.CancelledError:
                        cancelled = True
                    except Exception as exc:
                        # La vérification est un bonus : son échec ne doit pas perdre l'analyse.
                        log.exception("Échec de la vérification des profils")
                        errors["verify"] = str(exc)

            rows = db.get_results(target_id)
            previous = db.previous_target(key, target_id)
            diff = diff_results(db.get_results(previous["id"]), rows) if previous else None
            emit("Analyse interrompue." if cancelled else "Analyse terminée !", 100)
            return {
                "success": True,
                "cancelled": cancelled,
                "target_id": target_id,
                "target": target_data,
                "purpose": purpose,
                "input_score": input_score,
                "duration": time.time() - started,
                "modules_run": len(modules),
                "errors": errors,
                "results_count": len(rows),
                "results": rows,
                "summary": build_summary(rows),
                "previous_target_id": previous["id"] if previous else None,
                "diff": diff,
            }
        except Exception as exc:
            log.exception("Échec de l'analyse")
            return {
                "success": False,
                "error": f"Erreur lors de l'analyse : {exc}",
                "results": [],
                "target_id": target_id,
            }
        finally:
            self.running = False
            self.current_target_id = None
            self._loop = None
            self._tasks = []

    async def _run_module(self, module, target_data, session, target_id, callback, errors,
                          ignored, result_cb) -> None:
        """Exécute un module en isolant ses erreurs et en traçant la recherche en base."""
        search_id = db.start_search(target_id, module.name, module.description)
        try:
            results = await module.run(target_data, session, callback)
            # Un résultat déjà marqué faux positif pour cette cible n'est plus proposé.
            results = [r for r in results if not (r.url and r.url in ignored)]
            ids = db.save_results(target_id, search_id, results)
            db.finish_search(search_id, "done")
            if result_cb and results:
                result_cb([{**r.to_dict(), "id": rid, "status": "", "note": "", "found_at": time.time()}
                           for r, rid in zip(results, ids, strict=True)])
        except asyncio.CancelledError:
            db.finish_search(search_id, "cancelled")
            raise
        except Exception as exc:
            # Un module en échec ne doit pas faire perdre les résultats des autres.
            log.exception("Erreur du module %s", module.name)
            errors[module.name] = str(exc)
            db.finish_search(search_id, "error")

    def stop_analysis(self) -> None:
        """Demande l'arrêt de l'analyse en cours ; appelable depuis n'importe quel thread."""
        loop, tasks = self._loop, list(self._tasks)
        if loop is None or not loop.is_running():
            return

        def cancel_all() -> None:
            for task in tasks:
                if not task.done():
                    task.cancel()

        loop.call_soon_threadsafe(cancel_all)
