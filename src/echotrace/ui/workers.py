"""Threads de travail : l'analyse asynchrone ne doit jamais bloquer l'interface."""

from __future__ import annotations

import asyncio
import logging

from PyQt6.QtCore import QThread, pyqtSignal

from echotrace.core.engine import EchoTraceEngine

log = logging.getLogger(__name__)


class AnalysisThread(QThread):
    """Exécute `EchoTraceEngine.run_analysis` dans sa propre boucle asyncio."""

    progress_updated = pyqtSignal(str, float)
    results_found = pyqtSignal(list)  # lignes de résultats d'un module, dès qu'il a terminé
    analysis_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, engine: EchoTraceEngine, target_data: dict, purpose: str = "") -> None:
        super().__init__()
        self.engine = engine
        self.target_data = target_data
        self.purpose = purpose

    def run(self) -> None:
        try:
            result = asyncio.run(
                self.engine.run_analysis(
                    self.target_data,
                    self.progress_updated.emit,
                    self.results_found.emit,
                    self.purpose,
                )
            )
            self.analysis_finished.emit(result)
        except Exception as exc:
            log.exception("Thread d'analyse interrompu")
            self.error_occurred.emit(str(exc))

    def stop(self) -> None:
        self.engine.stop_analysis()
