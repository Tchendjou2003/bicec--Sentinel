# FAQ — Gestion des Recommandations Historiques et des Preuves

Ce document regroupe les questions fréquemment posées concernant l'importation de l'historique des recommandations de la BICEC, le cycle de vie des preuves (evidences), la gestion des rejets et le mécanisme de scellement cryptographique garantissant la conformité réglementaire (COBAC / RegTech).

---

## Sommaire
1. [Gestion des Recommandations Historiques](#1-gestion-des-recommandations-historiques)
   - [Comment sont importées les recommandations ?](#comment-sont-importées-les-recommandations-)
   - [Cas A : Recommandations historiques DÉJÀ traitées et closes](#cas-a--recommandations-historiques-déjà-traitées-et-closes)
   - [Cas B : Recommandations historiques EN COURS (actives)](#cas-b--recommandations-historiques-en-cours-actives)
2. [Gestion des Fichiers de Preuve & Sécurité](#2-gestion-des-fichiers-de-preuve--sécurité)
   - [L'Audit Interne peut-il télécharger les preuves ?](#laudit-interne-peut-il-télécharger-les-preuves-)
   - [Que deviennent les preuves rejetées/refusées ?](#que-deviennent-les-preuves-rejetéesrefusées-)
   - [Comment est géré le stockage lors du rejet de preuves, vis-à-vis du quota (20 Mo) ?](#comment-est-géré-le-stockage-lors-du-rejet-de-preuves-vis-à-vis-du-quota-20-mo-)
   - [Pourquoi y a-t-il une limite de 5 fichiers maximum par lot de soumission si le quota global est de 20 Mo ?](#pourquoi-y-a-t-il-une-limite-de-5-fichiers-maximum-par-lot-de-soumission-si-le-quota-global-est-de-20-mo-)
   - [Comment garantir que seules les preuves validées sont scellées à la clôture ?](#comment-garantir-que-seules-les-preuves-validées-sont-scellées-à-la-clôture-)
   - [Comment le scellement cryptographique empêche-t-il la falsification ?](#comment-le-scellement-cryptographique-empêche-t-il-la-falsification-)
3. [Déploiement et Création des Comptes (Prise en Main)](#3-déploiement-et-création-des-comptes-prise-en-main)
   - [Comment sont créés les comptes des utilisateurs et des administrateurs Sentinel ?](#comment-sont-créés-les-comptes-des-utilisateurs-et-des-administrateurs-sentinel-)
   - [Comment doit se passer la toute première prise en main après le déploiement ?](#comment-doit-se-passer-la-toute-première-prise-en-main-après-le-déploiement-)
   - [Comment faire la première prise en main de la gestion de l'organigramme ?](#comment-faire-la-première-prise-en-main-de-la-gestion-de-lorganigramme-)

---

## 1. Gestion des Recommandations Historiques

L'application Sentinel gère l'historique de l'ancien système (Word, Excel, PDF) grâce à un processus d'importation robuste et un aiguillage intelligent selon l'état réel des dossiers.

### Comment sont importées les recommandations ?
Toutes les recommandations historiques sont préparées par l'Audit Interne via un template Excel standardisé et importées de manière atomique (transaction tout-ou-rien).
*   **Statut initial** : Elles obtiennent directement le statut **`ASSIGNED`** (Assignée), contournant l'état `DRAFT` réservé aux nouvelles créations manuelles.
*   **Identification** : Elles reçoivent un tag inaltérable `import_tag="IMPORTED"`.
*   **Antériorité** : La date de création originale et l'échéance originale issues du fichier Excel sont préservées pour assurer des calculs exacts de vieillissement (*aging*) requis par la COBAC.

### Cas A : Recommandations historiques DÉJÀ traitées et closes
*Objectif : Archiver proprement les anciens dossiers résolus avec leurs preuves justificatives de l'époque.*

1.  **Dépôt de preuves** : Le Directeur Métier (DM) ou l'Employé Traitant (ETP) retrouve le dossier dans le "Backlog Historique" et y dépose les documents de preuve collectés à l'époque.
2.  **Coupe-file (PV de Recette signé)** : Pour éviter la friction administrative, le DM peut uploader directement le **PV de recette signé** de l'époque. Cette action **l'exempte d'écrire des commentaires obligatoires** lors de la validation.
3.  **Clôture et scellement** : L'Audit Interne examine les pièces et passe le dossier en statut **`CLOSED_RESOLVED`**. Le système calcule immédiatement l'empreinte cryptographique (Sceau Final) pour verrouiller le dossier.

### Cas B : Recommandations historiques EN COURS (actives)
*Objectif : Poursuivre le traitement de recommandations anciennes toujours actives au sein du workflow Sentinel.*

1.  **Bascule Opérationnelle** : Ces recommandations apparaissent dans le "Backlog Historique" des DMs et ETPs concernés.
2.  **Prise en main par le Workflow** : Le DM délègue la recommandation à un ETP, ce qui la fait basculer dans l'état standard **`IN_PROGRESS`**.
3.  **Demande de report** : Si l'échéance historique ne peut plus être tenue, le DM peut formuler une demande de report formelle dans Sentinel, avec une date ciblée et une justification détaillée. L'Audit Interne a le contrôle exclusif pour valider ou rejeter cette prolongation.
4.  **Résolution** : Le dossier suit le parcours classique (dépôt de preuves, validation DM, clôture Audit).

---

## 2. Gestion des Fichiers de Preuve & Sécurité

La traçabilité et l'immutabilité des preuves d'audit sont des exigences réglementaires clés. Sentinel applique un contrôle technique absolu sur les fichiers déposés.

### L'Audit Interne peut-il télécharger les preuves ?
**Oui, sans restriction.** 
Les auditeurs internes ont un droit de lecture complet sur toutes les pièces soumises par le Métier. Ils peuvent :
*   Consulter et télécharger individuellement chaque fichier depuis la fiche détaillée de la recommandation.
*   Télécharger en un clic une **archive ZIP consolidée** contenant l'intégralité des preuves validées pour un dossier.

### Que deviennent les preuves rejetées/refusées ?
**Elles ne sont jamais supprimées ni écrasées.**
Sentinel garantit une traçabilité historique totale pour prouver aux régulateurs qu'un véritable travail de contrôle a été effectué :
*   **Versionnage** : Lorsqu'un DM ou l'Audit rejette un document non conforme, le fichier est conservé et tagué historiquement (ex : `REJECTED_V1`).
*   **Accessibilité** : Le fichier rejeté reste consultable dans la frise chronologique (**Audit Trail / Timeline**) de la recommandation, accompagné du motif de rejet obligatoire saisi par le valideur.

### Comment est géré le stockage lors du rejet de preuves, vis-à-vis du quota (20 Mo) ?
L'application impose une limite d'upload unitaire de **6 Mo par fichier**, et un quota global cumulé de **20 Mo par recommandation** (NFR-SCA-01). Puisque le système garantit l'immutabilité et ne supprime jamais les preuves rejetées, la gestion se fait ainsi :
*   **Le quota s'applique uniquement à l'Actif :** La limite de 20 Mo est vérifiée uniquement sur la somme des tailles des preuves actuellement soumises ou validées (`Taille(Nouvelles Preuves + Preuves Actives Validées) <= 20 Mo`). L'export ZIP final ne concernera que ces preuves actives.
*   **Les preuves rejetées n'impactent pas le quota :** Les fichiers refusés sont historisés et "congelés" pour l'audit. Ils sont exclus du calcul des 20 Mo, ce qui laisse le champ libre à l'Employé Traitant (ETP) pour re-soumettre de nouvelles preuves valides sans être bloqué par un "Out of Space" virtuel.
*   **Capacité du Serveur :** L'accumulation des preuves rejetées (historique mort) consommera bien de l'espace disque. Le système prévoit une télémétrie et des alertes automatiques (RSSI) si le stockage serveur dépasse 80% de remplissage, permettant si besoin la bascule transparente du dossier `/media/` sur un NAS (stockage réseau externe).

### Pourquoi y a-t-il une limite de 5 fichiers maximum par lot de soumission si le quota global est de 20 Mo ?
Il y a une différence fondamentale entre le **quota global cumulé** d'une recommandation et la **limite par lot de soumission (batch)** :
*   **La limite globale de 20 Mo** concerne l'espace de stockage actif total alloué en base de données pour une recommandation. Tant que la somme totale des preuves actives (`PENDING` ou `ACCEPTED`) ne dépasse pas 20 Mo, l'ETP peut uploader des preuves.
*   **La limite de 5 fichiers max par soumission** est une règle de **sécurité applicative et de performance** lors du clic sur le bouton "Soumettre les preuves". Elle protège le serveur de plusieurs manières :
    *   **Prévention des Dénis de Service (DoS) et surcharge de calcul :** Le serveur Django effectue des opérations lourdes lors de la soumission de chaque fichier (validation des Magic Bytes réels, inspection de la structure interne des zips pour refuser les fichiers Excel `.xlsm` contenant des macros, calcul de l'empreinte SHA-256). Permettre d'uploader 50 ou 100 fichiers minuscules d'un coup mettrait le processeur du serveur à rude épreuve et risquerait de bloquer la base de données.
    *   **Qualité de l'audit :** Cela incite l'Employé Traitant (ETP) à consolider et sélectionner quelques preuves claires et de haute qualité plutôt qu'à téléverser en vrac des dizaines de captures d'écran désorganisées.
    *   **Gestion des re-soumissions :** Si le Directeur Métier rejette une preuve pour non-conformité, l'ETP peut tout à fait faire une **nouvelle soumission** (un nouveau lot de maximum 5 fichiers) pour compléter sa recommandation, tant que le volume total cumulé des preuves valides/actives ne dépasse pas 20 Mo.

### Comment garantir que seules les preuves validées sont scellées à la clôture ?
Le système filtre les documents selon leur statut technique pendant le workflow :
1.  **Statuts intermédiaires** : Les fichiers téléversés par l'ETP naissent en `DRAFT` (visible uniquement par lui), puis passent en `PENDING` (soumis au DM).
2.  **Approbation** : Seuls les fichiers qui ont été formellement acceptés par le DM puis validés par l'Audit obtiennent le statut final **`APPROVED`**.
3.  **Filtrage au scellement** : Au moment de la clôture (`CLOSED_RESOLVED`), Sentinel ignore les brouillons non soumis et les fichiers rejetés, et ne compile que les métadonnées de la recommandation et les fichiers au statut `APPROVED`.

### Comment le scellement cryptographique empêche-t-il la falsification ?
Sentinel applique un verrouillage mathématique par signature cryptographique **HMAC-SHA256** lors de la clôture :
1.  Le serveur calcule une empreinte unique (hash SHA-256) combinant les données textuelles de la recommandation et le contenu binaire exact des seuls fichiers de preuve validés (`APPROVED`), le tout signé par une clé secrète serveur.
2.  Cette signature finale (le **Sceau**) est enregistrée directement en base de données.
3.  **Garantie d'intégrité** : Si quelqu'un (y compris un administrateur ayant un accès direct à la base de données SQL) tente de modifier, supprimer ou remplacer un fichier de preuve après la clôture, le calcul du hash ne correspondra plus au Sceau enregistré. Le système lèvera immédiatement une alerte de corruption, invalidant la preuve falsifiée.

---

## 3. Déploiement et Création des Comptes (Prise en Main)

### Comment sont créés les comptes des utilisateurs et des administrateurs Sentinel ?
Dans Sentinel, par mesure de sécurité bancaire, un compte ne peut **jamais** être créé de bout en bout par une seule et même personne. L'application impose le "Principe des 4 yeux" (Aussi appelé *Maker / Checker*) :

1. **L'Initiateur (La Demande)** : Un membre du support technique remplit un formulaire de création avec le nom, le département et le rôle du futur utilisateur. À ce stade, **aucun compte n'est encore créé**, la demande est simplement mise en attente.
2. **Le Validateur (La Confirmation)** : Un deuxième administrateur reçoit une notification. Il vérifie les informations de la demande et clique sur "Approuver". C'est uniquement à cet instant précis que le compte utilisateur est réellement créé et activé.

> [!NOTE]
> Cette règle stricte s'applique à **tous les comptes**, qu'il s'agisse d'un simple employé, du Directeur de l'Audit, ou même d'un futur administrateur Sentinel. La sécurité prime avant tout.

### Comment doit se passer la toute première prise en main après le déploiement ?
Si le système exige obligatoirement deux personnes pour créer un compte (l'Initiateur et le Validateur), comment fait-on au tout début, juste après l'installation, quand le système est complètement vide ?

C'est là qu'intervient la phase de "Démarrage" (Bootstrap) :
1. **Le Super-Administrateur technique** : Lors de l'installation, l'équipe informatique crée un compte fantôme "Superuser" directement sur le serveur technique.
2. **Création des premiers vrais Admins** : Ce Superuser se connecte à Sentinel. Comme il possède les pleins pouvoirs exceptionnels de démarrage, il est autorisé à jouer **à la fois** le rôle de l'Initiateur et du Validateur. Il va ainsi créer et approuver les deux premiers vrais comptes de l'entreprise : l'Admin A et l'Admin B.
3. **Fermeture de la porte technique** : Dès que l'Admin A et l'Admin B sont créés, le Superuser ne doit plus être utilisé au quotidien. Le fonctionnement normal de la banque prend le relais : désormais, l'Admin A devra demander la création d'un compte, et l'Admin B devra l'approuver.

### Comment faire la première prise en main de la gestion de l'organigramme ?
L'organigramme est le cœur de Sentinel. C'est lui qui définit le périmètre de sécurité de chaque employé ("Qui a le droit de voir quelles recommandations").

Lors du tout premier déploiement de l'application, **l'organigramme de la banque est totalement vide**. Le système connaît les différents niveaux hiérarchiques (Direction, Service, Agence...), mais aucun département physique n'existe encore.

La toute première mission des nouveaux administrateurs (Admin A et Admin B) est donc de dessiner cette arborescence dans le système :
1. Rendez-vous dans le menu d'administration de l'Organigramme.
2. **Créer les racines du système** : Créez des départements totalement indépendants tout en haut de l'arbre, comme la "Direction Générale", la "Direction de l'Audit Interne", et le "Support Informatique" (DSI).
3. **Déployer les branches** : Sous la racine "Direction Générale", créez vos différentes directions métier (ex: Direction des Risques, Direction des Opérations, etc.), puis les services et les agences qui y sont rattachés.

Une fois que ce squelette organisationnel est en place, l'équipe support pourra enfin commencer à créer les comptes de vos employés en les rangeant proprement dans leurs départements respectifs !
