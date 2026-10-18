"""Fenêtre principale d'EchoTrace."""

from __future__ import annotations

import json
import logging
import webbrowser
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from echotrace import __version__
from echotrace.config.settings import get_settings
from echotrace.core.compare import diff_results, format_diff
from echotrace.core.engine import EchoTraceEngine, build_summary
from echotrace.core.identity import PURPOSES, split_photos
from echotrace.core.scorer import compute_input_score, confidence_label, is_input_valid
from echotrace.database import db
from echotrace.reports import ReportGenerator
from echotrace.ui.config_dialog import ConfigDialog
from echotrace.ui.workers import AnalysisThread

log = logging.getLogger(__name__)

BASIC_FIELDS = [
    ("prenom", "Prénom", "John"), ("nom", "Nom", "Doe"),
    ("pseudo", "Pseudo(s)", "yolezz ; autre ; yolezz."), ("email", "Email", "john.doe@example.com"),
    ("telephone", "Téléphone", "+33612345678"), ("ville", "Ville", "Paris"),
    ("pays", "Pays", "France"), ("entreprise", "Entreprise", "TechCorp"),
]
PSEUDO_TIP = (
    "Plusieurs pseudos : séparez-les par « ; ».\n"
    "Variantes automatiques : yolezz → yo_le_zz, yo-le-zz, yo.le.zz, yole_zz...\n"
    "Mode joker : « yolezz. » (point final) cherche yolezz.secret, yolezz.dev... "
    "d'après les moteurs de recherche et une liste de suffixes courants."
)
SOCIAL_FIELDS = [
    ("instagram", "Instagram"), ("twitter", "Twitter/X"), ("github", "GitHub"),
    ("reddit", "Reddit"), ("tiktok", "TikTok"), ("youtube", "YouTube"),
    ("linkedin", "LinkedIn"), ("discord", "Discord"), ("steam", "Steam"),
]
# Formats d'export : clé -> (libellé du bouton, filtre du dialogue, extension)
EXPORT_FORMATS = {
    "html": ("Exporter HTML", "Page HTML (*.html)", "html"),
    "json": ("Exporter JSON", "JSON (*.json)", "json"),
    "csv": ("Exporter CSV", "CSV (*.csv)", "csv"),
    "pdf": ("Exporter PDF", "PDF (*.pdf)", "pdf"),
    "graph": ("Graphe", "Page HTML (*.html)", "html"),
}
STATUS_LABELS = {"": "", "confirmed": "Confirmé", "to_check": "À vérifier", "false_positive": "Faux positif"}
STATUS_COLORS = {"confirmed": "#a6da95", "to_check": "#eed49f", "false_positive": "#6e6c7e"}
COLUMNS = ["Plateforme", "Confiance", "URL", "Titre", "Pseudo", "Indices", "Statut", "Note"]


def _font(size: int = 10, bold: bool = False) -> QFont:
    """Police système (Segoe UI, Cantarell, SF...) avec la taille et le poids voulus."""
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)
    return font


class SortItem(QTableWidgetItem):
    """Cellule triable sur une clé (nombre ou texte en minuscules) et non sur son affichage."""

    def __init__(self, text: str, key) -> None:
        super().__init__(text)
        self._key = key

    def __lt__(self, other) -> bool:
        if isinstance(other, SortItem):
            return self._key < other._key
        return super().__lt__(other)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.engine = EchoTraceEngine()
        self.thread: AnalysisThread | None = None
        # Analyse affichée : cible, finalité, résultats (dicts de la base) et résumé.
        self.target_data: dict = {}
        self.purpose: str = ""
        self.results: list[dict] = []
        self.summary: dict = build_summary([])
        self._targets: list[dict] = []
        self._shown: list[dict] = []
        self._build()
        self.load_history()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setWindowTitle(f"EchoTrace {__version__} - OSINT Correlation Engine")
        self.resize(1250, 820)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_analysis_tab(), "Analyse")
        self.tabs.addTab(self._build_results_tab(), "Résultats")
        self.tabs.addTab(self._build_history_tab(), "Historique")
        layout.addWidget(self.tabs)
        self.statusBar().showMessage("Prêt")

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        row = QHBoxLayout(frame)
        title = QLabel("EchoTrace")
        title.setFont(_font(16, True))
        row.addWidget(title)
        row.addStretch()
        self.score_label = QLabel("Score : 0")
        self.score_label.setFont(_font(12))
        row.addWidget(self.score_label)
        config_btn = QPushButton("Configuration")
        config_btn.clicked.connect(self.open_config)
        row.addWidget(config_btn)
        return frame

    def _build_analysis_tab(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_form())
        splitter.addWidget(self._build_progress_panel())
        splitter.setSizes([700, 450])
        tab = QWidget()
        QVBoxLayout(tab).addWidget(splitter)
        return tab

    def _build_form(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.fields: dict[str, QLineEdit] = {}

        basic = QGroupBox("Informations de base")
        grid = QGridLayout(basic)
        for index, (key, label, placeholder) in enumerate(BASIC_FIELDS):
            row, col = divmod(index, 2)
            grid.addWidget(QLabel(f"{label} :"), row, col * 2)
            edit = self._make_field(key, placeholder)
            if key == "pseudo":
                edit.setToolTip(PSEUDO_TIP)
            grid.addWidget(edit, row, col * 2 + 1)
        layout.addWidget(basic)

        social = QGroupBox("Réseaux sociaux")
        grid = QGridLayout(social)
        for index, (key, label) in enumerate(SOCIAL_FIELDS):
            row, col = divmod(index, 3)
            grid.addWidget(QLabel(f"{label} :"), row, col * 2)
            grid.addWidget(self._make_field(key, key), row, col * 2 + 1)
        layout.addWidget(social)

        layout.addWidget(self._build_photo_box())

        purpose_box = QGroupBox("Finalité de la recherche (obligatoire)")
        purpose_layout = QVBoxLayout(purpose_box)
        self.purpose_combo = QComboBox()
        self.purpose_combo.addItem("— Choisir la finalité —")
        self.purpose_combo.addItems(PURPOSES)
        self.purpose_combo.setToolTip(
            "Le RGPD impose une finalité précise et légitime. Elle est enregistrée avec l'analyse "
            "et rappelée dans les rapports.")
        purpose_layout.addWidget(self.purpose_combo)
        layout.addWidget(purpose_box)

        actions = QHBoxLayout()
        self.score_display = QLabel()
        self.score_display.setFont(_font(10, True))
        actions.addWidget(self.score_display)
        actions.addStretch()
        self.analyze_btn = QPushButton("LANCER L'ANALYSE")
        self.analyze_btn.setObjectName("primary")
        self.analyze_btn.setFont(_font(12, True))
        self.analyze_btn.clicked.connect(self.start_analysis)
        actions.addWidget(self.analyze_btn)
        layout.addLayout(actions)
        layout.addStretch()
        self.update_score()
        return widget

    def _build_photo_box(self) -> QGroupBox:
        box = QGroupBox("Photos de profil (fichiers ou URL, plusieurs possibles)")
        layout = QHBoxLayout(box)
        self.photo_list = QListWidget()
        self.photo_list.setMaximumHeight(90)
        self.photo_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.photo_list)
        buttons = QVBoxLayout()
        for label, slot in (("Ajouter des fichiers", self.add_photo_files),
                            ("Ajouter une URL", self.add_photo_url),
                            ("Retirer", self.remove_photos)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return box

    def _make_field(self, key: str, placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.textChanged.connect(self.update_score)
        self.fields[key] = edit
        return edit

    def _build_progress_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        progress = QGroupBox("Progression")
        box = QVBoxLayout(progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel("En attente...")
        self.stop_btn = QPushButton("Arrêter l'analyse")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_analysis)
        box.addWidget(self.progress_bar)
        box.addWidget(self.progress_label)
        box.addWidget(self.stop_btn)
        layout.addWidget(progress)

        log_group = QGroupBox("Journal")
        box = QVBoxLayout(log_group)
        buttons = QHBoxLayout()
        clear_btn = QPushButton("Vider")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        save_btn = QPushButton("Enregistrer")
        save_btn.clicked.connect(self.save_log)
        buttons.addWidget(clear_btn)
        buttons.addWidget(save_btn)
        buttons.addStretch()
        box.addLayout(buttons)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        box.addWidget(self.log_text)
        layout.addWidget(log_group, 1)
        return widget

    def _build_results_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Recherche :"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("plateforme, URL, titre, pseudo, note...")
        self.search_box.textChanged.connect(self.refresh_results_table)
        filter_row.addWidget(self.search_box, 1)
        filter_row.addWidget(QLabel("Confiance minimale :"))
        self.min_confidence = QDoubleSpinBox()
        self.min_confidence.setRange(0.0, 1.0)
        self.min_confidence.setSingleStep(0.05)
        self.min_confidence.setValue(get_settings().confidence_threshold)
        self.min_confidence.valueChanged.connect(self.refresh_results_table)
        filter_row.addWidget(self.min_confidence)
        self.hide_false = QCheckBox("Masquer les faux positifs")
        self.hide_false.setChecked(True)
        self.hide_false.toggled.connect(self.refresh_results_table)
        filter_row.addWidget(self.hide_false)
        layout.addLayout(filter_row)
        self.results_count_label = QLabel()
        layout.addWidget(self.results_count_label)

        self.results_table = QTableWidget(0, len(COLUMNS))
        self.results_table.setHorizontalHeaderLabels(COLUMNS)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.show_context_menu)
        self.results_table.cellDoubleClicked.connect(self._open_row_url)
        header = self.results_table.horizontalHeader()
        for column in (0, 1, 4, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 5, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_table)

        hint = QLabel("Clic droit : statut, note, copie. Les exports prennent les lignes sélectionnées, "
                      "sinon toutes les lignes affichées (jamais les faux positifs).")
        layout.addWidget(hint)
        buttons = QHBoxLayout()
        open_btn = QPushButton("Ouvrir des liens")
        open_btn.clicked.connect(self.open_links_dialog)
        buttons.addWidget(open_btn)
        buttons.addStretch()
        for key, (label, _filter, _ext) in EXPORT_FORMATS.items():
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, k=key: self.export(k))
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return widget

    def _build_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Double-clic : recharger une analyse. Sélectionnez-en deux pour les comparer."))
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Libellé", "Finalité", "Score", "Résultats"])
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history_table.cellDoubleClicked.connect(self.open_history_item)
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (0, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.history_table)

        buttons = QHBoxLayout()
        for label, slot in (("Rafraîchir", self.load_history), ("Comparer deux analyses", self.compare_selected),
                            ("Supprimer la sélection", self.delete_history_items)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        for label, slot in (("Exporter toutes mes données", self.export_all_data),
                            ("Tout effacer", self.erase_all_data)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return widget

    # ── Formulaire et score ──────────────────────────────────────────────────

    def photos(self) -> list[str]:
        return [self.photo_list.item(i).text() for i in range(self.photo_list.count())]

    def get_target_data(self) -> dict:
        data = {key: edit.text().strip() for key, edit in self.fields.items() if edit.text().strip()}
        photos = self.photos()
        if photos:
            data["photo"] = "\n".join(photos)
        return data

    def update_score(self) -> None:
        score = compute_input_score(self.get_target_data())
        minimum = get_settings().min_score_required
        self.score_display.setText(f"Score : {score}/{minimum}")
        self.score_label.setText(f"Score : {score}")
        color = "#a6da95" if score >= minimum else "#eed49f" if score >= minimum / 2 else "#ed8796"
        self.score_display.setStyleSheet(f"color: {color};")

    def _add_photos(self, sources: list[str]) -> None:
        existing = set(self.photos())
        for source in split_photos(sources):
            if source not in existing:
                self.photo_list.addItem(QListWidgetItem(source))
        self.update_score()

    def add_photo_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Sélectionner des photos", "", "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        self._add_photos(paths)

    def add_photo_url(self) -> None:
        url, ok = QInputDialog.getText(self, "Photo en ligne", "URL de l'image :")
        if ok and url.strip():
            if not url.strip().startswith(("http://", "https://")):
                QMessageBox.warning(self, "URL", "L'URL doit commencer par http:// ou https://.")
                return
            self._add_photos([url.strip()])

    def remove_photos(self) -> None:
        for item in self.photo_list.selectedItems():
            self.photo_list.takeItem(self.photo_list.row(item))
        self.update_score()

    # ── Analyse ──────────────────────────────────────────────────────────────

    def start_analysis(self) -> None:
        data = self.get_target_data()
        valid, _score, message = is_input_valid(data)
        if not valid:
            QMessageBox.warning(self, "Validation", message)
            return
        if self.purpose_combo.currentIndex() == 0:
            QMessageBox.warning(self, "Finalité requise",
                                "Choisissez la finalité de la recherche avant de lancer l'analyse.")
            return

        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyse en cours...")
        self.stop_btn.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        # Les résultats s'affichent au fil de l'eau : on repart d'un tableau vide.
        self.show_results(data, [], self.purpose_combo.currentText())
        self.tabs.setCurrentIndex(0)

        self.thread = AnalysisThread(self.engine, data, self.purpose_combo.currentText())
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.results_found.connect(self.add_live_results)
        self.thread.analysis_finished.connect(self.analysis_completed)
        self.thread.error_occurred.connect(self.analysis_error)
        self.thread.start()

    def stop_analysis(self) -> None:
        if self.thread is not None:
            self.stop_btn.setEnabled(False)
            self.log_text.append("Arrêt demandé...")
            self.thread.stop()

    def _analysis_ended(self) -> None:
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("LANCER L'ANALYSE")
        self.stop_btn.setEnabled(False)

    def update_progress(self, message: str, percent: float) -> None:
        self.progress_bar.setValue(int(percent))
        self.progress_label.setText(message)
        self.log_text.append(f"[{int(percent)}%] {message}")
        self.statusBar().showMessage(message)

    def add_live_results(self, rows: list) -> None:
        """Ajoute les résultats d'un module dès qu'il a terminé (avant la vérification des profils)."""
        self.results.extend(rows)
        self.refresh_results_table()

    def analysis_completed(self, result: dict) -> None:
        self._analysis_ended()
        if not result["success"]:
            self.log_text.append(f"Erreur : {result['error']}")
            QMessageBox.critical(self, "Erreur", result["error"])
            return

        state = "interrompue" if result.get("cancelled") else "terminée"
        self.log_text.append(f"\nAnalyse {state} en {result['duration']:.1f}s : "
                             f"{result['results_count']} résultat(s), {result['modules_run']} module(s).")
        for module, error in result.get("errors", {}).items():
            self.log_text.append(f"Module {module} en erreur : {error}")
        diff = result.get("diff")
        if diff is not None:
            self.log_text.append(f"\nDepuis l'analyse précédente de cette cible :\n{format_diff(diff)}")
            if diff.appeared:
                self.statusBar().showMessage(f"{len(diff.appeared)} nouveau(x) résultat(s) depuis la dernière analyse")

        # On remplace les lignes provisoires par celles de la base (confiances mises à jour).
        self.show_results(result["target"], result["results"], result["purpose"])
        self.load_history()
        self.tabs.setCurrentIndex(1)

    def analysis_error(self, message: str) -> None:
        self._analysis_ended()
        self.log_text.append(f"Erreur : {message}")
        QMessageBox.critical(self, "Erreur", f"Erreur lors de l'analyse :\n{message}")

    # ── Résultats ────────────────────────────────────────────────────────────

    def show_results(self, target_data: dict, results: list[dict], purpose: str = "") -> None:
        self.target_data = target_data
        self.purpose = purpose
        self.results = results
        self.refresh_results_table()

    def visible_results(self) -> list[dict]:
        minimum = self.min_confidence.value()
        needle = self.search_box.text().strip().lower()
        rows = []
        for r in self.results:
            if r["confidence"] < minimum:
                continue
            if self.hide_false.isChecked() and r.get("status") == "false_positive":
                continue
            haystack = " ".join(str(r.get(k, "")) for k in ("platform", "url", "title", "username", "note")).lower()
            if needle and needle not in haystack:
                continue
            rows.append(r)
        return rows

    def refresh_results_table(self) -> None:
        rows = self.visible_results()
        self._shown = rows  # le tableau ne stocke que l'indice : Qt copierait un dict au lieu de le partager
        self.summary = build_summary(rows)
        table = self.results_table
        table.setSortingEnabled(False)  # pendant le remplissage, sinon les lignes se réordonnent
        table.setRowCount(len(rows))
        for index, result in enumerate(rows):
            self._fill_row(index, result)
        table.setSortingEnabled(True)
        self.results_count_label.setText(
            f"{len(rows)}/{len(self.results)} résultat(s) affiché(s) — "
            f"{self.summary['high_confidence']} à haute confiance")

    def _fill_row(self, index: int, result: dict) -> None:
        label, color = confidence_label(result["confidence"])
        data = result.get("data") or {}
        signals = ", ".join(data.get("signals", []))
        if not signals and data.get("verifiable") is False:
            signals = "profil non vérifiable"
        status = result.get("status", "")

        confidence_item = SortItem(f"{result['confidence']:.2f} ({label})", result["confidence"])
        confidence_item.setBackground(QColor(color))
        confidence_item.setForeground(QColor("#1e1f2e"))
        platform_item = SortItem(result["platform"], result["platform"].lower())
        platform_item.setData(Qt.ItemDataRole.UserRole, index)  # indice dans self._shown
        url_item = SortItem(result["url"], result["url"].lower())
        status_item = SortItem(STATUS_LABELS.get(status, ""), status)
        if status in STATUS_COLORS:
            status_item.setForeground(QColor(STATUS_COLORS[status]))
        items = [platform_item, confidence_item, url_item,
                 SortItem(result["title"], result["title"].lower()),
                 SortItem(result["username"], result["username"].lower()),
                 SortItem(signals, signals.lower()), status_item,
                 SortItem(result.get("note", ""), result.get("note", "").lower())]
        for column, item in enumerate(items):
            self.results_table.setItem(index, column, item)

    def _selected_results(self) -> list[dict]:
        rows = sorted({i.row() for i in self.results_table.selectedItems()})
        return [self._result_at(row) for row in rows]

    def _result_at(self, row: int) -> dict:
        """Résultat affiché sur une ligne du tableau (qui peut être trié)."""
        return self._shown[self.results_table.item(row, 0).data(Qt.ItemDataRole.UserRole)]

    @staticmethod
    def _is_web_url(url: str) -> bool:
        return url.startswith(("http://", "https://"))

    def _open_row_url(self, row: int, _column: int) -> None:
        result = self._result_at(row)
        if self._is_web_url(result["url"]):
            webbrowser.open(result["url"])

    def show_context_menu(self, position) -> None:
        selected = self._selected_results()
        if not selected:
            return
        menu = QMenu(self)
        for status, label in (("confirmed", "Marquer confirmé"), ("to_check", "Marquer à vérifier"),
                              ("false_positive", "Marquer faux positif (ne plus proposer)"),
                              ("", "Retirer le statut")):
            menu.addAction(label, lambda s=status: self.set_status(selected, s))
        menu.addSeparator()
        menu.addAction("Ajouter une note...", lambda: self.edit_note(selected))
        menu.addAction("Copier l'URL", lambda: self.copy_urls(selected))
        menu.exec(self.results_table.viewport().mapToGlobal(position))

    def set_status(self, results: list[dict], status: str) -> None:
        for result in results:
            if "id" in result:
                db.set_result_review(result["id"], status=status)
            result["status"] = status
        self.refresh_results_table()

    def edit_note(self, results: list[dict]) -> None:
        note, ok = QInputDialog.getText(self, "Note", "Note (laisser vide pour effacer) :",
                                        text=results[0].get("note", ""))
        if not ok:
            return
        for result in results:
            if "id" in result:
                db.set_result_review(result["id"], note=note.strip())
            result["note"] = note.strip()
        self.refresh_results_table()

    @staticmethod
    def copy_urls(results: list[dict]) -> None:
        QGuiApplication.clipboard().setText("\n".join(r["url"] for r in results if r["url"]))

    def open_links_dialog(self) -> None:
        links = [(r["platform"], r["url"]) for r in self.visible_results() if self._is_web_url(r["url"])]
        if not links:
            QMessageBox.information(self, "Liens", "Aucun lien à ouvrir.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Liens à ouvrir")
        dialog.resize(650, 500)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Cochez les liens à ouvrir dans le navigateur :"))
        link_list = QListWidget()
        for platform, url in links:
            item = QListWidgetItem(f"{platform} : {url}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, url)
            link_list.addItem(item)
        layout.addWidget(link_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        for text, state in (("Tout cocher", Qt.CheckState.Checked), ("Tout décocher", Qt.CheckState.Unchecked)):
            button = QPushButton(text)
            button.clicked.connect(lambda _c=False, s=state: self._set_all(link_list, s))
            buttons.addButton(button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        urls = [link_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(link_list.count())
                if link_list.item(i).checkState() == Qt.CheckState.Checked]
        if len(urls) > 10 and QMessageBox.question(
                self, "Confirmation", f"Ouvrir {len(urls)} onglets ?") != QMessageBox.StandardButton.Yes:
            return
        for url in urls:
            webbrowser.open(url)  # utilise le navigateur par défaut de chaque système
        self.log_text.append(f"{len(urls)} lien(s) ouvert(s).")

    @staticmethod
    def _set_all(link_list: QListWidget, state: Qt.CheckState) -> None:
        for index in range(link_list.count()):
            link_list.item(index).setCheckState(state)

    # ── Export ───────────────────────────────────────────────────────────────

    def exportable_results(self) -> list[dict]:
        """Lignes sélectionnées, sinon lignes affichées ; les faux positifs ne sortent jamais."""
        rows = self._selected_results() or self.visible_results()
        return [r for r in rows if r.get("status") != "false_positive"]

    def export(self, kind: str) -> None:
        results = self.exportable_results()
        if not results:
            QMessageBox.information(self, "Export", "Aucun résultat à exporter.")
            return

        _label, file_filter, extension = EXPORT_FORMATS[kind]
        default = get_settings().export_path / f"echotrace_{kind}_{datetime.now():%Y%m%d_%H%M%S}.{extension}"
        chosen, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'export", str(default), file_filter)
        if not chosen:
            return

        path = Path(chosen)
        generator = ReportGenerator(path.parent)
        summary = build_summary(results)
        target, purpose = self.target_data, self.purpose
        try:
            written = {
                "html": lambda: generator.generate_html_report(target, results, summary, path.name, purpose),
                "json": lambda: generator.generate_json_report(target, results, summary, path.name, purpose),
                "csv": lambda: generator.generate_csv_report(results, path.name),
                "pdf": lambda: generator.generate_pdf_report(target, results, summary, path.name, purpose),
                "graph": lambda: generator.generate_network_graph(results, path.name),
            }[kind]()
        except Exception as exc:
            log.exception("Échec de l'export %s", kind)
            QMessageBox.critical(self, "Erreur d'export", f"Export impossible :\n{exc}")
            return

        if not written:
            QMessageBox.information(self, "Graphe", "Aucun lien pseudo/plateforme à représenter.")
            return
        self.log_text.append(f"Export enregistré : {written}")
        self.statusBar().showMessage(f"Export enregistré : {written}")

    # ── Historique ───────────────────────────────────────────────────────────

    def load_history(self) -> None:
        try:
            self._targets = db.list_targets()
        except Exception as exc:
            log.exception("Lecture de l'historique impossible")
            QMessageBox.critical(self, "Erreur", f"Historique illisible : {exc}")
            return
        self.history_table.setRowCount(len(self._targets))
        for row, target in enumerate(self._targets):
            date = datetime.fromtimestamp(target["created_at"]).strftime("%Y-%m-%d %H:%M")
            values = (date, target["label"] or "Sans nom", target.get("purpose", ""),
                      target["input_score"], target["results_count"])
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _selected_targets(self) -> list[dict]:
        rows = sorted({i.row() for i in self.history_table.selectedItems()})
        return [self._targets[row] for row in rows if 0 <= row < len(self._targets)]

    def open_history_item(self, row: int, _column: int) -> None:
        target = self._targets[row]
        self.show_results(target["data"], db.get_results(target["id"]), target.get("purpose", ""))
        self.tabs.setCurrentIndex(1)

    def compare_selected(self) -> None:
        selected = self._selected_targets()
        if len(selected) != 2:
            QMessageBox.information(self, "Comparer", "Sélectionnez exactement deux analyses.")
            return
        older, newer = sorted(selected, key=lambda t: t["id"])
        diff = diff_results(db.get_results(older["id"]), db.get_results(newer["id"]))
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{older['label']} : analyse du {datetime.fromtimestamp(older['created_at']):%d/%m/%Y} "
                              f"→ {datetime.fromtimestamp(newer['created_at']):%d/%m/%Y}")
        dialog.resize(800, 550)
        layout = QVBoxLayout(dialog)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(format_diff(diff))
        layout.addWidget(view)
        close = QPushButton("Fermer")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def delete_history_items(self) -> None:
        selected = self._selected_targets()
        if not selected:
            return
        if QMessageBox.question(
                self, "Supprimer", f"Supprimer {len(selected)} analyse(s) et leurs résultats ?"
        ) != QMessageBox.StandardButton.Yes:
            return
        for target in selected:
            db.delete_target(target["id"])
        self.load_history()

    def export_all_data(self) -> None:
        """Droit d'accès : toutes les données stockées par l'application, en un fichier JSON."""
        default = get_settings().export_path / f"echotrace_mes_donnees_{datetime.now():%Y%m%d}.json"
        chosen, _ = QFileDialog.getSaveFileName(self, "Exporter toutes les données", str(default), "JSON (*.json)")
        if not chosen:
            return
        try:
            Path(chosen).write_text(
                json.dumps(db.export_everything(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Erreur", f"Export impossible : {exc}")
            return
        self.statusBar().showMessage(f"Données exportées : {chosen}")

    def erase_all_data(self) -> None:
        """Droit à l'effacement : supprime analyses, résultats, faux positifs et cache."""
        if QMessageBox.question(
                self, "Tout effacer",
                "Supprimer définitivement toutes les analyses, résultats, notes et le cache ?\n"
                "Cette action est irréversible."
        ) != QMessageBox.StandardButton.Yes:
            return
        db.erase_everything()
        self.show_results({}, [], "")
        self.load_history()
        self.statusBar().showMessage("Toutes les données ont été effacées")

    # ── Divers ───────────────────────────────────────────────────────────────

    def save_log(self) -> None:
        default = f"echotrace_log_{datetime.now():%Y%m%d_%H%M%S}.txt"
        chosen, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le journal", str(get_settings().export_path / default), "Texte (*.txt)")
        if not chosen:
            return
        try:
            Path(chosen).write_text(self.log_text.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Erreur", f"Enregistrement impossible : {exc}")

    def open_config(self) -> None:
        settings = get_settings()
        if ConfigDialog(settings, self).exec() == QDialog.DialogCode.Accepted:
            try:
                settings.save()
            except OSError as exc:
                QMessageBox.critical(self, "Erreur", f"Configuration non enregistrée : {exc}")
                return
            self.min_confidence.setValue(settings.confidence_threshold)
            self.update_score()
            self.statusBar().showMessage("Configuration enregistrée")

    def closeEvent(self, event) -> None:
        # Évite de détruire un QThread encore actif à la fermeture.
        if self.thread is not None and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(5000)
        super().closeEvent(event)
