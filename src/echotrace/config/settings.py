"""Configuration utilisateur d'EchoTrace."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from echotrace import paths

log = logging.getLogger(__name__)

MASK = "***MASKED***"
SECRET_FIELDS = ("hibp_api_key", "hunter_api_key", "github_token")

# Profils de réglages : (rapide) peu de variantes, (discret) peu de requêtes simultanées et lentes.
PROFILES: dict[str, dict] = {
    "rapide": {"max_username_variations": 4, "max_concurrent": 50, "request_delay_min": 0.1,
               "request_delay_max": 0.5, "per_host_limit": 5, "verify_profiles": False, "two_pass": True},
    "equilibre": {"max_username_variations": 10, "max_concurrent": 25, "request_delay_min": 0.3,
                  "request_delay_max": 1.5, "per_host_limit": 3, "verify_profiles": True, "two_pass": True},
    "complet": {"max_username_variations": 30, "max_concurrent": 25, "request_delay_min": 0.3,
                "request_delay_max": 1.5, "per_host_limit": 3, "verify_profiles": True, "two_pass": False},
    "discret": {"max_username_variations": 6, "max_concurrent": 5, "request_delay_min": 1.5,
                "request_delay_max": 4.0, "per_host_limit": 1, "verify_profiles": True, "two_pass": True},
}


@dataclass
class Settings:
    # Clés API (optionnelles). Seule la clé HIBP est utilisée aujourd'hui ;
    # Hunter et GitHub sont réservées pour de futurs modules.
    hibp_api_key: str = ""
    hunter_api_key: str = ""
    github_token: str = ""

    # Réseau
    request_timeout: int = 10
    request_delay_min: float = 0.3
    request_delay_max: float = 1.5
    max_concurrent: int = 25
    use_proxies: bool = False
    proxy_list: list = field(default_factory=list)

    # Cache des requêtes HTTP (table `cache` de la base)
    cache_enabled: bool = True
    cache_ttl_hours: int = 24

    # Seuils
    min_score_required: int = 100
    confidence_threshold: float = 0.0  # 0 = afficher tous les résultats
    max_username_variations: int = 10

    # Moteur
    profile: str = "equilibre"  # voir PROFILES
    two_pass: bool = True  # variantes d'abord sur les sites « sondes », puis sur tous si elles existent
    verify_profiles: bool = True  # relit les profils trouvés pour y chercher des indices
    per_host_limit: int = 3  # requêtes simultanées maximum vers un même site

    # Protection des données : suppression automatique des analyses anciennes (0 = jamais)
    retention_days: int = 90

    # Interface
    theme: str = "catppuccin_macchiato"
    language: str = "fr"

    # Export (vide = Documents/EchoTrace)
    export_dir: str = ""

    def validate(self) -> None:
        """Lève ValueError si une valeur est hors des bornes acceptables."""
        if self.request_timeout < 1:
            raise ValueError("Le timeout doit être d'au moins 1 seconde.")
        if self.request_delay_min < 0 or self.request_delay_max < self.request_delay_min:
            raise ValueError("Les délais doivent vérifier 0 <= minimum <= maximum.")
        if not 1 <= self.max_concurrent <= 200:
            raise ValueError("Les requêtes concurrentes doivent être comprises entre 1 et 200.")
        if self.min_score_required < 0:
            raise ValueError("Le score minimum ne peut pas être négatif.")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("Le seuil de confiance doit être compris entre 0 et 1.")
        if not 1 <= self.max_username_variations <= 50:
            raise ValueError("Le nombre de variations de pseudo doit être compris entre 1 et 50.")
        if not 1 <= self.per_host_limit <= 20:
            raise ValueError("La limite par site doit être comprise entre 1 et 20.")
        if not 0 <= self.retention_days <= 3650:
            raise ValueError("La durée de conservation doit être comprise entre 0 et 3650 jours.")

    def apply_profile(self, name: str) -> None:
        """Applique un profil de réglages prédéfini ; nom inconnu = aucun changement."""
        preset = PROFILES.get(name)
        if preset is None:
            return
        for key, value in preset.items():
            setattr(self, key, value)
        self.profile = name

    @property
    def export_path(self) -> Path:
        """Dossier d'export effectif."""
        if self.export_dir.strip():
            path = Path(self.export_dir).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            return path
        return paths.default_export_dir()

    # ── Persistance ──────────────────────────────────────────────────────────

    def save(self, path: Path | None = None) -> None:
        """Écrit la configuration de façon atomique, lisible par l'utilisateur seul."""
        target = path or paths.config_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        # Fichier temporaire dans le même dossier : os.replace reste atomique.
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(asdict(self), handle, indent=2, ensure_ascii=False)
            if os.name == "posix":
                os.chmod(tmp_name, 0o600)  # le fichier contient des clés API
            os.replace(tmp_name, target)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        target = path or paths.config_file()
        try:
            with open(target, encoding="utf-8") as handle:
                return cls._from_dict(json.load(handle))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError, TypeError) as exc:
            log.warning("Configuration illisible (%s), valeurs par défaut utilisées : %s", target, exc)
            return cls()

    @classmethod
    def _from_dict(cls, data: dict) -> Settings:
        if not isinstance(data, dict):
            raise TypeError("la configuration doit être un objet JSON")
        # On ignore les clés inconnues pour rester compatible entre versions.
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def export_to_file(self, file_path: str | Path) -> None:
        """Exporte la configuration en masquant les secrets."""
        data = asdict(self)
        for name in SECRET_FIELDS:
            data[name] = MASK if data[name] else ""
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    @classmethod
    def import_from_file(cls, file_path: str | Path) -> Settings:
        """Importe une configuration ; les secrets masqués sont ignorés."""
        with open(file_path, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            for name in SECRET_FIELDS:
                if data.get(name) == MASK:
                    data[name] = ""
        return cls._from_dict(data)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Instance partagée, chargée au premier appel."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings() -> Settings:
    """Relit le fichier de configuration (utile pour les tests)."""
    global _settings
    _settings = Settings.load()
    return _settings
