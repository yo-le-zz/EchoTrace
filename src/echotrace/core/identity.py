"""Empreinte stable d'une cible : relie deux analyses de la même personne."""

from __future__ import annotations

import hashlib

# Champs qui identifient la cible ; ville, entreprise... peuvent changer sans changer la cible.
IDENTITY_FIELDS = ("pseudo", "email", "telephone", "nom", "prenom")

# Finalités proposées avant une analyse : le RGPD demande de savoir pourquoi on traite des données
# personnelles. La finalité est enregistrée avec l'analyse et rappelée dans les rapports.
PURPOSES = (
    "Ma propre empreinte en ligne",
    "Avec l'accord de la personne concernée",
    "Vérification professionnelle (recrutement, due diligence)",
    "Journalisme ou recherche (intérêt légitime)",
    "Protection de mes droits (litige, usurpation d'identité)",
)


def split_photos(value: str | list[str] | None) -> list[str]:
    """Liste des photos d'une cible (une par ligne ou séparées par `;`), sans doublon."""
    if not value:
        return []
    items = value if isinstance(value, list) else value.replace(";", "\n").splitlines()
    return list(dict.fromkeys(item.strip() for item in items if item.strip()))


def split_pseudos(value: str | None) -> list[str]:
    """Pseudos d'une cible (un par ligne ou séparés par `;`), sans doublon."""
    if not value:
        return []
    items = value.replace(";", "\n").splitlines()
    return list(dict.fromkeys(item.strip() for item in items if item.strip()))


def target_key(target_data: dict) -> str:
    """Empreinte des champs d'identité (insensible à la casse, aux espaces et à l'ordre)."""
    parts = []
    for field in IDENTITY_FIELDS:
        value = str(target_data.get(field, ""))
        if field == "pseudo":  # plusieurs pseudos : l'ordre de saisie ne change pas la cible
            value = ";".join(sorted(p.lower() for p in split_pseudos(value)))
        parts.append(f"{field}={value.strip().lower()}")
    if not any(target_data.get(field) for field in IDENTITY_FIELDS):
        return ""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]
