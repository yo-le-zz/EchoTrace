"""
EchoTrace — Configuration & Settings
"""

import json
import os
from dataclasses import dataclass, field, asdict

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(_BASE_DIR, "config", "echotrace_config.json")


@dataclass
class Settings:
    # API Keys (optionnels)
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

    # Cache
    cache_enabled: bool = True
    cache_ttl_hours: int = 24

    # Seuils
    min_score_required: int = 100
    confidence_threshold: float = 0.6

    # UI
    theme: str = "catppuccin_macchiato"
    language: str = "fr"

    # Export
    export_dir: str = ""

    def save(self):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            # Only keep known fields
            valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**valid)
        except Exception:
            return cls()
    
    def export_to_file(self, file_path: str):
        """Exporte la configuration vers un fichier JSON."""
        export_data = asdict(self)
        # Masquer les clés API pour la sécurité
        export_data["hibp_api_key"] = "***MASKED***" if self.hibp_api_key else ""
        export_data["hunter_api_key"] = "***MASKED***" if self.hunter_api_key else ""
        export_data["github_token"] = "***MASKED***" if self.github_token else ""
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def import_from_file(cls, file_path: str) -> "Settings":
        """Importe la configuration depuis un fichier JSON."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Ne pas importer les clés API masquées
        if data.get("hibp_api_key") == "***MASKED***":
            data["hibp_api_key"] = ""
        if data.get("hunter_api_key") == "***MASKED***":
            data["hunter_api_key"] = ""
        if data.get("github_token") == "***MASKED***":
            data["github_token"] = ""
        
        # Only keep known fields
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


# Singleton global
SETTINGS = Settings.load()


# ─── Score initial des champs ─────────────────────────────────────────────────

FIELD_SCORES = {
    "email":       90,
    "telephone":   80,
    "photo":       70,
    "pseudo":      50,
    "nom":         40,
    "prenom":      20,
    "ville":       15,
    "pays":        10,
    "entreprise":  25,
    "ecole":       20,
    "instagram":   35,
    "twitter":     35,
    "github":      40,
    "reddit":      30,
    "tiktok":      25,
    "youtube":     25,
    "twitch":      20,
    "discord":     20,
    "steam":       20,
    "snapchat":    20,
    "linkedin":    35,
    "domaine":     45,
    "bio":         15,
    "wallet":      50,
}

FIELD_LABELS = {
    "email":       "Adresse email",
    "telephone":   "Téléphone",
    "photo":       "Photo / Avatar",
    "pseudo":      "Pseudo / Username",
    "nom":         "Nom de famille",
    "prenom":      "Prénom",
    "ville":       "Ville",
    "pays":        "Pays",
    "entreprise":  "Entreprise",
    "ecole":       "École / Université",
    "instagram":   "Instagram",
    "twitter":     "Twitter / X",
    "github":      "GitHub",
    "reddit":      "Reddit",
    "tiktok":      "TikTok",
    "youtube":     "YouTube",
    "twitch":      "Twitch",
    "discord":     "Discord",
    "steam":       "Steam",
    "snapchat":    "Snapchat",
    "linkedin":    "LinkedIn",
    "domaine":     "Domaine web",
    "bio":         "Bio connue",
    "wallet":      "Wallet crypto",
}