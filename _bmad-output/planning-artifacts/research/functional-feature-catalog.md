# Catalogue Détaillé des Fonctionnalités — Sentinel

Ce catalogue présente l'ensemble des capacités fonctionnelles de la plateforme Sentinel, organisées par rôle utilisateur. Il sert de document de référence pour les présentations stratégiques et la formation des utilisateurs à la BICEC.

---

## 1. Auditeur Interne (AU) — Le Chef d'Orchestre
L'Auditeur Interne est le garant de la probité du système. Il initialise les recommandations, supervise le workflow et assure la clôture cryptographique.

| ID | Fonctionnalité | Description & Règles | Valeur Métier |
| :--- | :--- | :--- | :--- |
| **UC1** | **Créer recommandation (unitaire)** | Saisie manuelle d'une recommandation individuelle via formulaire (Source, Priorité, Échéance, Pièces Jointes). | Permet de réagir immédiatement après un constat d'audit ponctuel. |
| **UC2** | **Créer par lots (Bulk)** | Interface de saisie rapide type grille pour créer plusieurs recommandations simultanément. | Réduction radicale de la friction administrative post-mission. |
| **UC3** | **Correction/Suppression (Brouillon)** | Modification ou "Soft Delete" possible *uniquement tant que la reco n'est pas assignée*. | Droit à l'erreur sans compromettre l'intégrité du workflow officiel. |
| **UC4** | **Importer historique (Atomique)** | Import de masse via template Excel. Transaction "Tout ou Rien" avec tag `IMPORTED`. | Migration sécurisée de l'existant sans "trou" dans la traçabilité. |
| **UC5** | **Triage complexe** | Phase d'auto-assignation pour analyser le périmètre avant attribution définitive. | Évite d'envoyer des dossiers mal qualifiés aux directions métier. |
| **UC6** | **Assigner DM cible** | Attribution formelle à un Directeur Métier (DM). Déclenche le chrono d'échéance. | Établit la responsabilité de traitement au premier niveau hiérarchique. |
| **UC7** | **Ré-assignation d'urgence** | Transfert manuel d'une recommandation d'un DM absent vers un autre DM. | Garantit la continuité du service même en cas de vacance de poste. |
| **UC8** | **Examen des preuves** | Audit des documents soumis par le DM après validation métier interne. | Deuxième niveau de contrôle (LOD2) pour valider la résolution effective. |
| **UC9** | **Clôturer & Scellement HMAC** | Clôture finale avec génération du hash SHA-256 (ADR-07). Dossier verrouillé. | Preuve infalsifiable et opposable aux régulateurs (COBAC). |
| **UC10** | **Rejet motivé** | Renvoi d'un dossier au DM avec commentaire obligatoire justifiant le refus. | Maintient la qualité de la correction en refusant les preuves insuffisantes. |
| **UC11** | **Gestion des reports** | Approbation ou refus des demandes d'allongement de délai soumises par les DM. | L'Audit garde le contrôle absolu sur le calendrier de conformité. |
| **UC12** | **Dashboard Audit** | Vue d'ensemble filtrable par statut, priorité et source sur l'ensemble de la banque. | Pilotage stratégique de l'avancement global des recommandations. |
| **UC13** | **Consultation Timeline** | Accès à l'historique complet (Transitions, Acteurs, Dates) de chaque dossier. | Transparence totale : qui a fait quoi, et quand ? |
| **UC14** | **Gérer intérim DM** | Paramétrage centralisé des délégations temporaires de droits. | Sécurité : les intérims sont maîtrisés par l'Audit, pas par l'IT. |
| **UC15** | **Template d'import** | Téléchargement du fichier Excel normalisé pour la préparation des données. | Standardisation des données entrantes pour éviter les erreurs d'import. |
| **UC16** | **Rapport PDF Statistique** | Génération instantanée d'un bilan chiffré de conformité en format document. | Support prêt à l'emploi pour les Comités de Direction et de Risques. |

---

## 2. Directeur Métier (DM) — Le Responsable
Le DM reçoit les recommandations, coordonne ses équipes et engage sa responsabilité en validant les preuves d'exécution.

| ID | Fonctionnalité | Description & Règles | Valeur Métier |
| :--- | :--- | :--- | :--- |
| **UC1** | **Dashboard DM** | Vue centralisée des recommandations assignées à sa Direction uniquement. | Focus exclusif sur les tâches incombant à son périmètre. |
| **UC2** | **Délégation à l'ETP** | Affectation d'une recommandation à un Employé Traitant (ETP) opérationnel. | Décharge le DM du travail de collecte tout en gardant la supervision. |
| **UC3** | **Gérer intérim ETP** | Désignation temporaire d'un remplaçant pour la collecte de preuves. | Évite le blocage des dossiers lors des congés ou missions terrain. |
| **UC4** | **Examen interne des preuves** | Vérification des documents chargés par ses collaborateurs (ETP). | Premier niveau de contrôle métier avant envoi à l'Audit. |
| **UC5** | **Validation + PV Recette** | Signature de la résolution. *Exemption de commentaire si PV de recette uploadé.* | Accélère le workflow pour les DM tout en certifiant la qualité. |
| **UC6** | **Rejet vers ETP** | Renvoi de la preuve à l'ETP pour correction (Motif obligatoire). | Garantie que les preuves soumises à l'Audit sont déjà "propres". |
| **UC7** | **Soumission directe** | Capacité à envoyer les preuves sans passer par un ETP (DM Porteur). | Flexibilité pour les dossiers sensibles ou les directions à faible staff. |
| **UC8** | **Demande de report** | Formule une demande justifiée de délai avant l'échéance. | Remplace les emails officieux par une demande tracée et motivée. |
| **UC9** | **Historique versions** | Accès aux documents précédemment rejetés pour comparaison. | Trçabilité des itérations jusqu'à la conformité. |
| **UC10** | **Pilotage par Dashboard** | Indicateurs visuels (Aging, Urgence) sur ses propres dossiers. | Priorisation immédiate des dossiers critiques ou en retard (`OVERDUE`). |

---

## 3. Employé Traitant (ETP) — L'Opérateur
L'ETP est l'utilisateur terrain qui collecte, justifie et transmet les preuves documentaires.

| ID | Fonctionnalité | Description & Règles | Valeur Métier |
| :--- | :--- | :--- | :--- |
| **UC1** | **To-Do List (Personal)** | Liste des dossiers délégués par son DM, classée par urgence. | Organisation claire du travail quotidien sans dispersion. |
| **UC2** | **Soumission de preuves** | Upload de fichiers (PDF, Excel...) avec commentaire obligatoire. | Formalisation de la résolution technique du risque. |
| **UC3** | **Ré-soumission (Fix)** | Capacité à modifier son dossier après un rejet du DM ou de l'Audit. | Cycle d'amélioration contenu dans l'outil jusqu'à validation. |
| **UC4** | **Historique versions** | Consultation de ses propres soumissions passées par dossier. | Mémoire opérationnelle des documents de preuve fournis. |
| **UC5** | **Feedback Rejet** | Consultation directe du motif de rejet formulé par le DM ou l'Audit. | Compréhension immédiate de ce qui doit être corrigé pour réussir. |
| **UC6** | **Détail Recommandation** | Accès aux rapports d'audit originaux liés à sa tâche. | Compréhension parfaite du "Pourquoi" de la recommandation. |
| **UC7** | **Brouillon (Draft)** | Enregistrement de preuves sans soumission finale (Travail en cours). | Permet de collecter les preuves au fil de l'eau avant de valider. |

---

## 4. Direction Générale (DG) — Le Superviseur Stratégique
La DG utilise Sentinel comme un baromètre d'exposition aux risques réglementaires.

| ID | Fonctionnalité | Description & Règles | Valeur Métier |
| :--- | :--- | :--- | :--- |
| **UC1** | **Supervision Macro** | Dashboard haut niveau avec Volume, Retard (`OVERDUE`) et Taux de Résolution. | Vision 360° du profil de risque de la banque en temps réel. |
| **UC2** | **Filtre par Source** | Focus spécifique sur les recos COBAC, Commissaires aux Comptes (CAC). | Priorisation des risques "Sanctions" (Régulateurs externes). |
| **UC3** | **Filtre Statut/Priorité** | Isolation des dossiers "Critiques" et "Bloquants". | Gestion des urgences absolues au niveau top-management. |
| **UC4** | **Filtre Aging (> 24 mois)** | Identification des "Vieux Dossiers" hérités non résolus. | Nettoyage structurel de la dette de conformité. |
| **UC5** | **Rapport Synthèse Imprimable**| Export optimisé (CSS Print) pour les supports physiques de réunion. | Information fiable et synchronisée pour les réunions de la DG. |
| **UC6** | **Détail dossier (Read)** | Consultation du contenu d'une recommandation spécifique. | Capacité de zoom sur un dossier sensible lors d'un arbitrage. |
| **UC7** | **Timeline Audit Trail** | Consultation du journal d'événements pour comprendre un blocage. | Identification factuelle des goulots d'étranglement hiérarchiques. |
| **UC8** | **Droit de suite (Upload)** | Soumettre des preuves directement (Cas de force majeure). | Flexibilité exceptionnelle pour la haute direction. |
| **UC9** | **Arbitrage de délai** | Demander ou accorder un report de manière exceptionnelle. | Pilotage politique des délais très longs (projets de transformation). |
| **UC10**| **Stats par Direction** | Visualisation du "Top des directions en retard". | Incitation à la performance pour les Directeurs Métiers. |
| **UC11**| **To-Do List DG** | Suivi des rares dossiers assignés directement à la DG (Risque IT/LBC). | Pilotage des recommandations transversales stratégiques. |
| **UC12**| **Consultation Timeline** | Historique complet et inaltérable des interactions stratégiques. | Sécurité de la prise de décision au plus haut niveau. |

---

## 5. Auditeur Externe (COBAC / BEAC) — Le Régulateur
Un accès restreint et sécurisé pour certifier la transparence de la banque envers les autorités.

| ID | Fonctionnalité | Description & Règles | Valeur Métier |
| :--- | :--- | :--- | :--- |
| **UC1** | **Connexion Mission** | Compte temporaire avec credentials locaux (Hors LDAP/AD). | Sécurisation de l'infrastructure BICEC lors des contrôles. |
| **UC2** | **Accès Périmètre Mission** | Cloisonnement strict (RLS) : l'auditeur ne voit *que* ce qui est autorisé. | Confidentialité : les autres directions sont invisibles à l'inspecteur. |
| **UC3** | **Filtre Temporel** | Consultation limitée à une période de contrôle spécifique. | Respect du mandat exact de la mission du régulateur. |
| **UC4** | **Vérification HMAC** | Pastille visuelle confirmant l'intégrité du hash SHA-256. | Preuve mathématique que les données n'ont pas été altérées. |
| **UC5** | **Archive ZIP Autonome** | Téléchargement d'un lot complet (Fiche + Preuves) en 1 clic. | Autonomie de l'inspecteur, gain de temps massif pour l'Audit. |
| **UC6** | **Consultation Preuves** | Visualisation directe des documents validés (PDF/Excel). | Preuve concrète de l'action corrective devant le régulateur. |

---

## 6. IT Admin / Support — Le Gardien Applicatif
L'Administrateur IT se limite aux opérations qu'il doit effectuer *dans l'application Sentinel* via l'administration Django, évitant ainsi toute sur-ingénierie redondante avec ses outils d'infrastructure au niveau serveur (monitoring OS, gestion backups `pg_dump`, routage TLS Nginx).

| ID | Fonctionnalité | Description & Règles | Valeur Métier |
| :--- | :--- | :--- | :--- |
| **UC1** | **Gérer l'organigramme** | Définition des Directions, Départements et hiérarchies SQL. | Fondement absolu du cloisonnement des données (RLS). |
| **UC2** | **Gérer les utilisateurs** | Création, modification, attribution de rôles RBAC et révocation de comptes. | Verrou de sécurité sur les accès, permettant un blocage immédiat d'un compte compromis. |
| **UC3** | **Monitorer les tâches Q2** | Accès au dashboard Django-Q2 pour visualiser les emails asynchrones. | Diagnostic rapide si les rappels d'échéances aux DM ne partent pas. |
| **UC4** | **Consulter l'Audit Log** | Visualisation du journal de sécurité métier inaltérable. | Traçabilité absolue en cas de suspicion de modification frauduleuse d'un audit (cas de force majeure). |
| **UC5** | **Gérer paramètres globaux** | Modifier des variables de configuration métier via interface. | Agilité pour ajuster l'application (ex: email de l'expéditeur) sans devoir relancer un déploiement complet. |

---

## 7. KPIs de Succès & Valeur Stratégique
Pour votre présentation, voici comment ces fonctionnalités contribuent aux objectifs stratégiques :

*   **Taux d'Adoption (Focus UX) :** La saisie multiple (UC2 Audit) et l'exemption de commentaire via PV (UC5 DM) garantissent une adhésion immédiate des cadres.
*   **Intégrité Réglementaire (Sécurité) :** Le cumul du RLS (cloisons étanches) et du sceau final (UC9 Audit) rend Sentinel **opposable juridiquement**.
*   **Efficacité Opérationnelle (Focus Process) :** La réduction radicale des "relances manuelles" (Automation Q2) permet à l'Audit de se concentrer sur l'analyse de fond plutôt que sur le secrétariat.

explique :     UC5["Trier et s'auto-assigner\n(triage complexe)"]
L'UC5 : Trier et s'auto-assigner (triage complexe) est une fonctionnalité tampon stratégique située au tout début du cycle de vie d'une recommandation. Elle répond au besoin de l'Audit Interne d'analyser un dossier avant de désigner officiellement un responsable.

Voici le détail de cette fonctionnalité :

1. Qu'est-ce que le "Triage" ?
Souvent, après une mission d'inspection (ex: par la COBAC), les recommandations reçues sont brutes ou transversales. L'auditeur ne sait pas toujours immédiatement quel Directeur Métier (DM) est le "vrai" porteur de la correction.

Le triage permet à l'auditeur de garder la recommandation dans un état de "préparation" sans encore déclencher les chronomètres de retard (OVERDUE) pour une direction qui ne serait peut-être pas la bonne.

2. Pourquoi parler de "Triage Complexe" ?
On utilise cette fonction dans trois scénarios critiques à la BICEC :

La recommandation transverse : Elle impacte à la fois l'IT, les Risques et les Opérations. L'Audit doit discuter en interne pour décider qui sera le lead.
La qualification réglementaire : L'Auditeur doit parfois enrichir la recommandation avec des documents internes ou des précisions avant qu'elle ne soit actionnable par le métier.
L'incertitude hiérarchique : En cas de réorganisation d'une direction, l'Audit s'auto-assigne le dossier pour éviter qu'il ne tombe dans un "vide" organisationnel.
3. Fonctionnement technique (S'auto-assigner)
Mécanisme : L'auditeur clique sur "S'auto-assigner". Dans la base de données, le champ assigned_to pointe temporairement vers le compte de l'auditeur lui-même (ou son pool).
Visibilité : La recommandation n'apparaît pas encore dans le dashboard d'aucun DM. Elle reste dans la "pile de triage" de l'Audit.
Audit Trail : Le système trace : "L'auditeur X a pris en charge le triage du dossier".
4. Valeur ajoutée pour la banque
Évite le "Ping-pong" administratif : Sans triage, l'Audit assignerait au hasard, le DM rejetterait en disant "ce n'est pas moi", et le dossier perdrait en crédibilité.
Précision des échéances : Le compte à rebours de résolution pour le métier ne commence que lorsque le triage est fini et que le DM cible est validé (UC6).
Souveraineté de l'Audit : Cela renforce le rôle de l'Audit comme "filtre intelligent" plutôt que simple passe-plat de documents.
En résumé, c'est la salle d'attente intelligente de Sentinel où les recommandations sont qualifiées avant d'être envoyées au front métier.



quelle est la difference entre UC4 : Importer historique (atomique) et UC2 : Créer recommandations (bulk / par lots) n'y a t'il pas de similitude 
C'est une excellente question, car elles se ressemblent effectivement sur la finalité (créer plusieurs lignes d'un coup). Cependant, elles répondent à des besoins opérationnels et techniques très différents dans le contexte d'une banque comme la BICEC.

Voici les différences fondamentales entre la saisie par lots (Bulk) et l'import historique (Atomique) :

1. La source des données
UC2 (Bulk / Par lots) : C'est une interface de saisie manuelle rapide dans l'application. Imaginez une grille (type Excel) directement dans votre navigateur. L'auditeur vient de terminer une mission, il a 10 nouvelles recommandations en tête et il les tape une par une très vite sans changer de page.
UC4 (Importer historique) : C'est un chargement de fichier externe. L'auditeur télécharge un template Excel officiel, le remplit hors-ligne (souvent avec des données provenant d'anciens fichiers de suivi de la banque), puis l'uploade dans Sentinel.
2. Le moment de l'utilisation
UC2 (Bulk) : Utilisé au quotidien pour les nouvelles missions. C'est un outil de productivité pour la phase de "Run".
UC4 (Import) : Utilisé principalement lors du lancement du projet (Go-Live) pour injecter les 450+ recommandations existantes, ou après de très grandes missions nationales/internationales où les données ont déjà été pré-remplies dans un fichier de travail.
3. Les contraintes techniques et "l'Atomisme"
UC2 (Bulk) : Si vous saisissez 10 recommandations et qu'il y a une erreur sur la 10ème, les 9 premières peuvent être enregistrées (selon le design UX) ou vous corrigez juste la ligne en erreur. C'est une interaction fluide.
UC4 (Import) - L'Atomisme : C'est une sécurité critique (FR9). Si votre fichier Excel contient 1 000 lignes et que la ligne 999 a une date invalide, Sentinel rejette les 1 000 lignes.
Pourquoi ? Pour éviter que l'auditeur ne se retrouve avec une base "polluée" (500 lignes importées, 500 manquantes) sans savoir exactement où il s'est arrêté. On repart de zéro tant que le fichier n'est pas 100% parfait.
4. Le marquage et la traçabilité
UC2 (Bulk) : Les recommandations sont marquées comme créées nativement dans l'outil par l'auditeur X.
UC4 (Import) : Elles reçoivent un tag inaltérable IMPORTED. Cela permet, 2 ans plus tard, de savoir que cette donnée ne vient pas d'une saisie directe dans l'application mais d'une migration de données historiques (précieux pour les contrôles COBAC).
En résumé :
Caractéristique	UC2 : Créer par lots (Bulk)	UC4 : Importer historique
Interface	Tableau de saisie en ligne (Web)	Upload de fichier Excel (Template)
Utilisation	Saisie de nouvelles recommandations	Migration de données existantes
Rigueur	Souple, aide à la saisie	Atomique (Tout ou Rien)
Tag Audit	Standard	Marqué IMPORTED
La similitude, c'est effectivement le gain de temps. Mais là où l'UC2 est un confort de saisie, l'UC4 est un outil de migration sécurisé.