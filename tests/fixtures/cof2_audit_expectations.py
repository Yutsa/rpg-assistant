"""Expectations derived from docs/audits/comparaison-pdf-ingestion-cof2/RAPPORT.md."""

from __future__ import annotations

MOMIE_SYNOPSIS_MARKERS = ("malédiction", "momie")
MOMIE_SYNOPSIS_SECTION = "LA MALÉDICTION DE LA MOMIE"
MOMIE_CREDITS_MARKERS = ("Black Book", "Tous droits réservés")

FAELYS_CREDITS_MARKERS = ("Black Book", "Tous droits réservés")
# EN QUELQUES MOTS synopsis (p.5) — distinct from backstory in FICHE TECHNIQUE.
FAELYS_INTRO_MARKERS = ("Hiver 325", "Manthine de Sénice")
FAELYS_BACKSTORY_MARKERS = ("Le bois d'Astréis", "bois d'Astréis")
FAELYS_CREDITS_SECTION = "CRÉDITS"
FAELYS_INTRO_SECTION = "EN QUELQUES MOTS"

# ASCII spellings for synthetic fixtures (mirrors audit p.7 encadré; PDF uses FÉLIS/FÉÉRIQUE).
FAELYS_SHADOW_BOX_TITLE = "LES FELIS ET LE PLAN DE L'OMBRE FEERIQUE"
FAELYS_SHADOW_BOX_TRUNCATED = "LES FELIS ET LE PLAN DE"

FAELYS_IMPLICATION_SECTION = "IMPLICATION DES PJ"
FAELYS_ZONE_TITLES = (
    "La prairie fleurie",
    "La grotte d'Ekhidna",
)

CENTAURE_ABILITIES = ("ATTAQUE DOUBLE", "CHARGER", "HYBRIDE", "DISCRET")
FEE_ABILITIES = (
    "CHARME PERSONNE",
    "DISTRACTION",
    "ÉTERNUEMENT",
    "RÉSISTANCE AUX DM",
    "VOL",
)
SOMBRE_FEE_ABILITIES = (
    "TOILE",
    "MAÎTRE DES TOILES",
    "PATTES D'ARAIGNÉE",
    "POISON",
    "CAMOUFLAGE",
)
