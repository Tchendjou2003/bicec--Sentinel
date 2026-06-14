# Et s'il faudrait que ce soit les structures qui s'adaptent à Sentinel ?

> Document de réflexion stratégique — 28 mai 2026
> Doctrine v2 consolidée après discussion utilisateur

---

## L'approche "logiciel opinioné"

C'est ce que font SAP, Salesforce, et tous les grands ERP : **ce n'est pas le logiciel qui s'adapte à ton chaos organisationnel, c'est toi qui alignes tes processus sur les bonnes pratiques du logiciel.**

Et la bonne nouvelle, c'est que Sentinel a déjà un modèle très clair. Il suffit de le formaliser.

---

## Ce que Sentinel exige réellement

Si on épure le workflow au maximum, Sentinel repose sur **3 fonctions universelles séquentielles** (la chaîne workflow) et **1 rôle stratégique transverse** (le pilotage), que **toute organisation au monde possède**, peu importe comment elle les appelle :

| Catégorie | Fonction Sentinel | Rôle technique | Ce que ça veut dire |
|---|---|---|---|
| **Workflow** | L'Auditeur | `AUDIT` | Constate, rédige, **valide la clôture en fin de chaîne** |
| **Workflow** | Le Responsable | `DM` | Reçoit, s'engage, **peut porter un recours d'échéance** |
| **Workflow** | L'Exécutant | `ETP` | Réalise concrètement le travail de mise en conformité. **≥ 1 par entité (non négociable)** |
| **Stratégique** | La Direction Générale | `DG` | **Pilote** via dashboard + indicateurs (recours actifs, statuts des recommandations). **Peut aussi être audité ou exécutant** comme tout collaborateur |

La chaîne workflow Constat → Responsabilité → Exécution est **fermée par l'Audit lui-même** (qui valide la clôture), **pas** par la Direction Générale. La DG intervient en transverse : elle observe les indicateurs globaux (notamment les recours actifs), prend des décisions stratégiques, et peut elle-même être destinataire d'une recommandation. La story 3.7 *"soumission exclusive DG"* ajoute à ce rôle stratégique une capacité de soumission directe et une vue globale des recours en cours.

Un hôpital appelle ça "Inspecteur → Chef de service → Infirmier référent" + "Directeur d'hôpital".
Une banque appelle ça "Auditeur → Directeur Métier → Correspondant ETP" + "Direction Générale".
Une ONG appelle ça "Contrôleur → Coordinateur → Agent terrain" + "Direction exécutive".

**Peu importe les noms : la chaîne Constat → Responsabilité → Exécution existe partout, et il existe toujours un acteur stratégique qui pilote au-dessus.**

---

## Ce que l'organigramme apporte (et seulement ça)

L'organigramme dans Sentinel ne sert **pas** au workflow. Le workflow est piloté par les rôles (`AUDIT → DM → ETP`, fermé par AUDIT), pas par la position dans l'arbre.

L'organigramme sert **uniquement** à deux choses :

1. **Le périmètre de visibilité** : Un Responsable ne voit que les recommandations de son département et ses sous-entités.

   Cela signifie que la profondeur et la forme de votre arbre **dictent qui voit quoi**. Si vous structurez plat (DG → 50 services sans niveau intermédiaire), chaque Responsable est isolé dans son service ; si vous structurez profondément (DG → Pôles → Directions → Services), un Responsable de Pôle voit l'ensemble de ses Directions et Services. L'organigramme n'a pas d'impact sur le **workflow**, mais il dicte le **périmètre de visibilité**. **Choisir sa structure, c'est choisir qui voit.**

2. **L'assignation** : L'Audit choisit à quel département (et donc à quel Responsable) adresser la recommandation.

Donc l'Audit Admin peut structurer son organigramme comme il veut : DG → Départements → Services, ou DG → Pôles → Cellules — **ça ne change rien au workflow**. Ce qui compte, c'est que chaque nœud de l'arbre ait un Responsable et au moins un Exécutant rattachés.

---

## Ce que ça implique concrètement pour l'UX

Au lieu de présenter la création d'organigramme comme "dessinez votre structure", on la présente comme un **processus d'onboarding guidé en 4 étapes** :

### Étape 1 — "Qui audite ?"

> *"Créez votre équipe d'audit. Ces utilisateurs pourront créer, suivre et valider la clôture des recommandations."*

L'Audit Admin crée les comptes avec le rôle AUDIT. Pas besoin d'organigramme pour ça.

### Étape 2 — "À qui s'adressent vos recommandations ?"

> *"Créez les entités de votre organisation qui reçoivent des recommandations. Chaque entité aura un Responsable."*

Ici, l'Audit Admin crée son arbre. Mais la question posée n'est plus "construisez votre organigramme" (vague et intimidant), c'est **"listez les entités auxquelles vous adressez des recommandations"** (concret et orienté métier).

Pour chaque entité créée, on lui demande immédiatement : "Qui est le Responsable de cette entité ?" → création du compte DM dans la foulée.

### Étape 3 — "Qui exécute ?"

> *"Pour chaque entité, désignez **au moins un** correspondant qui mettra en œuvre les recommandations."*

Création des comptes ETP rattachés à chaque département. **Validation bloquante** : on ne sort pas de cette étape tant qu'au moins un ETP n'est pas désigné par entité créée à l'étape 2.

### Étape 4 — "Qui pilote ?"

> *"Désignez la Direction Générale (ou son équivalent). Cette personne aura accès au dashboard global des indicateurs (recours actifs, statuts des recommandations) et pourra soumettre directement des recommandations. Elle peut aussi être destinataire d'une recommandation, comme tout collaborateur."*

Création du compte DG en fin de parcours. **1 DG obligatoire** par cohérence avec le rôle stratégique.

---

## Le contrat de Sentinel

On documente clairement les **pré-requis non négociables** :

> **Pour utiliser Sentinel, votre organisation doit :**
>
> 1. Avoir une équipe d'audit interne (au moins 1 personne) qui constate, rédige et valide la clôture
> 2. Identifier les entités auxquelles elle adresse des recommandations
> 3. Pour chaque entité, désigner un Responsable qui s'engage sur les recommandations et peut porter un recours d'échéance
> 4. Pour chaque entité, désigner **au moins un Exécutant** qui réalisera concrètement les actions. Cette règle est non négociable : Sentinel exige qu'à chaque action corresponde un acteur identifié, c'est la base de l'auditabilité. Si une entité n'a qu'une personne en propre, le Responsable doit créer un compte Exécutant nominal (qui peut être lui-même sous un autre profil, ou un agent dédié). Le **cumul Responsable+Exécutant sur un même compte est interdit**.
> 5. Désigner une **Direction Générale** (ou son équivalent) qui aura une vision transverse des indicateurs et pourra soumettre directement des recommandations. La DG n'est pas le validateur final du workflow (c'est l'Audit qui ferme la chaîne), mais elle pilote stratégiquement et peut être elle-même auditée.

Ce paragraphe doit apparaître dans la doc d'installation, dans l'écran d'onboarding, et en tooltips du formulaire.

---

## Ce que la story 3.7 a déjà posé

La story 3.7 (livrée) donne à la Direction Générale deux prérogatives qui complètent son rôle stratégique :

1. **Soumission exclusive** : la DG peut soumettre directement des recommandations, sans passer par la séquence AUDIT → DM → ETP.
2. **Vision globale des indicateurs** : la DG a accès à un dashboard agrégé des recours actifs et de l'état des recommandations à l'échelle de toute l'organisation.

Ces deux fonctions confirment que la DG est un **acteur transverse** (pilotage + soumission directe) et non un maillon séquentiel du workflow.

---

## Ce qui change dans le code (très peu)

| Changement | Effort |
|---|---|
| Renommer les libellés `DM` → `Responsable` et `ETP` → `Exécutant` dans l'UI (labels, sidebar, tooltips) — internals (`Role.DM`, `PENDING_DM_REVIEW`) inchangés | ~1 demi-journée |
| Ajouter un écran d'onboarding 4 étapes (Audit / Entités+Responsables / Exécutants / DG) avec validation bloquante ≥ 1 ETP par entité et 1 DG total | **~1 story (3-4 jours)** |
| Bouton "+" contextuel dans l'arbre avec parent pré-rempli | ~1 demi-journée |
| Documenter le "Contrat Sentinel" (5 prérequis + doctrine ETP-min + RBAC arbre = visibilité) dans un encart d'aide + tooltips | ~3 heures |
| Empty-state pédagogique sur `/auth/organigramme/` quand 0 département | ~1 demi-journée |

**Le workflow, le RBAC, le FSM, les migrations — rien ne bouge.** C'est purement de l'habillage UX et de la documentation.

---

## Pourquoi c'est la bonne approche

1. **Le modèle Auditeur → Responsable → Exécutant + Pilote stratégique est universel.** Toute organisation qui fait du suivi de recommandations a ces 4 fonctions, même si elle les appelle autrement.
2. **L'organigramme est libre.** Sentinel ne dicte pas ta structure hiérarchique, il dicte juste qu'il faut des gens dans 4 rôles fonctionnels — et la forme de ton arbre déterminera qui voit quoi.
3. **C'est beaucoup moins risqué.** Un workflow configurable est un projet monstre avec des edge cases infinis. Un workflow fixe avec un bon onboarding est simple, testable et maintenable.

La seule chose à faire c'est **mieux communiquer** ce contrat à l'utilisateur pour qu'il ne se sente pas perdu devant un formulaire vide.
