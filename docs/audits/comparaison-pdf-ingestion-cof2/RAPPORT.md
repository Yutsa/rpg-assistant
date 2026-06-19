# Audit ingestion COF2 — comparaison PDF / base de données

**Date initiale :** 2026-06-18  
**Re-vérification code :** 2026-06-18 (régressions synthétiques + correctif continuation colonne)

| Campagne | Document ID (réf.) | PDF source |
|----------|-------------------|------------|
| `momie` | `doc_010672301b36` | `COF2_10_Mondanites_Et_Momies_web_v1a.pdf` |
| `dernier-faelys` | `doc_9890af687cf9` | `COF2_07_Le_Dernier_Faelys_web_v0.pdf` |

## Synthèse

Les **10 problèmes** listés dans l'audit initial sont couverts par des tests de régression synthétiques (`tests/test_cof2_audit_*.py`, `tests/test_page8_layout.py`) qui passent tous après les correctifs suivants :

1. **Crédits / synopsis** — filtrage des blocs éditoriaux, pas de fusion inter-pages crédits ↔ narratif.
2. **Encadré p. 7 Faelys** — fusion des lignes de titre d'encadré (`block_merging`) + normalisation du titre de section.
3. **Hiérarchie zones Faelys** — réinitialisation du parent actif pour les sections `subordinate` tardives.
4. **Capacités COF2** — parsing inline et ordre de lecture deux colonnes (`cof2.py`).
5. **Chunk p. 10→12** — découpage aux sauts de page non contigus (`_split_at_page_gaps`).
6. **MILLE-PATTES / centaures** — frontières de chunk et assignation colonne.

**Correctif additionnel (2026-06-18)** : un chapitre parent (`PARTIE I`) ne doit plus capter la continuation de colonne d'une sous-section (`L'histoire pour le MJ`) sur la page suivante ; la continuation sparse après page décorative est prioritaire sur un propriétaire de colonne non concerné.

### Vérification automatisée

```bash
# Tests de régression audit
uv run python -m pytest tests/test_cof2_audit_sections.py tests/test_cof2_audit_chunking.py tests/test_cof2_audit_stat_blocks.py tests/test_page8_layout.py -v

# Import + checklist complète (PDF requis)
uv run python scripts/audit_cof2_ingestion.py \
  --momie-pdf /chemin/COF2_10_Mondanites_Et_Momies_web_v1a.pdf \
  --faelys-pdf /chemin/COF2_07_Le_Dernier_Faelys_web_v0.pdf
```

Placer les PDF dans `data/pdfs/` permet aussi la résolution automatique par glob.

### Re-vérification PDF réelle

Les PDF propriétaires ne sont pas versionnés. Une re-importation sur les fichiers sources reste recommandée pour valider visuellement via MCP `prepare_visual_ingestion_review` une fois les PDF disponibles sur la machine d'exécution.

---

## Erreurs initiales — détail et statut attendu

| # | Problème | Page(s) | Statut attendu après correctifs |
|---|----------|---------|--------------------------------|
| 1 | Momie — synopsis + crédits fusionnés | 2, 4 | Corrigé (crédits filtrés du chunk synopsis) |
| 2 | Faelys — crédits + intro fusionnés | 4, 5 | Corrigé |
| 3 | Faelys — encadré titre éclaté | 7 | Corrigé |
| 4 | Faelys — 11 sections mal rattachées | 12–19 | Corrigé |
| 5 | Faelys — CENTAURE capacités manquantes | 16 | Corrigé |
| 6 | Faelys — FÉE capacités manquantes | 15 | Corrigé |
| 7 | Faelys — SOMBRE FÉE capacités manquantes | 19 | Corrigé |
| 8 | Faelys — chunk saute p. 11 | 10–12 | Corrigé |
| 9 | Faelys — MILLE-PATTES tronqué | 12 | Corrigé |
| 10 | Faelys — texte centaures mauvaise section | 16 | Corrigé |

---

## Captures de référence

Les captures dans `screenshots/` proviennent de l'audit visuel initial et servent de référence pour une comparaison manuelle ou MCP.

| Document | Pages capturées |
|----------|-----------------|
| Momie | 2, 4, 15 |
| Faelys | 4, 5, 7, 12, 15, 16, 19 |

---

## Pistes si un écart persiste sur PDF réel

1. Exécuter `scripts/audit_cof2_ingestion.py` et noter les `findings` JSON.
2. `prepare_visual_ingestion_review(document_id, seed=42)` puis comparer `image_path` / chunks.
3. Vérifier la couverture texte (`text_coverage_ratio`) et l'absence de PDF scanné.
