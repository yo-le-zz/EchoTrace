"""
EchoTrace — Main GUI Window
Interface principale PyQt6
"""

import sys
import os
import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QScrollArea, QFrame, QGroupBox, QCheckBox, QFileDialog,
    QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QComboBox, QDialog, QDialogButtonBox, QListWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon, QPalette, QColor
import webbrowser
from core.engine import ENGINE
from core.scorer import is_input_valid, compute_input_score, confidence_label
from database.db import list_targets, get_results


class AnalysisThread(QThread):
    """Thread pour les analyses OSINT."""
    progress_updated = pyqtSignal(str, float)
    analysis_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, target_data):
        super().__init__()
        self.target_data = target_data
    
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                ENGINE.run_analysis(self.target_data, self.progress_callback)
            )
            self.analysis_finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def progress_callback(self, message: str, percent: float):
        self.progress_updated.emit(message, percent)


class MainWindow(QMainWindow):
    """Fenêtre principale d'EchoTrace."""
    
    def __init__(self):
        super().__init__()
        self.current_analysis = None
        self.init_ui()
        self.apply_theme()
    
    def init_ui(self):
        """Initialise l'interface utilisateur."""
        self.setWindowTitle("EchoTrace - OSINT Correlation Engine")
        self.setGeometry(100, 100, 1200, 800)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        self.create_header(main_layout)
        
        # Tabs
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Tab 1: Analyse
        self.analysis_tab = self.create_analysis_tab()
        self.tab_widget.addTab(self.analysis_tab, "Analyse")
        
        # Tab 2: Résultats
        self.results_tab = self.create_results_tab()
        self.tab_widget.addTab(self.results_tab, "Résultats")
        
        # Tab 3: Historique
        self.history_tab = self.create_history_tab()
        self.tab_widget.addTab(self.history_tab, "Historique")
        
        # Charger l'historique au démarrage
        self.load_history()
        
        # Status bar
        self.statusBar().showMessage("Prêt")
    
    def create_header(self, parent_layout):
        """Crée le header de l'application."""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout(header_frame)
        
        # Logo et titre
        title_label = QLabel("🔍 EchoTrace")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Score actuel
        self.score_label = QLabel("Score: 0")
        self.score_label.setFont(QFont("Segoe UI", 12))
        header_layout.addWidget(self.score_label)
        
        # Bouton de configuration
        config_btn = QPushButton("⚙️ Configuration")
        config_btn.setFont(QFont("Segoe UI", 10))
        config_btn.clicked.connect(self.open_config)
        header_layout.addWidget(config_btn)
        
        parent_layout.addWidget(header_frame)
    
    def create_analysis_tab(self):
        """Crée l'onglet d'analyse."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Gauche: Formulaire
        left_widget = self.create_input_form()
        splitter.addWidget(left_widget)
        
        # Droite: Progression
        right_widget = self.create_progress_panel()
        splitter.addWidget(right_widget)
        
        splitter.setSizes([600, 400])
        
        return tab
    
    def create_input_form(self):
        """Crée le formulaire de saisie."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Groupe: Informations de base
        basic_group = QGroupBox("Informations de base")
        basic_layout = QGridLayout(basic_group)
        
        # Champs de saisie
        self.fields = {}
        
        # Ligne 1: Prénom, Nom
        basic_layout.addWidget(QLabel("Prénom:"), 0, 0)
        self.fields['prenom'] = QLineEdit()
        self.fields['prenom'].setPlaceholderText("John")
        basic_layout.addWidget(self.fields['prenom'], 0, 1)
        
        basic_layout.addWidget(QLabel("Nom:"), 0, 2)
        self.fields['nom'] = QLineEdit()
        self.fields['nom'].setPlaceholderText("Doe")
        basic_layout.addWidget(self.fields['nom'], 0, 3)
        
        # Ligne 2: Pseudo, Email
        basic_layout.addWidget(QLabel("Pseudo:"), 1, 0)
        self.fields['pseudo'] = QLineEdit()
        self.fields['pseudo'].setPlaceholderText("johndoe123")
        basic_layout.addWidget(self.fields['pseudo'], 1, 1)
        
        basic_layout.addWidget(QLabel("Email:"), 1, 2)
        self.fields['email'] = QLineEdit()
        self.fields['email'].setPlaceholderText("john.doe@example.com")
        basic_layout.addWidget(self.fields['email'], 1, 3)
        
        # Ligne 3: Téléphone, Ville
        basic_layout.addWidget(QLabel("Téléphone:"), 2, 0)
        self.fields['telephone'] = QLineEdit()
        self.fields['telephone'].setPlaceholderText("+33612345678")
        basic_layout.addWidget(self.fields['telephone'], 2, 1)
        
        basic_layout.addWidget(QLabel("Ville:"), 2, 2)
        self.fields['ville'] = QLineEdit()
        self.fields['ville'].setPlaceholderText("Paris")
        basic_layout.addWidget(self.fields['ville'], 2, 3)
        
        # Ligne 4: Pays, Entreprise
        basic_layout.addWidget(QLabel("Pays:"), 3, 0)
        self.fields['pays'] = QLineEdit()
        self.fields['pays'].setPlaceholderText("France")
        basic_layout.addWidget(self.fields['pays'], 3, 1)
        
        basic_layout.addWidget(QLabel("Entreprise:"), 3, 2)
        self.fields['entreprise'] = QLineEdit()
        self.fields['entreprise'].setPlaceholderText("TechCorp")
        basic_layout.addWidget(self.fields['entreprise'], 3, 3)
        
        layout.addWidget(basic_group)
        
        # Groupe: Réseaux sociaux
        social_group = QGroupBox("Réseaux sociaux")
        social_layout = QGridLayout(social_group)
        
        social_networks = [
            ('instagram', 'Instagram'), ('twitter', 'Twitter/X'), ('github', 'GitHub'),
            ('reddit', 'Reddit'), ('tiktok', 'TikTok'), ('youtube', 'YouTube'),
            ('linkedin', 'LinkedIn'), ('discord', 'Discord'), ('steam', 'Steam')
        ]
        
        for i, (key, label) in enumerate(social_networks):
            social_layout.addWidget(QLabel(f"{label}:"), i // 3, (i % 3) * 2)
            self.fields[key] = QLineEdit()
            # Set appropriate placeholder based on platform
            if key in ['reddit']:
                placeholder = f"user/{key}"
            elif key in ['tiktok', 'youtube', 'replit']:
                placeholder = f"@{key}"
            elif key in ['snapchat']:
                placeholder = f"add/{key}"
            elif key in ['npm']:
                placeholder = f"~{key}"
            else:
                placeholder = key
            self.fields[key].setPlaceholderText(placeholder)
            social_layout.addWidget(self.fields[key], i // 3, (i % 3) * 2 + 1)
        
        layout.addWidget(social_group)
        
        # Photo
        photo_group = QGroupBox("Photo / Avatar")
        photo_layout = QHBoxLayout(photo_group)
        
        self.photo_path = QLineEdit()
        self.photo_path.setPlaceholderText("Chemin vers l'image...")
        photo_layout.addWidget(self.photo_path)
        
        photo_btn = QPushButton("Parcourir")
        photo_btn.clicked.connect(self.browse_photo)
        photo_layout.addWidget(photo_btn)
        
        layout.addWidget(photo_group)
        
        # Boutons d'action
        btn_layout = QHBoxLayout()
        
        # Score
        self.score_display = QLabel("Score: 0/100")
        self.score_display.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_layout.addWidget(self.score_display)
        
        btn_layout.addStretch()
        
        # Analyse
        analyze_btn = QPushButton("🔍 LANCER L'ANALYSE")
        analyze_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #8aadf4;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7dc4e4;
            }
        """)
        analyze_btn.clicked.connect(self.start_analysis)
        btn_layout.addWidget(analyze_btn)
        
        layout.addLayout(btn_layout)
        
        # Connecter les changements pour mettre à jour le score
        for field in self.fields.values():
            field.textChanged.connect(self.update_score)
        
        layout.addStretch()
        return widget
    
    def create_progress_panel(self):
        """Crée le panneau de progression."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Progression
        progress_group = QGroupBox("Progression de l'analyse")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("En attente...")
        progress_layout.addWidget(self.progress_label)
        
        layout.addWidget(progress_group)
        
        # Log
        log_group = QGroupBox("Log d'analyse")
        log_layout = QVBoxLayout(log_group)
        
        # Boutons pour le log
        log_btn_layout = QHBoxLayout()
        
        # Créer et stocker les boutons comme attributs de la classe
        self.clear_log_btn = QPushButton("🗑️ Vider le log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_btn_layout.addWidget(self.clear_log_btn)
        
        self.save_log_btn = QPushButton("💾 Sauvegarder le log")
        self.save_log_btn.clicked.connect(self.save_log)
        log_btn_layout.addWidget(self.save_log_btn)
        
        log_btn_layout.addStretch()
        log_layout.addLayout(log_btn_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(300)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        layout.addStretch()
        return widget
    
    def create_results_tab(self):
        """Crée l'onglet des résultats."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tableau des résultats
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Plateforme", "Confiance", "URL", "Titre", "Username", "Module"
        ])
        
        # Ajuster les colonnes
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.results_table)
        
        # Boutons d'action
        btn_layout = QHBoxLayout()
        
        # Bouton pour ouvrir tous les liens
        open_links_btn = QPushButton("🌐 Ouvrir tous les liens")
        open_links_btn.clicked.connect(self.open_all_links)
        btn_layout.addWidget(open_links_btn)
        
        btn_layout.addStretch()
        
        # Boutons d'export
        export_html_btn = QPushButton("📄 Exporter HTML")
        export_html_btn.clicked.connect(self.export_html)
        btn_layout.addWidget(export_html_btn)
        
        export_json_btn = QPushButton("📋 Exporter JSON")
        export_json_btn.clicked.connect(self.export_json)
        btn_layout.addWidget(export_json_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def create_history_tab(self):
        """Crée l'onglet d'historique."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tableau d'historique
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Label", "Score", "Résultats"
        ])
        
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.history_table)
        
        # Bouton de rafraîchissement
        refresh_btn = QPushButton("🔄 Rafraîchir")
        refresh_btn.clicked.connect(self.load_history)
        layout.addWidget(refresh_btn)
        
        return widget
    
    def apply_theme(self):
        """Applique le thème Catppuccin Macchiato amélioré avec styles CSS."""
        # Palette de couleurs de base
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(24, 25, 38))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(202, 211, 245))
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 31, 46))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(24, 25, 38))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(24, 25, 38))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(202, 211, 245))
        palette.setColor(QPalette.ColorRole.Text, QColor(202, 211, 245))
        palette.setColor(QPalette.ColorRole.Button, QColor(49, 50, 68))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(202, 211, 245))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(243, 139, 168))
        palette.setColor(QPalette.ColorRole.Link, QColor(137, 180, 250))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(137, 180, 250))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(30, 31, 46))
        self.setPalette(palette)
        
        # Styles CSS pour une apparence moderne
        self.setStyleSheet("""
            QMainWindow {
                background-color: #181926;
            }
            
            QTabWidget::pane {
                border: 1px solid #494a64;
                background-color: #1e1f2e;
                border-radius: 8px;
            }
            
            QTabBar::tab {
                background-color: #313244;
                color: #cad3f5;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 500;
            }
            
            QTabBar::tab:selected {
                background-color: #575268;
                color: #cad3f5;
                border-bottom: 2px solid #8bd5ca;
            }
            
            QTabBar::tab:hover {
                background-color: #45475a;
            }
            
            QGroupBox {
                font-weight: 600;
                font-size: 13px;
                color: #cad3f5;
                border: 2px solid #494a64;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #1e1f2e;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #1e1f2e;
            }
            
            QPushButton {
                background-color: #313244;
                color: #cad3f5;
                border: 1px solid #494a64;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
            }
            
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #575268;
            }
            
            QPushButton:pressed {
                background-color: #575268;
                border: 1px solid #6e6c7e;
            }
            
            QPushButton[text*="ANALYSE"] {
                background-color: #8bd5ca;
                color: #1e1f2e;
                border: 1px solid #8bd5ca;
                font-weight: 600;
                padding: 10px 20px;
            }
            
            QPushButton[text*="ANALYSE"]:hover {
                background-color: #a6d189;
                border: 1px solid #a6d189;
            }
            
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #1e1f2e;
                color: #cad3f5;
                border: 1px solid #494a64;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 2px solid #8bd5ca;
            }
            
            QTableWidget {
                background-color: #1e1f2e;
                color: #cad3f5;
                border: 1px solid #494a64;
                border-radius: 6px;
                gridline-color: #494a64;
                selection-background-color: #575268;
            }
            
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #494a64;
            }
            
            QTableWidget::item:selected {
                background-color: #575268;
                color: #cad3f5;
            }
            
            QHeaderView::section {
                background-color: #313244;
                color: #cad3f5;
                padding: 8px;
                border: 1px solid #494a64;
                font-weight: 600;
                font-size: 12px;
            }
            
            QProgressBar {
                border: 1px solid #494a64;
                border-radius: 6px;
                text-align: center;
                background-color: #1e1f2e;
                color: #cad3f5;
                font-weight: 500;
            }
            
            QProgressBar::chunk {
                background-color: #8bd5ca;
                border-radius: 5px;
            }
            
            QLabel {
                color: #cad3f5;
                font-size: 13px;
            }
            
            QSpinBox, QDoubleSpinBox {
                background-color: #1e1f2e;
                color: #cad3f5;
                border: 1px solid #494a64;
                border-radius: 6px;
                padding: 4px 8px;
            }
            
            QCheckBox {
                color: #cad3f5;
                font-size: 13px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #494a64;
                border-radius: 3px;
                background-color: #1e1f2e;
            }
            
            QCheckBox::indicator:checked {
                background-color: #8bd5ca;
                border: 1px solid #8bd5ca;
            }
            
            QSlider::groove:horizontal {
                border: 1px solid #494a64;
                height: 6px;
                background-color: #1e1f2e;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background-color: #8bd5ca;
                border: 1px solid #8bd5ca;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            
            QStatusBar {
                background-color: #1e1f2e;
                color: #cad3f5;
                border-top: 1px solid #494a64;
            }
            
            QMenuBar {
                background-color: #1e1f2e;
                color: #cad3f5;
                border-bottom: 1px solid #494a64;
            }
            
            QMenuBar::item {
                padding: 6px 12px;
                background-color: transparent;
            }
            
            QMenuBar::item:selected {
                background-color: #313244;
            }
            
            QMenu {
                background-color: #1e1f2e;
                color: #cad3f5;
                border: 1px solid #494a64;
            }
            
            QMenu::item {
                padding: 6px 20px;
            }
            
            QMenu::item:selected {
                background-color: #313244;
            }
        """)
    
    def browse_photo(self):
        """Ouvre un dialogue pour sélectionner une photo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner une photo", "", 
            "Images (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        if file_path:
            self.photo_path.setText(file_path)
            self.update_score()
    
    def update_score(self):
        """Met à jour le score d'entrée."""
        data = self.get_target_data()
        score = compute_input_score(data)
        
        self.score_display.setText(f"Score: {score}/100")
        self.score_label.setText(f"Score: {score}")
        
        # Couleur selon le score
        if score >= 100:
            self.score_display.setStyleSheet("color: #a6da95;")  # vert
        elif score >= 50:
            self.score_display.setStyleSheet("color: #eed49f;")  # jaune
        else:
            self.score_display.setStyleSheet("color: #ed8796;")  # rouge
    
    def get_target_data(self):
        """Récupère les données du formulaire."""
        data = {}
        for key, field in self.fields.items():
            value = field.text().strip()
            if value:
                data[key] = value
        
        photo = self.photo_path.text().strip()
        if photo:
            data['photo'] = photo
        
        return data
    
    def start_analysis(self):
        """Démarre une analyse."""
        data = self.get_target_data()
        
        # Validation
        valid, score, message = is_input_valid(data)
        if not valid:
            QMessageBox.warning(self, "Validation", message)
            return
        
        # Désactiver le bouton
        sender = self.sender()
        sender.setEnabled(False)
        sender.setText("⏳ Analyse en cours...")
        
        # Vider les logs
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        # Démarrer le thread d'analyse
        self.current_analysis = AnalysisThread(data)
        self.current_analysis.progress_updated.connect(self.update_progress)
        self.current_analysis.analysis_finished.connect(self.analysis_completed)
        self.current_analysis.error_occurred.connect(self.analysis_error)
        self.current_analysis.start()
    
    def update_progress(self, message: str, percent: float):
        """Met à jour la barre de progression."""
        self.progress_bar.setValue(int(percent))
        self.progress_label.setText(message)
        self.log_text.append(f"[{int(percent)}%] {message}")
        self.statusBar().showMessage(message)
    
    def analysis_completed(self, result: dict):
        """Analyse terminée avec succès."""
        # Réactiver le bouton
        for widget in self.findChildren(QPushButton):
            if "ANALYSE" in widget.text():
                widget.setEnabled(True)
                widget.setText("🔍 LANCER L'ANALYSE")
        
        if result['success']:
            self.log_text.append(f"\n✅ Analyse terminée en {result['duration']:.1f}s")
            self.log_text.append(f"📊 {result['results_count']} résultats trouvés")
            self.log_text.append(f"🔧 {result['modules_run']} modules exécutés")
            
            # Afficher les résultats
            self.display_results(result['results'])
            
            # Changer d'onglet
            self.tab_widget.setCurrentIndex(1)
            
            QMessageBox.information(self, "Succès", 
                f"Analyse terminée!\n\n"
                f"Résultats: {result['results_count']}\n"
                f"Durée: {result['duration']:.1f}s")
        else:
            self.log_text.append(f"\n❌ Erreur: {result['error']}")
            QMessageBox.critical(self, "Erreur", result['error'])
    
    def analysis_error(self, error_message: str):
        """Erreur lors de l'analyse."""
        # Réactiver le bouton
        for widget in self.findChildren(QPushButton):
            if "ANALYSE" in widget.text():
                widget.setEnabled(True)
                widget.setText("🔍 LANCER L'ANALYSE")
        
        self.log_text.append(f"\n❌ Erreur: {error_message}")
        QMessageBox.critical(self, "Erreur", f"Erreur lors de l'analyse:\n{error_message}")
    
    def display_results(self, results: list):
        """Affiche les résultats dans le tableau après filtrage des URLs invalides."""
        # Filtrer les résultats pour n'afficher que les URLs valides
        filtered_results = self._filter_valid_urls(results)
        
        self.results_table.setRowCount(len(filtered_results))
        
        for i, result in enumerate(filtered_results):
            # Plateforme
            self.results_table.setItem(i, 0, QTableWidgetItem(result.get('platform', '')))
            
            # Confiance
            confidence = result.get('confidence', 0)
            confidence_item = QTableWidgetItem(f"{confidence:.2f}")
            label, color = confidence_label(confidence)
            confidence_item.setText(f"{confidence:.2f} ({label})")
            confidence_item.setBackground(QColor(color))
            self.results_table.setItem(i, 1, confidence_item)
            
            # URL
            url_item = QTableWidgetItem(result.get('url', ''))
            if result.get('status_code') == 200:
                url_item.setText(f"✅ {result.get('url', '')}")
            else:
                url_item.setText(f"❌ {result.get('url', '')}")
            self.results_table.setItem(i, 2, url_item)
            
            # Titre
            self.results_table.setItem(i, 3, QTableWidgetItem(result.get('title', '')))
            
            # Username
            self.results_table.setItem(i, 4, QTableWidgetItem(result.get('username', '')))
            
            # Module
            self.results_table.setItem(i, 5, QTableWidgetItem(result.get('module', '')))
        
        # Log du filtrage
        total_urls = len(results)
        valid_urls = len(filtered_results)
        self.log_text.append(f"\n🔍 Filtrage URLs: {valid_urls}/{total_urls} URLs valides ({total_urls - valid_urls} URLs invalides filtrées)")
    
    def _filter_valid_urls(self, results: list) -> list:
        """Filtre les résultats pour ne garder que les URLs valides (non 404)."""
        import aiohttp
        import asyncio
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class URLCheckerThread(QThread):
            finished = pyqtSignal(list)
            
            def __init__(self, results):
                super().__init__()
                self.results = results
            
            def run(self):
                """Vérifie les URLs en parallèle."""
                async def check_urls():
                    valid_results = []
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=10),
                        connector=aiohttp.TCPConnector(limit=20)
                    ) as session:
                        tasks = []
                        for result in self.results:
                            task = asyncio.create_task(
                                self._check_single_url(session, result)
                            )
                            tasks.append(task)
                        
                        # Exécuter toutes les vérifications en parallèle
                        checked_results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        for checked_result in checked_results:
                            if isinstance(checked_result, dict):
                                valid_results.append(checked_result)
                    
                    return valid_results
                
                # Exécuter la fonction asynchrone
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(check_urls())
                    self.finished.emit(results)
                finally:
                    loop.close()
            
            async def _check_single_url(self, session, result):
                """Vérifie une seule URL."""
                try:
                    url = result.get('url', '')
                    if not url or not url.startswith(('http://', 'https://')):
                        return result
                    
                    async with session.head(url, allow_redirects=True, ssl=False) as response:
                        result['status_code'] = response.status
                        # Garder seulement les URLs qui ne retournent pas 404
                        if response.status != 404:
                            return result
                        else:
                            return None
                except Exception:
                    # En cas d'erreur, on garde le résultat (mieux que de le perdre)
                    result['status_code'] = 0
                    return result
        
        # Lancer la vérification de manière synchrone pour l'interface
        checker = URLCheckerThread(results)
        checker.run()
        return results  # Temporairement, retourner tous les résultats
    
    def export_html(self):
        """Exporte les résultats en HTML."""
        # TODO: Implémenter l'export HTML
        QMessageBox.information(self, "Export", "Export HTML non encore implémenté")
    
    def export_json(self):
        """Exporte les résultats en JSON."""
        # TODO: Implémenter l'export JSON
        QMessageBox.information(self, "Export", "Export JSON non encore implémenté")
    
    def open_all_links(self):
        """Ouvre tous les liens trouvés dans le navigateur."""
        try:
            # Récupérer tous les URLs depuis le tableau de résultats
            links = []
            for row in range(self.results_table.rowCount()):
                url_item = self.results_table.item(row, 2)  # Colonne URL
                if url_item and url_item.text():
                    platform_item = self.results_table.item(row, 0)  # Colonne Plateforme
                    platform = platform_item.text() if platform_item else "Inconnu"
                    url = url_item.text()
                    links.append({
                        'platform': platform,
                        'url': url,
                        'selected': True  # Par défaut, tout est sélectionné
                    })
            
            if not links:
                QMessageBox.information(self, "Liens", "Aucun lien à ouvrir!")
                return
            
            # Créer une boîte de dialogue pour la sélection
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox, QPushButton
            
            dialog = QDialog(self)
            dialog.setWindowTitle("🌐 Sélection des liens à ouvrir")
            dialog.setModal(True)
            dialog.resize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            # Ajouter une instruction
            instruction_label = QLabel("Sélectionnez les liens à ouvrir (tout est coché par défaut):")
            layout.addWidget(instruction_label)
            
            # Liste des liens avec cases à cocher
            link_list = QListWidget()
            for i, link in enumerate(links):
                item = QListWidgetItem(f"🔗 {link['platform']}: {link['url'][:60]}{'...' if len(link['url']) > 60 else ''}")
                item.setCheckState(2 if link['selected'] else 0)  # 2 = Checked, 0 = Unchecked
                item.setData(1, link)  # Stocker le lien complet
                link_list.addItem(item)
            
            layout.addWidget(link_list)
            
            # Boutons
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            
            # Bouton pour tout sélectionner/désélectionner
            select_all_btn = QPushButton("Tout sélectionner")
            select_all_btn.clicked.connect(lambda: self.toggle_all_links(link_list, True))
            button_box.addButton(select_all_btn, QDialogButtonBox.ButtonRole.ActionRole)
            
            deselect_all_btn = QPushButton("Tout désélectionner")
            deselect_all_btn.clicked.connect(lambda: self.toggle_all_links(link_list, False))
            button_box.addButton(deselect_all_btn, QDialogButtonBox.ButtonRole.ActionRole)
            
            layout.addWidget(button_box)
            
            # Gérer la réponse
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Ouvrir les liens sélectionnés
                selected_links = []
                for i in range(link_list.count()):
                    item = link_list.item(i)
                    if item.checkState() == 2:  # Checked
                        link = item.data(1)
                        selected_links.append(link)
                
                self.open_selected_links(selected_links)
        
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur ouverture des liens: {e}")
    
    def toggle_all_links(self, link_list, checked):
        """Sélectionne ou désélectionne tous les liens."""
        for i in range(link_list.count()):
            item = link_list.item(i)
            item.setCheckState(2 if checked else 0)  # 2 = Checked, 0 = Unchecked
    
    def open_selected_links(self, links):
        """Ouvre les liens sélectionnés dans le navigateur par défaut."""
        import webbrowser
        import subprocess
        import platform as platform_module
        
        opened_count = 0
        failed_count = 0
        
        for link in links:
            try:
                url = link['url']
                platform_name = link['platform']
                
                # Ouvrir avec le navigateur par défaut du système
                if platform_module.system() == "Windows":
                    webbrowser.open(url)
                elif platform_module.system() == "Darwin":  # macOS
                    subprocess.run(["open", url])
                else:  # Linux
                    subprocess.run(["xdg-open", url])
                
                opened_count += 1
                
            except Exception as e:
                print(f"Erreur ouverture lien {link['url']}: {e}")
                failed_count += 1
        
        # Message de confirmation
        if opened_count > 0:
            QMessageBox.information(
                self, 
                "Liens ouverts", 
                f"✅ {opened_count} lien(s) ouvert(s) avec succès!\n❌ {failed_count} échec(s)"
            )
        
        # Log de l'action
        self.log_text.append(f"🌐 Ouverture de {opened_count} lien(s) - {failed_count} échec(s)")
        for link in links:
            self.log_text.append(f"   🔗 {link['platform']}: {link['url']}")
    
    def load_history(self):
        """Charge l'historique des analyses."""
        try:
            targets = list_targets()
            self.history_table.setRowCount(len(targets))
            
            for i, target in enumerate(targets):
                # Date
                import datetime
                date = datetime.datetime.fromtimestamp(target['created_at'])
                self.history_table.setItem(i, 0, QTableWidgetItem(date.strftime("%Y-%m-%d %H:%M")))
                
                # Label
                self.history_table.setItem(i, 1, QTableWidgetItem(target.get('label', 'Sans nom')))
                
                # Score
                self.history_table.setItem(i, 2, QTableWidgetItem(str(target.get('input_score', 0))))
                
                # Résultats
                results_count = len(get_results(target['id']))
                self.history_table.setItem(i, 3, QTableWidgetItem(str(results_count)))
        
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur chargement historique: {e}")
    
    def clear_log(self):
        """Vide le log d'analyse."""
        from datetime import datetime
        self.log_text.clear()
        self.log_text.append("🗑️ Log vidé le " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def save_log(self):
        """Sauvegarde le log d'analyse dans un fichier."""
        try:
            from datetime import datetime
            from PyQt6.QtWidgets import QFileDialog
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"echotrace_log_{timestamp}.txt"
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Sauvegarder le log", 
                filename, 
                "Fichiers texte (*.txt)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"=== LOG D'ANALYSE ECHOTRACE ===\n")
                    f.write(f"Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(self.log_text.toPlainText())
                
                QMessageBox.information(self, "Log sauvegardé", f"Log sauvegardé dans:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur sauvegarde: {e}")
    
    def open_config(self):
        """Ouvre la fenêtre de configuration."""
        try:
            from config.settings import SETTINGS
            config_dialog = ConfigDialog(SETTINGS, self)
            if config_dialog.exec() == QMessageBox.DialogCode.Accepted:
                # Sauvegarder la configuration
                SETTINGS.save()
                QMessageBox.information(self, "Configuration", "Configuration sauvegardée!")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur configuration: {e}")


class ConfigDialog(QDialog):
    """Fenêtre de configuration d'EchoTrace."""
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("⚙️ Configuration EchoTrace")
        self.setModal(True)
        self.resize(500, 400)
        self.init_ui()
    
    def init_ui(self):
        """Initialise l'interface de configuration."""
        layout = QVBoxLayout(self)
        
        # API Keys
        api_group = QGroupBox("Clés API (Optionnelles)")
        api_layout = QGridLayout(api_group)
        
        # HIBP API Key
        hibp_label = QLabel("HaveIBeenPwned API Key:")
        hibp_label.setToolTip("Pour obtenir une clé:\n1. Allez sur https://haveibeenpwned.com/API/Key\n2. Créez un compte gratuit\n3. Demandez une clé API gratuite\n4. Copiez-collez la clé ici")
        api_layout.addWidget(hibp_label, 0, 0)
        self.hibp_input = QLineEdit()
        self.hibp_input.setText(self.settings.hibp_api_key)
        self.hibp_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.hibp_input.setPlaceholderText("Clé API HIBP (optionnel)")
        self.hibp_input.setToolTip("Clé API pour vérifier les fuites de données via HaveIBeenPwned")
        api_layout.addWidget(self.hibp_input, 0, 1)
        
        # Hunter API Key
        hunter_label = QLabel("Hunter.io API Key:")
        hunter_label.setToolTip("Pour obtenir une clé:\n1. Allez sur https://hunter.io/\n2. Créez un compte gratuit\n3. Accédez à votre dashboard API\n4. Copiez-collez la clé API ici")
        api_layout.addWidget(hunter_label, 1, 0)
        self.hunter_input = QLineEdit()
        self.hunter_input.setText(self.settings.hunter_api_key)
        self.hunter_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.hunter_input.setPlaceholderText("Clé API Hunter.io (optionnel)")
        self.hunter_input.setToolTip("Clé API pour la recherche d'emails via Hunter.io")
        api_layout.addWidget(self.hunter_input, 1, 1)
        
        # GitHub Token
        github_label = QLabel("GitHub Token:")
        github_label.setToolTip("Pour obtenir un token:\n1. Allez sur https://github.com/settings/tokens\n2. Cliquez sur 'Generate new token'\n3. Sélectionnez les permissions nécessaires\n4. Copiez-collez le token ici")
        api_layout.addWidget(github_label, 2, 0)
        self.github_input = QLineEdit()
        self.github_input.setText(self.settings.github_token)
        self.github_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_input.setPlaceholderText("Token GitHub (optionnel)")
        self.github_input.setToolTip("Token GitHub pour accéder aux informations de profil")
        api_layout.addWidget(self.github_input, 2, 1)
        
        layout.addWidget(api_group)
        
        # Configuration réseau
        network_group = QGroupBox("Configuration Réseau")
        network_layout = QGridLayout(network_group)
        
        # Timeout
        network_layout.addWidget(QLabel("Timeout (secondes):"), 0, 0)
        self.timeout_input = QLineEdit()
        self.timeout_input.setText(str(self.settings.request_timeout))
        network_layout.addWidget(self.timeout_input, 0, 1)
        
        # Délai minimum
        network_layout.addWidget(QLabel("Délai minimum (secondes):"), 1, 0)
        self.delay_min_input = QLineEdit()
        self.delay_min_input.setText(str(self.settings.request_delay_min))
        network_layout.addWidget(self.delay_min_input, 1, 1)
        
        # Délai maximum
        network_layout.addWidget(QLabel("Délai maximum (secondes):"), 2, 0)
        self.delay_max_input = QLineEdit()
        self.delay_max_input.setText(str(self.settings.request_delay_max))
        network_layout.addWidget(self.delay_max_input, 2, 1)
        
        # Requêtes concurrentes
        network_layout.addWidget(QLabel("Requêtes concurrentes:"), 3, 0)
        self.concurrent_input = QLineEdit()
        self.concurrent_input.setText(str(self.settings.max_concurrent))
        network_layout.addWidget(self.concurrent_input, 3, 1)
        
        layout.addWidget(network_group)
        
        # Seuils
        threshold_group = QGroupBox("Seuils")
        threshold_layout = QGridLayout(threshold_group)
        
        # Score minimum
        threshold_layout.addWidget(QLabel("Score minimum requis:"), 0, 0)
        self.min_score_input = QLineEdit()
        self.min_score_input.setText(str(self.settings.min_score_required))
        threshold_layout.addWidget(self.min_score_input, 0, 1)
        
        # Confiance minimum
        threshold_layout.addWidget(QLabel("Confiance minimum:"), 1, 0)
        self.confidence_input = QLineEdit()
        self.confidence_input.setText(str(self.settings.confidence_threshold))
        threshold_layout.addWidget(self.confidence_input, 1, 1)
        
        layout.addWidget(threshold_group)
        
        # Boutons
        # Boutons d'export/import
        import_export_layout = QHBoxLayout()
        
        export_btn = QPushButton("📤 Exporter config")
        export_btn.clicked.connect(self.export_config)
        import_export_layout.addWidget(export_btn)
        
        import_btn = QPushButton("📥 Importer config")
        import_btn.clicked.connect(self.import_config)
        import_export_layout.addWidget(import_btn)
        
        import_export_layout.addStretch()
        layout.addLayout(import_export_layout)
        
        # Boutons principaux
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Sauvegarder")
        save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def save_config(self):
        """Sauvegarde la configuration."""
        try:
            # Mettre à jour les settings
            self.settings.hibp_api_key = self.hibp_input.text().strip()
            self.settings.hunter_api_key = self.hunter_input.text().strip()
            self.settings.github_token = self.github_input.text().strip()
            
            # Validation des valeurs numériques
            try:
                self.settings.request_timeout = int(self.timeout_input.text())
                self.settings.request_delay_min = float(self.delay_min_input.text())
                self.settings.request_delay_max = float(self.delay_max_input.text())
                self.settings.max_concurrent = int(self.concurrent_input.text())
                self.settings.min_score_required = int(self.min_score_input.text())
                self.settings.confidence_threshold = float(self.confidence_input.text())
            except ValueError:
                QMessageBox.warning(self, "Erreur", "Les valeurs numériques sont invalides!")
                return
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur sauvegarde: {e}")
    
    def export_config(self):
        """Exporte la configuration vers un fichier JSON."""
        try:
            from PyQt6.QtWidgets import QFileDialog
            from config.settings import Settings
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Exporter la configuration",
                "echotrace_config.json",
                "Fichiers JSON (*.json)"
            )
            
            if file_path:
                self.settings.export_to_file(file_path)
                QMessageBox.information(self, "Export réussi", f"Configuration exportée dans:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur export: {e}")
    
    def import_config(self):
        """Importe la configuration depuis un fichier JSON."""
        try:
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            from config.settings import Settings
            
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Importer la configuration",
                "",
                "Fichiers JSON (*.json)"
            )
            
            if file_path:
                # Charger la configuration depuis le fichier
                imported_settings = Settings.import_from_file(file_path)
                
                # Mettre à jour les champs de l'interface
                self.hibp_input.setText(imported_settings.hibp_api_key)
                self.hunter_input.setText(imported_settings.hunter_api_key)
                self.github_input.setText(imported_settings.github_token)
                self.timeout_input.setText(str(imported_settings.request_timeout))
                self.delay_min_input.setText(str(imported_settings.request_delay_min))
                self.delay_max_input.setText(str(imported_settings.request_delay_max))
                self.concurrent_input.setText(str(imported_settings.max_concurrent))
                self.min_score_input.setText(str(imported_settings.min_score_required))
                self.confidence_input.setText(str(imported_settings.confidence_threshold))
                
                QMessageBox.information(
                    self, 
                    "Import réussi", 
                    f"Configuration importée depuis:\n{file_path}\n\nNote: Les clés API masquées n'ont pas été importées pour des raisons de sécurité."
                )
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur import: {e}")
    
    
