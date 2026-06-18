# Audit ingestion COF2 — trois campagnes supplémentaires

**Date :** 2026-06-18  
**Méthode :** import `game_system=cof2`, script `scripts/audit_cof2_campaign.py`, revue visuelle ciblée (rendu PNG des pages signalées).

| Campagne | `campaign_id` | `document_id` | PDF | Pages | Chunks | Sections | Fiches |
|----------|---------------|---------------|-----|-------|--------|----------|--------|
| Mortelle Xélys | `mortelle-xelys` | `doc_576859501624` | `COF2_Mortelle_Xelys.pdf` | 20 | 45 | 42 | 4 |
| Croissez et multipliez | `croissez-multipliez` | `doc_940fbddb1034` | `COF2_Croissez_Et_Multipliez.pdf` | 20 | 36 | 21 | 4 |
| Retour en grâce | `retour-en-grace` | `doc_9d4fe6da33a1` | `COF2_Retour_En_Grace.pdf` | 20 | 48 | 48 | 0 |

## Synthèse

| Sévérité | Mortelle Xélys | Croissez et multipliez | Retour en grâce |
|----------|----------------|------------------------|-----------------|
| **Majeure** | 2 | 0 (1 faux positif) | 3 |
| **Mineure** | 4 | 0 | 4 |

Les trois PDF sont bien importés et globalement lisibles. Les écarts majeurs se concentrent sur **Retour en grâce** (texte tronqué, titres éclatés, arbre généalogique illisible) et sur les **fiches COF2** des deux autres scénarios (filigrane DRM dans la couche texte PDF).

---

## Mortelle Xélys (`doc_576859501624`)

### Problèmes majeurs

#### 1. Fiches monstre/PNJ corrompues par le filigrane (p. 3)

Les noms extraits sont `W HERMÉSIA\x03`, `W DECTIANN\x03`, etc. Le corps des fiches mélange attributs lisibles et glyphes de personnalisation DRM (`TAIèèá`, `òëè`, titres de capacités illisibles).

**Cause :** le filtre `filter_watermark_blocks` ne retire que les blocs répétés sur plusieurs pages ou dans l'en-tête/pied ; le filigrane « W NOM\x03 » est injecté page par page dans la couche texte des fiches et n'est pas éliminé.

**Impact :** `list_stat_blocks` / `get_stat_block` inutilisables pour Hermésia, Pseck, Dectiann.

#### 2. Texte de SURVEILLANCE rattaché à la mauvaise section (p. 12–13)

Le paragraphe *« Pseck et Hermésia guettent l'arrivée des PJ… »* (sous le titre **SURVEILLANCE**, p. 12) est bien extrait mais rangé dans le chunk `chunk_doc_576859501624_012_025`, section **LE VOYAGE JUSQU'À XÉLYS**. La section `SURVEILLANCE` (`sec_d7be636a43fb`) apparaît vide.

**Vérification visuelle :** p. 12 — titre SURVEILLANCE en bas de colonne droite ; p. 13 — suite du paragraphe avant **AUTOUR D'ERRANDS**. Le texte est présent, l'assignation de section est fausse.

### Problèmes mineurs

#### 3. Section fantôme « J-15 » (p. 7)

`J-15` est une ligne du tableau **Chronologie des événements**, pas un titre de section. Une section niveau 3 vide a été créée (`sec_f8ba63a655e6`).

#### 4. Section parente « LES PISTES À SUIVRE » vide (p. 17)

Le contenu (*Les mercenaires Sables rouges*) est dans la sous-section `Les mercenaires Sables\nrouges` ; le titre parent niveau 1 n'a pas de chunk direct (comportement hiérarchique, pas de perte de texte).

#### 5. Trois blocs orphelins (p. 4)

Blocs `block_doc_576859501624_004_003` à `_005` : page **CRÉDITS** (fond bleu, peu de texte extractible) — impact négligeable.

---

## Croissez et multipliez (`doc_940fbddb1034`)

### Faux positif : « saut » de page 14

Le chunk `chunk_doc_940fbddb1034_013_028` couvre p. 13–15 en omettant p. 14. **Vérification visuelle :** p. 14 est une illustration pleine page sans texte (page décorative). Comportement attendu, pas un bug.

### Problème majeur (commun aux COF2 filigranés)

#### Fiches avec préfixe filigrane (p. 9, 13, 19)

Même schéma que Mortelle Xélys : `W SERGENT ORC\x03`, `W PANTHÈRE\x03`, etc. Les attributs de base sont souvent lisibles ; les capacités en colonne opposée (ex. **EMBUSCADE** de la Panthère, p. 13) peuvent être incomplètes si le parseur s'arrête au filigrane.

**Vérification visuelle p. 13 :** la fiche Panthère commence en bas de colonne gauche ; les capacités **EMBUSCADE** et **DÉVORER** continuent en haut de colonne droite, au-dessus de l'encadré **REBROUSSER CHEMIN**.

**Constat base :** le chunk `stat_block` Panthère ne contient que l'en-tête et les attributs ; `abilities: []` — les capacités ne sont pas extraites (filigrane + coupure colonne / encadré).

### Points positifs

- Pas de mélange crédits / intro.
- Pas de section vide significative.
- Hiérarchie des sections cohérente sur l'échantillon p. 13–15.

---

## Retour en grâce (`doc_9d4fe6da33a1`)

### Problèmes majeurs

#### 1. Texte tronqué sous « Démasquer l'espion » (p. 10)

Le chunk `chunk_doc_9d4fe6da33a1_010_013` (section **MISSION 1**) se termine en plein milieu de phrase :

> « …Une fois le nombre de réussites atteint, l'espion n'est pas nécessairement démasqué. **Les** »

La section `Démasquer l'espion` (`sec_471aef00b284`) est vide. Le paragraphe suivant (*« PJ obtiennent un indice… »*) n'apparaît dans aucun chunk.

**Cause probable :** enrobage de colonne autour de l'illustration centrale + titres **Démasquer l'espion** / **Organiser une** / **réception** sur trois blocs séparés ; la continuation de colonne est coupée au changement de sous-titre.

#### 2. Titre de section tronqué « Organiser une » (p. 10)

Le PDF extrait deux blocs : `Organiser une` puis `réception`. La section créée est `Organiser une` ; le contenu est rattaché à une section fantôme `réception` (`sec_469fe4a4ac53`). Texte présent mais structure incorrecte.

#### 3. Arbre généalogique illisible (p. 17)

Le chunk `chunk_doc_9d4fe6da33a1_017_041` mélange le diagramme (texte garbage : `! Ýé Larentia ĆoĐėesse…`) avec le début du passage **Un tournoi de chevaliers**. Le visuel est un arbre généalogique graphique non extractible proprement en texte.

### Problèmes mineurs

#### 4. Sections vides avec contenu ailleurs

| Section vide | Contenu réel |
|--------------|--------------|
| `Un passage secret` (p. 13–14) | Intro (test PER) fusionnée dans chunk RÉCOMPENSE ; corps dans `Le complexe souterrain` |
| `Un tournoi de chevaliers` (p. 17–19) | Texte dans chunk `Manthine` et `MISSION : LA JOUTE ROYALE` |
| `RÉCOMPENSE EN POINTS DE FAVEUR` (p. 16) | Doublon — autre encadré homonyme p. 11 et p. 13 |

#### 5. Aucune fiche COF2 détectée

Normal pour ce scénario : pas de fiches monstre au format COF2 standard sur l'échantillon parcouru.

#### 6. Titres de mission avec caractères corrompus

Ex. `MISSION : LA JOUTE ROõALE`, `MISSION ! : LE CAVEAU DU SOUVENIR` — artefacts de la couche texte PDF.

---

## Commandes de reproduction

```bash
# Import (déjà effectué)
uv run rpg-ingest raw extract data/pdfs/COF2_Mortelle_Xelys.pdf \
  --campaign-id mortelle-xelys --game-system cof2
uv run rpg-ingest raw extract data/pdfs/COF2_Croissez_Et_Multipliez.pdf \
  --campaign-id croissez-multipliez --game-system cof2
uv run rpg-ingest raw extract data/pdfs/COF2_Retour_En_Grace.pdf \
  --campaign-id retour-en-grace --game-system cof2

# Audit automatisé
uv run python scripts/audit_cof2_campaign.py mortelle-xelys \
  data/pdfs/COF2_Mortelle_Xelys.pdf --skip-import --document-id doc_576859501624
uv run python scripts/audit_cof2_campaign.py croissez-multipliez \
  data/pdfs/COF2_Croissez_Et_Multipliez.pdf --skip-import --document-id doc_940fbddb1034
uv run python scripts/audit_cof2_campaign.py retour-en-grace \
  data/pdfs/COF2_Retour_En_Grace.pdf --skip-import --document-id doc_9d4fe6da33a1
```

Captures de revue visuelle : `data/visual_review/doc_<id>/page_*.png`.

---

## Pistes de correctif (par priorité)

1. **Filigrane DRM dans les fiches** — détecter et retirer les blocs `W <NOM>\x03` et glyphes associés avant `annotate_stat_blocks` / parsing COF2.
2. **Retour en grâce p. 10** — fusion des titres multi-blocs (`Organiser une` + `réception`) ; continuation de colonne à travers l'illustration pour ne pas tronquer « Démasquer l'espion ».
3. **Sections fantômes tableaux** — ne pas promouvoir les libellés de ligne (`J-12`, `J-15`) en sections si le contexte est un tableau.
4. **Arbres / diagrammes** — marquer comme `content_only` ou ignorer les zones à faible couverture texte (pas de chunk narrative).
5. **Assignation section / chunk** — quand un titre niveau 1 n'a que du contenu en continuation de colonne, rattacher au bon parent (ex. SURVEILLANCE).
