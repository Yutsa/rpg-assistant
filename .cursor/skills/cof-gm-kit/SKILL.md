---
name: cof-gm-kit
description: >-
  Crée une documentation MJ token-efficace (kit multi-fichiers) à partir d'un PDF
  de campagne/scénario Chroniques Oubliées Fantasy 2, style Croissez et multipliez.
  À utiliser quand l'utilisateur demande un kit MJ, une fiche de campagne pour agent,
  ou de préparer un scénario COF2 pour faire jouer sans relire le PDF.
---

# Skill — Kit MJ depuis PDF de campagne COF2

## Objectif

Produire sous `docs/gm-kits/<slug>/` un **kit MJ** qu’un agent peut charger **à la demande** (index + 1 fichier) pour faire jouer le scénario, sans avaler le PDF ni le livre de base.

Contraintes : fidélité au scénario, économie de tokens, règles LB via MCP `cof-rules`.

## Recommandation d’approche (hybride)

**Ne pas** lire tout le PDF en vision. **Ne pas** se fier au seul `get_text()`.

| Étape | Méthode | Pourquoi |
|-------|---------|----------|
| 1. Inventaire | `get_text()` + liste des pages | Volume bon marché (~12k tokens / 20 p.) |
| 2. Structure | Repérer pages à risque | Fiches monstre, encadrés, double colonne dense, titres déco |
| 3. Vision ciblée | PNG 1,5×–2× des pages à risque seulement | Structure, appartenance section, polices décoratives |
| 4. Règles LB | MCP `cof_*` / CLI `search` **1 fiche à la fois** | Corriger stats/libellés ; ne pas tout importer |
| 5. Rédaction kit | Fichiers `.txt` courts + `INDEX.txt` | Session live : INDEX puis 1 fichier |
| 6. QA | Vision sur 3–5 pages aléatoires vs kit | Hexagones, titres capacités, colonnes |

Coût typique campagne courte (≈16–20 p. contenu) : **texte + 3–6 pages vision + quelques `cof_get_*`** ≈ 17–25k tokens de préparation, vs 30–40k+ en vision naïve sur tout le PDF.

## Quand utiliser la vision (obligatoire)

Rendre et lire l’image si la page contient au moins un de :

- Fiche(s) technique(s) monstre/PNJ (boîtes, icônes DEF/PV/Init)
- Encadré MJ / sidebar (conseils, callouts)
- Titres en police décorative / petites caps ornementales
- Mise en page complexe : 2 colonnes + boîtes côte à côte
- Éléments non textuels utiles : hexagones de notation, symboles

Sinon : `get_text()` suffit pour le corps narratif.

### Détection automatique (signaux)

Classer chaque page en **MUST** / **SHOULD** / **TEXT** à partir du PDF (sans vision d’abord).

#### Ignorer (faux positifs)

- Dingbats / PUA seuls (`\uf074`, `\uf0af`, losanges de pagination, puces)
- Filigrane / mail (`WILLISSECK`, `@gmail`)
- Accents français normaux

#### MUST vision (au moins un signal dur)

1. **Title-garble** — ligne courte (≲70 car.) avec mojibake *significatif* :
   - motifs typiques COF : `Å…àé` (à la place de `DM`), `ïáê…`, `IéPÝ…`, `ðáïðï`, `Ýßðá` (titres d’acte)
   - ou ≥25 % de lettres hors alphabet FR sur une ligne type titre
2. **Statblock + garble** — présence de `NC` / `Points de vigueur` / `TAILLE` / marqueurs `(S)(V)(I)` **et** title-garble sur la même page
3. **Fiche technique scénario** — `FICHE TECHNIQUE` (hexagones Action/Ambiance non fiables en texte)

#### SHOULD vision (utile, pas forcément toutes)

- Encadré / callout (`TESTS OU`, `AVERTISSEMENT`, `NOTE DE…`) même si le texte est lisible
- Statblock **sans** garble (recouper icônes / appartenance colonne)
- Double colonne **seulement si** l’ordre du flux texte alterne L/R/L/R (chaos) — un simple `L* puis R*` propre → **TEXT OK**

#### TEXT OK

- Corps narratif, listes, jets en prose
- Double colonne propre (extracteur gauche→droite)
- Pages illustration sans règles critiques

#### Budget cible

Sur un one-shot ~20 p. type Croissez : viser **~30–50 %** des pages en vision (MUST+SHOULD), pas 100 %.  
Exemple mesuré sur Croissez : MUST `{5,6,7,9,12,13,18}` + SHOULD `{16,19,20}` ≈ 10/20.

Implémentation possible : petit script PyMuPDF (`get_text` + `dict` fonts/bboxes) appliquant les règles ci-dessus avant tout rendu PNG.

### Signes que `get_text()` a échoué

- Mojibake sur un titre (`ïáêï…`, `IéPÝ…`) alors que le paragraphe suivant est lisible
- `DM` devenu `Åàé` / glyphes bizarres
- Ordre absurde (attaque d’une fiche au milieu d’un autre paragraphe)
- Ratings / hexagones tous identiques (`W W W`) alors que la maquette varie

→ **Vision de cette page** +, si monstre aussi dans le LB, `cof_get_creature`.

## Pipeline pas à pas

### 0. Entrées

- Chemin PDF campagne
- `slug` dossier (ex. `croissez-et-multipliez`)
- Confirmer MCP `cof-rules` dispo (`cof_stats` ou CLI `stats`)

### 1. Extraction texte

```bash
# Exemple PyMuPDF : texte par page + liste pages
```

Conserver un extrait temporaire **hors repo** (`/tmp/…`). Ne pas committer le dump brut.

Noter : n° page PDF vs n° page scénario (souvent décalé : couv./crédits).

### 2. Cartographier le scénario (depuis le texte)

En une passe texte, extraire :

- Pitch, ton, avertissements table
- Actes / scènes et enchaînement
- Secrets MJ vs indices PJ
- Tous les **jets** (carac + DD) et renvois « livre p.XXX »
- Noms de créatures / PNJ à fiche
- Fins / branches

### 3. Vision ciblée

1. Identifier 3–8 pages à risque (étape 2 + heuristiques ci-dessus).
2. Rendre PNG (échelle 1,5 ou 2).
3. Lire chaque image (outil Read / vision).
4. Corriger libellés, appartenance encadrés, hexagones, découpage fiches bi-colonne.

### 4. Enrichir depuis le livre de base

Pour chaque créature / règle citée :

```
cof_search "…"  ou  cof_get_creature "Orc de base"
cof_get_element "Froid" / "Tendre une embuscade" / …
```

Règles :

- **1 appel = 1 besoin** ; pas de dump catalogue.
- Si le scénario **surcharge** une règle LB (ex. DD progression montagne), documenter la surcharge clairement.
- Propriété absente du LB (ex. « anti-magie » inventée par le module) : noter « scénario only » + effet tel quel.

### 5. Écrire le kit

Créer `docs/gm-kits/<slug>/` :

| Fichier | Contenu | Taille cible |
|---------|---------|--------------|
| `INDEX.txt` | Point d’entrée, table « quand ouvrir quoi », rappels MCP | &lt; 2 Ko |
| `00-pitch-secrets.txt` | Pitch, ton, secrets, indices, PNJ clés, fiche technique | &lt; 3 Ko |
| `01-deroule.txt` | Beats par acte + jets | &lt; 3 Ko |
| `02-fiches.txt` | Profils combat compact (NC DEF PV Init attaques capacités) | &lt; 3 Ko |
| `03-regles.txt` | Sous-ensemble LB indispensable + surcharges scénario | &lt; 3 Ko |
| `04-fins.txt` | Branches / conséquences | &lt; 2 Ko |

Adapter le découpage si besoin (ex. `02a`/`02b` si beaucoup de fiches), mais **toujours** un INDEX qui route.

Principes rédactionnels :

- Français, style télégraphique MJ (pas de roman).
- Chaque fichier **autonome** pour son rôle (pas de « voir ci-dessus » vers un autre fichier non ouvert).
- Références LB : `nom` + page quand connue.
- Secrets clairement marquées MJ-only.

### 6. Contrôle qualité

1. **Échantillon vision** : 3–5 pages PDF **aléatoires** (seed noté) → comparer au kit (pas seulement à `get_text()`).
2. **Lookups LB** : chaque créature/règle citée dans `02`/`03` résout via `cof_search` / `cof_get_*`.
3. **Budget** : kit total ≲ 15 Ko (~3–4k tokens) pour un one-shot type Croissez ; INDEX seul ≲ 2 Ko.
4. Mettre à jour `AGENTS.md` si nouveau kit (une ligne dans la liste des kits).

### 7. Livrables git

- Committer uniquement `docs/gm-kits/<slug>/` (+ docs agents si besoin).
- Ne pas committer dumps `/tmp`, PNG de QA (sauf artefacts demandés), ni `data/*.db`.

## Session de jeu (après création du kit)

Conduite de partie : skill **`.cursor/skills/cof-gm/SKILL.md`**.  
Journal de suivi après jeu : skill **`.cursor/skills/cof-chronicle/SKILL.md`**.

L’agent MJ doit :

1. Ouvrir **seulement** `INDEX.txt`.
2. Ouvrir **un** autre fichier du kit selon le besoin.
3. Appeler `cof_*` uniquement pour un trou ponctuel.
4. Jets / PNJ mécaniques : `<rule_application_secret>` ; hors balise, seule l’interprétation.

Interdit en session : relire le PDF campagne entier ; `cof_list_*` sans filtre large ; vision de toutes les pages.

## Anti-patterns

- Vision sur 100 % des pages « pour être sûr »
- Un seul `campagne.md` de 50 Ko
- Copier-coller le `get_text()` brut (mojibake inclus) dans le kit
- SQL ad hoc sur `cof_rules.db` (passer par MCP/CLI)
- Inventer des stats LB sans vérifier `cof_get_creature`

## Exemple de référence

Kit existant : `docs/gm-kits/croissez-et-multipliez/`  
PDF type : one-shot COF2 ~16–20 pages contenu, double colonne, fiches monstre, renvois LB.
