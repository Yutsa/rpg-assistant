# Consignes d’extraction COF (livre de règles)

Source : fichiers `pages/page-NNN.txt` (numéro = page du PDF = page du sommaire).

## Nettoyage obligatoire

- Supprimer le filigrane acheteur (`WILLISSECK`, email, `202608/…`).
- Supprimer en-têtes / pieds (`PAGE 20  PARTIE I`, `INTRO`, `PERSO`, `RÈGLES`, lettres isolées de filet).
- Recoller les césures de fin de ligne (`maî‑\ntise` → `maîtrise`).
- Corps en **Markdown**. Conserver formules, DM, DEF, NC, tests.

## Éléments à produire

Chaque objet nommé du jeu = un `elements[]` distinct.

| kind | Quand |
|---|---|
| `people` | Peuple jouable (demi-elfe, nain, …) |
| `profile` | Profil (arquebusier, magicien, …) |
| `voie` | Voie de profil, de peuple ou de prestige |
| `capacity` | Capacité rang 1–5 (ou 4–8 prestige). `parent_kind=voie`, `parent_name=…` |
| `equipment` | Arme, armure, matériel, munition |
| `rule` | Règle mécanique nommable (test, surprise, round, critique, …) |
| `creature` | Fiche d’opposition |
| `magic_item` | Objet magique nommé |
| `spell` | Sort identifié (`*` dans le nom de capacité) — en plus de `capacity` |
| `table` | Tableau récapitulatif |
| `scenario` | Scénario |
| `npc` | PNJ nommé (scène, prétiré) |
| `glossary_term` | Terme défini |
| `setting` | Lieu / nation des Terres d’Osgild |

## Champ `data` (JSON objet, pas de chaîne)

**people** : `stat_modifiers`, `age_start`, `lifespan`, `size_range`, `weight_range`, `traits`, `typical_names`, `voie_choices`

**profile** : `family` (`aventuriers`\|`combattants`\|`mages`\|`mystiques`), `hp_per_level`, `recovery_die`, `chance_points_bonus`, `weapon_proficiencies`, `armor_proficiencies`, `starting_equipment`, `voies` (liste de noms)

**voie** : `voie_type` (`profile`\|`people`\|`prestige`\|`generic`), `family`, `profile`, `rank_min`, `rank_max`

**capacity** : `rank` (int), `action` (`G`\|`M`\|`A`\|`L`\|`P` ou null), `is_spell` (bool), `voie`

**creature** : `nc`, `creature_type`, `stats` (AGI/CON/FOR/PER/CHA/INT/VOL, `*` via `starred_stats`), `defense`, `hp`, `initiative`, `attacks` `[{name,bonus,damage,notes}]`, `abilities` `[{name,action,text}]`

**equipment** : `category`, `damage`, `defense_bonus`, `price`, `range`, `properties`

**magic_item** : `category`, `rarity_or_level`, `price`

Ne pas inventer. Si une valeur n’est pas dans le texte, omettre la clé.
