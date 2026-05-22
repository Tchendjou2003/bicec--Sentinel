# Rapport d'Analyse des Remarques IA sur la Story 3.1

Ce rapport fait suite à l'analyse critique générée par une IA tierce concernant le plan d'implémentation de la **Story 3.1 — To-Do List Filter (Historique vs Récent)**. L'objectif est de démêler les vrais problèmes des faux positifs, tout en respectant le périmètre (scope) et la chronologie de l'Epic 3.

## 1. À appliquer immédiatement (Vrais Positifs pour la Story 3.1)

Ces remarques sont fondées et pointent vers des lacunes techniques du plan actuel qui pourraient causer des bugs ou des erreurs de compilation. Elles **doivent être intégrées** au plan de la Story 3.1.

*   **Correction des fichiers ciblés (Frontend)** : Le fichier `recommendation_filters.html` mentionné dans la Subtask 2.3 est effectivement un fichier mort (obsolète). Les filtres actuels se trouvent directement dans `recommendation_list.html`. Le plan doit être mis à jour pour cibler le bon fichier.
*   **Mise à jour des attributs `hx-include`** : Dans `recommendation_list.html`, les listes déroulantes de filtres utilisent un attribut explicite `hx-include="[name='source'],[name='status'],[name='priority'],[name='q']"`. L'ajout d'un nouveau filtre caché `import_status` nécessite impérativement d'ajouter `,[name='import_status']` à tous ces attributs pour ne pas perdre l'état lors de requêtes croisées.
*   **Correction de la Pagination** : Le template `recommendation_table.html` (lignes 96-99) construit les liens de pagination en dur. Il est crucial d'ajouter le paramètre `&import_status={{ current_import_status|urlencode }}` aux liens "Précédent" et "Suivant" pour maintenir le filtre en changeant de page.
*   **Absence de balise `<form>`** : La Subtask 2.4 suggère d'utiliser `$dispatch('submit')`, mais les filtres actuels ne sont pas enveloppés dans un `<form>`. Il faudra restructurer le HTML pour envelopper les filtres.
*   **Correction de l'attribut `user.is_auditor`** : Le plan suggère `{% if user.is_auditor %}`, mais le modèle `User` Sentinel ne possède pas cette propriété. Il faut utiliser `{% if user.role == 'AUDIT' %}`.
*   **Application du `WorkflowAccessMixin` à la vue Détail** : Le plan prévoit d'autoriser les DM/ETP sur la `RecommendationListView`. Cependant, s'ils voient la liste, ils doivent pouvoir cliquer pour voir le détail. Le mixin doit aussi remplacer `AuditRequiredMixin` sur `RecommendationDetailView`.
*   **Ajout des tests d'intégration RBAC** : Les tests suggérés (vérifier qu'un DM ne voit pas les DRAFTs, qu'un ETP ne voit que ses recommandations assignées, etc.) sont très pertinents et renforcent la Subtask 3.

## 2. À rejeter (Faux Positifs et erreurs d'analyse)

Ces remarques de l'IA sont incorrectes ou résultent d'une mauvaise lecture du plan ou des exigences. Elles **ne doivent pas** être appliquées.

*   **"Sélecteur universel non détaillé"** : L'IA affirme que la logique de branchement par rôle n'est pas décrite. C'est faux. La Subtask 1.2 du plan décrit explicitement les filtres à appliquer pour chaque rôle (Audit, DM, ETP).
*   **"import_tag edge case (blank=True, null=True)"** : L'IA s'inquiète de la gestion des valeurs nulles/vides. Le plan indique déjà de vérifier `isnull=False` et `exclude(import_tag="")`, ce qui gère parfaitement la structure de la base de données de Django pour ce champ.
*   **"NFR-SEC-05 — Audit Logs absents pour le filtre"** : L'IA suggère de logger les actions de filtrage. L'Audit Log est conçu pour tracer les *mutations* de données (création, assignation, modification), et non les requêtes de lecture (GET). Logger les filtres polluerait la base de données inutilement.

## 3. À reporter (Vrais Positifs, mais hors périmètre pour la Story 3.1)

Ces remarques sont architecturalement justes, mais elles débordent du cadre strict de la Story 3.1, qui se concentre uniquement sur la mise en place du filtre "Historique vs Récent" pour les DM/ETP.

*   **Prise en compte du rôle DG (Direction Générale)** : Le rôle `DG` existe bien dans le modèle. Cependant, l'User Story 3.1 précise explicitement : *"As a Directeur Métier (DM) ou ETP..."*. Les accès et vues spécifiques à la Direction Générale (Dashboard macro) font partie d'une autre Story dédiée au Reporting.
*   **Code couleur urgence (Rouge/Orange/Vert) (FR30)** : Le tableau actuel gère déjà l'affichage en rouge des échéances dépassées (`is_overdue`). L'implémentation d'une colorimétrie dynamique complète (R/O/V) est une tâche d'amélioration UI globale qui n'est pas strictement liée à la création du bouton de bascule "Historique/Récent".
*   **Tests de charge de performance (NFR-PERF-02)** : Le plan demande d'utiliser `select_related` pour prévenir les requêtes N+1, ce qui répond au besoin d'optimisation. L'écriture de benchmarks automatisés complets est disproportionnée pour cette Story et relève d'une tâche de QA technique transverse.
