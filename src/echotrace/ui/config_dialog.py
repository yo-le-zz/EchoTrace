"""Fenêtre de configuration."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from echotrace.config.settings import PROFILES, Settings
from echotrace.database import db

API_KEY_HELP = {
    "hibp_api_key": ("HaveIBeenPwned API Key :",
                     "Clé payante sur https://haveibeenpwned.com/API/Key (requise pour la v3)."),
    "hunter_api_key": ("Hunter.io API Key :", "Réservée à un futur module."),
    "github_token": ("GitHub Token :", "Réservé à un futur module."),
}


class ConfigDialog(QDialog):
    """Édite un objet `Settings` ; les modifications ne sont appliquées qu'à la validation."""

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Configuration EchoTrace")
        self.setModal(True)
        self.resize(600, 800)
        self._build()
        self._load(settings)

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        api_group = QGroupBox("Clés API (optionnelles)")
        api_layout = QGridLayout(api_group)
        self.key_inputs: dict[str, QLineEdit] = {}
        for row, (name, (label, tip)) in enumerate(API_KEY_HELP.items()):
            api_layout.addWidget(QLabel(label), row, 0)
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setToolTip(tip)
            api_layout.addWidget(edit, row, 1)
            self.key_inputs[name] = edit
        layout.addWidget(api_group)

        net_group = QGroupBox("Réseau")
        net_layout = QGridLayout(net_group)
        self.timeout = QSpinBox()
        self.timeout.setRange(1, 120)
        self.timeout.setSuffix(" s")
        self.delay_min = QDoubleSpinBox()
        self.delay_max = QDoubleSpinBox()
        for spin in (self.delay_min, self.delay_max):
            spin.setRange(0.0, 60.0)
            spin.setSingleStep(0.1)
            spin.setSuffix(" s")
        self.concurrent = QSpinBox()
        self.concurrent.setRange(1, 200)
        rows = [("Timeout :", self.timeout), ("Délai minimum :", self.delay_min),
                ("Délai maximum :", self.delay_max), ("Requêtes concurrentes :", self.concurrent)]
        for row, (label, widget) in enumerate(rows):
            net_layout.addWidget(QLabel(label), row, 0)
            net_layout.addWidget(widget, row, 1)
        layout.addWidget(net_group)

        thr_group = QGroupBox("Seuils et cache")
        thr_layout = QGridLayout(thr_group)
        self.min_score = QSpinBox()
        self.min_score.setRange(0, 1000)
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0)
        self.confidence.setSingleStep(0.05)
        self.variations = QSpinBox()
        self.variations.setRange(1, 50)
        self.cache_enabled = QCheckBox("Activer le cache des requêtes")
        self.cache_ttl = QSpinBox()
        self.cache_ttl.setRange(1, 24 * 30)
        self.cache_ttl.setSuffix(" h")
        clear_cache = QPushButton("Vider le cache")
        clear_cache.clicked.connect(self._clear_cache)
        rows = [("Score minimum requis :", self.min_score),
                ("Confiance minimale affichée :", self.confidence),
                ("Variations de pseudo testées :", self.variations),
                ("Durée de vie du cache :", self.cache_ttl)]
        for row, (label, widget) in enumerate(rows):
            thr_layout.addWidget(QLabel(label), row, 0)
            thr_layout.addWidget(widget, row, 1)
        thr_layout.addWidget(self.cache_enabled, len(rows), 0)
        thr_layout.addWidget(clear_cache, len(rows), 1)
        layout.addWidget(thr_group)

        engine_group = QGroupBox("Moteur et protection des données")
        engine_layout = QGridLayout(engine_group)
        self.profile = QComboBox()
        self.profile.addItems(list(PROFILES))
        self.profile.setToolTip("Applique un jeu de réglages (variantes, vitesse, discrétion).")
        apply_profile = QPushButton("Appliquer le profil")
        apply_profile.clicked.connect(self._apply_profile)
        self.two_pass = QCheckBox("Deux passes (variantes d'abord sur les sites rapides)")
        self.verify_profiles = QCheckBox("Vérifier le contenu des profils trouvés")
        self.per_host = QSpinBox()
        self.per_host.setRange(1, 20)
        self.retention = QSpinBox()
        self.retention.setRange(0, 3650)
        self.retention.setSuffix(" jours")
        self.retention.setSpecialValueText("jamais")
        self.retention.setToolTip("Les analyses plus anciennes sont supprimées au démarrage (RGPD : "
                                  "limitation de la conservation).")
        purge = QPushButton("Purger maintenant")
        purge.clicked.connect(self._purge_now)
        engine_layout.addWidget(QLabel("Profil :"), 0, 0)
        engine_layout.addWidget(self.profile, 0, 1)
        engine_layout.addWidget(apply_profile, 0, 2)
        engine_layout.addWidget(self.two_pass, 1, 0, 1, 3)
        engine_layout.addWidget(self.verify_profiles, 2, 0, 1, 3)
        engine_layout.addWidget(QLabel("Requêtes simultanées par site :"), 3, 0)
        engine_layout.addWidget(self.per_host, 3, 1)
        engine_layout.addWidget(QLabel("Conservation des analyses :"), 4, 0)
        engine_layout.addWidget(self.retention, 4, 1)
        engine_layout.addWidget(purge, 4, 2)
        layout.addWidget(engine_group)

        export_group = QGroupBox("Export")
        export_layout = QHBoxLayout(export_group)
        self.export_dir = QLineEdit()
        self.export_dir.setPlaceholderText("Par défaut : Documents/EchoTrace")
        browse = QPushButton("Parcourir")
        browse.clicked.connect(self._browse_export_dir)
        export_layout.addWidget(self.export_dir)
        export_layout.addWidget(browse)
        layout.addWidget(export_group)

        io_layout = QHBoxLayout()
        export_btn = QPushButton("Exporter la config")
        export_btn.clicked.connect(self._export_config)
        import_btn = QPushButton("Importer une config")
        import_btn.clicked.connect(self._import_config)
        io_layout.addWidget(export_btn)
        io_layout.addWidget(import_btn)
        io_layout.addStretch()
        layout.addLayout(io_layout)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Enregistrer")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    # ── Données ──────────────────────────────────────────────────────────────

    def _load(self, settings: Settings) -> None:
        for name, edit in self.key_inputs.items():
            edit.setText(getattr(settings, name))
        self.timeout.setValue(settings.request_timeout)
        self.delay_min.setValue(settings.request_delay_min)
        self.delay_max.setValue(settings.request_delay_max)
        self.concurrent.setValue(settings.max_concurrent)
        self.min_score.setValue(settings.min_score_required)
        self.confidence.setValue(settings.confidence_threshold)
        self.variations.setValue(settings.max_username_variations)
        self.cache_enabled.setChecked(settings.cache_enabled)
        self.cache_ttl.setValue(settings.cache_ttl_hours)
        self.export_dir.setText(settings.export_dir)
        self.profile.setCurrentText(settings.profile)
        self.two_pass.setChecked(settings.two_pass)
        self.verify_profiles.setChecked(settings.verify_profiles)
        self.per_host.setValue(settings.per_host_limit)
        self.retention.setValue(settings.retention_days)

    def _collect(self) -> Settings:
        """Construit un Settings à partir du formulaire, en conservant les champs non édités."""
        data = {**self.settings.__dict__}
        data.update(
            {name: edit.text().strip() for name, edit in self.key_inputs.items()},
            request_timeout=self.timeout.value(),
            request_delay_min=self.delay_min.value(),
            request_delay_max=self.delay_max.value(),
            max_concurrent=self.concurrent.value(),
            min_score_required=self.min_score.value(),
            confidence_threshold=self.confidence.value(),
            max_username_variations=self.variations.value(),
            cache_enabled=self.cache_enabled.isChecked(),
            cache_ttl_hours=self.cache_ttl.value(),
            export_dir=self.export_dir.text().strip(),
            profile=self.profile.currentText(),
            two_pass=self.two_pass.isChecked(),
            verify_profiles=self.verify_profiles.isChecked(),
            per_host_limit=self.per_host.value(),
            retention_days=self.retention.value(),
        )
        return Settings(**data)

    def _save(self) -> None:
        candidate = self._collect()
        try:
            candidate.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Configuration invalide", str(exc))
            return
        # Mise à jour en place : le reste de l'application garde la même instance.
        self.settings.__dict__.update(candidate.__dict__)
        self.accept()

    # ── Actions ──────────────────────────────────────────────────────────────

    def _apply_profile(self) -> None:
        """Remplit le formulaire avec le profil choisi, sans rien enregistrer avant la validation."""
        preview = self._collect()
        preview.apply_profile(self.profile.currentText())
        self._load(preview)

    def _purge_now(self) -> None:
        days = self.retention.value()
        if days == 0:
            QMessageBox.information(self, "Purge", "La conservation est illimitée : rien à purger.")
            return
        deleted = db.purge_older_than(days)
        QMessageBox.information(self, "Purge", f"{deleted} analyse(s) de plus de {days} jours supprimée(s).")

    def _browse_export_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Dossier d'export", self.export_dir.text())
        if folder:
            self.export_dir.setText(folder)

    def _clear_cache(self) -> None:
        db.cache_clear()
        QMessageBox.information(self, "Cache", "Cache vidé.")

    def _export_config(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la configuration", "echotrace_config.json", "JSON (*.json)")
        if not path:
            return
        try:
            self._collect().export_to_file(path)
        except OSError as exc:
            QMessageBox.critical(self, "Erreur", f"Export impossible : {exc}")
            return
        QMessageBox.information(self, "Export réussi",
                                f"Configuration exportée (clés API masquées) :\n{path}")

    def _import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer une configuration", "", "JSON (*.json)")
        if not path:
            return
        try:
            imported = Settings.import_from_file(path)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Erreur", f"Fichier de configuration invalide : {exc}")
            return
        # Les clés masquées à l'export reviennent vides : on garde celles déjà saisies.
        for name, edit in self.key_inputs.items():
            if getattr(imported, name):
                continue
            setattr(imported, name, edit.text().strip())
        self._load(imported)
