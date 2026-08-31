---
name: cof-chronicle
description: >-
  Compacte l’histoire d’une partie Chroniques Oubliées Fantasy 2 dans un
  journal indexé (résumé très court + fichiers chapitre). À utiliser quand
  l’utilisateur demande de compacter / archiver / résumer la session ou
  la campagne, que le contexte du chat est trop gros, ou qu’il faut un
  journal de suivi pour reprendre sans relire le fil.
---

# Skill — Chronique (compactage de l’aventure)

## Rôle

Tu **n’es pas** le MJ ni un PJ. Tu **archives** ce qui s’est déjà joué
dans des fichiers courts, pour qu’un agent MJ puisse **reprendre** sans
avaler le transcript.

Buts, dans cet ordre :

1. **Tracer** l’aventure (faits, décisions, conséquences, fils ouverts).
2. **Indexer** : un `INDEX.txt` minuscule qui pointe vers le détail.
3. **Épargner les tokens** : personne ne relit tout le dossier ni le chat.

Déclenchement **manuel** (première version) : l’utilisateur le demande
quand le fil devient trop long. Ne pas compacter tout seul en plein beat.

## Arborescence

```
docs/chronicles/<slug>/
  INDEX.txt      résumé global + table des chapitres (toujours ça d’abord)
  etat.txt       maintenant (lieu, enjeu, groupe, scène encore ouverte)
  mj.txt         secrets / horloges / fins encore vifs — JAMAIS agents PJ
  10-<titre>.txt chapitres (faits de table, une scène ou une session)
  11-<titre>.txt
  r01-*.txt      recap plié (quand trop de chapitres) — les 10+ restent sur disque
```

Slug = celui du kit / du fil public (`croissez-et-multipliez`, …).

Modèles : `docs/chronicles/_modele-*.txt`. README : `docs/chronicles/README.txt`.

## Deux modes

| Mode | Quand | Quoi faire |
|------|--------|------------|
| **Compacter** | « compacte », « archive la session », « journal », contexte trop gros | Écrire / réécrire les fichiers |
| **Consulter** | Reprise de partie, « on en était où ? », un souvenir flou | Lire **INDEX + etat** seulement ; **un** autre fichier si trou |

Si l’utilisateur ne précise pas : **compacter**.  
Consulter ne réécrit rien sauf `etat.txt` si la scène ouverte a bougé
et qu’on te le demande.

## Budget (dur)

| Fichier | Plafond | Contenu |
|---------|---------|---------|
| `INDEX.txt` | ~40 lignes | 5–8 lignes de résumé + 1 ligne par chapitre + fils ouverts |
| `etat.txt` | ~40 lignes | Maintenant seulement, pas l’histoire |
| `mj.txt` | ~40 lignes | Secrets **encore utiles** |
| Chapitre `1N-*.txt` | ~15–40 lignes | Une scène (ou une session courte) |
| Recap `r0N-*.txt` | ~40 lignes | Plusieurs vieux chapitres pliés |

Interdit : roman, dialogues in extenso, jets / DD / PV ennemi, copier le
kit, coller le fil public, transcript du chat.

## Compacter — procédure

1. **Slug.** Si absent : celui du kit ouvert / du public / demander une fois.
2. **Créer** le dossier si besoin : copier les `_modele-*.txt` vers
   `INDEX.txt`, `etat.txt`, `mj.txt` (chapitres : pas de modèle vide
   commité dans le slug).
3. **Lire seulement** l’existant `INDEX.txt` + `etat.txt` + `mj.txt`.
   **Pas** tous les chapitres. **Pas** tout le kit (`00`–`04`).
4. **Sources du nouveau** (dans cet ordre, le minimum) :
   - le fil de **cette** conversation (ce qui s’est joué depuis le
     dernier compact / depuis `etat.txt` → scène ouverte) ;
   - `docs/table/<slug>-public.txt` (dernier beat, pour ne pas rater
     l’état perçu) ;
   - mémoires `docs/pc-memory/` **uniquement** si un fait PJ (promesse,
     croyance, blessure) manque et qu’il faudra le noter en faits de table.
5. **Découper** en scènes **closes** (changement de lieu, de but, ou fin
   de session). Une scène close = **un** chapitre, ou **mise à jour** du
   dernier chapitre s’il s’agit du même lieu / même but (ne pas exploser
   en micro-fichiers).
6. **Écrire** les chapitres nouveaux ou mis à jour (gabarit ci-dessous).
7. **Réécrire** `etat.txt` (écraser, ne pas append) : maintenant +
   éventuelle scène encore ouverte en 1–3 lignes.
8. **Réécrire** `INDEX.txt` : résumé global à jour ; table des chapitres
   (et recaps) avec **une** phrase chacun ; fils ouverts avec pointeur
   de fichier.
9. **Mettre à jour** `mj.txt` : secrets encore cachés, horloges MJ,
   déviations vs kit, fins encore possibles. Retirer ce qui est mort.
   Les révélations **déjà dites à la table** migrent dans le chapitre
   (faits) et une ligne « révélé (chap. N) » dans `mj.txt`.
10. **Répondre à l’utilisateur** : slug, fichiers touchés, 5 lignes
    « où on en est », rappel « prochaine session MJ : INDEX + etat ».

Ne pas vider le fil public (le MJ le tient à 1–3 beats). Ne pas réécrire
les fiches `pc-sheets`. Ne pas « résumer » les mémoires PJ à leur place.

### Pliage (campagne qui s’allonge)

Si l’INDEX listerait **plus de ~12** chapitres :

- Rédiger `r01-recap-….txt` (puis `r02`, …) qui **plie** les plus anciens
  en bullets (faits + décisions + conséquences).
- Dans l’INDEX : une ligne vers le recap ; **ne plus** lister chaque
  vieux `10-*.txt`. Les fichiers chapitre **restent** sur disque.
- L’INDEX ne garde en liste fine que le recap + les **chapitres récents**.

## Consulter — procédure

1. Lire `INDEX.txt` puis `etat.txt`.
2. Trou (« c’était qui déjà ? », « on a promis quoi ? ») : **un**
   chapitre ou recap nommé dans l’INDEX, ou `mj.txt` si c’est un secret
   / une horloge.
3. S’arrêter. Ne pas précharger le dossier.

Le skill MJ (`.cursor/skills/cof-gm/SKILL.md`) fait ça au (re)démarrage
si la chronique existe. Toi tu ne joues pas la scène.

## Qui a le droit de lire quoi

| Fichier | MJ | Agent PJ | Fil public |
|---------|----|----------|------------|
| `INDEX.txt` / `etat.txt` / `1N-*.txt` / `r0N-*.txt` | oui | **non** (ils ont `pc-memory` + public) | non |
| `mj.txt` | oui | **interdit** | **interdit** |

Les chapitres ne contiennent que des **faits de table** (déjà perçus).
Les secrets non révélés : **seulement** `mj.txt` (et le kit).

## Style

- Phrases courtes, listes à tirets, noms propres stables.
- Une décision PJ = une ligne (« ils refusent l’hospitalité de X »).
- Une conséquence = une ligne (« Y s’enfuit vers Z »).
- Pas de « peut-être », pas de relancer l’intrigue, pas de conseil de jeu.

### Gabarit chapitre (densité cible)

```
CHAPITRE 10 — L’auberge de Besse
================================
Lieu / moment : Besse, soir, session 1

FAITS (table)
-------------
- Les PJ arrivent gelés ; l’aubergiste Maël les loge contre des corvées.
- Rumeur : disparitions sur le col depuis la dernière lune.

DÉCISIONS PJ
------------
- Ils acceptent de monter au col à l’aube, pas de rester au village.

CONSÉQUENCES
------------
- Maël fournit pain et lanterne. Un chasseur refuse de les guider.

PNJ / LIEUX
-----------
- Maël (aubergiste, inquiet, hospitable)
- Col des Monts Vierges (objectif lendemain)

SUSPENS
-------
- Qui guide ; ce qu’il y a réellement au col (non vu)
```

### Résumé INDEX (densité cible)

```
RÉSUMÉ
------
Groupe de 4 à Besse. Ils montent au col demain. Disparitions rumurées.
Rien vu des orcs. Maël allié fragile. Horloge perçue : lune / disparitions.

CHAPITRES
---------
10-auberge-besse.txt  Accueil Maël ; décision : partir à l’aube.
```

## Anti-patterns

- Append infini dans INDEX / etat (on **réécrit**)
- Un fichier par réplique ou par round de combat
- Jets, DD, NC, PV, noms de règles LB
- Secrets dans un chapitre ou dans INDEX
- Relire tout `gm-kits/<slug>/` « pour être sûr »
- Faire jouer ou incarner un PJ pendant le compactage
- Effacer les vieux chapitres après pliage
- Donner `mj.txt` à un agent PJ
- Dupliquer le kit (la chronique = **ce qui s’est passé**, pas le scénario)

## Lien avec les autres skills

- Conduite de partie : **`.cursor/skills/cof-gm/SKILL.md`** (lit INDEX +
  etat au (re)démarrage ; déclenche ce skill **sur demande**)
- Compagnons IA : **`.cursor/skills/cof-pj/SKILL.md`** (ne lisent pas
  `docs/chronicles/`)
- Fabriquer un kit : **`.cursor/skills/cof-gm-kit/SKILL.md`**
