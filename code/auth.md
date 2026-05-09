# Authentification et Habilitations dans Sentinel

Ce document détaille le fonctionnement du système d'authentification et de gestion des habilitations de Sentinel, conçu pour répondre aux exigences de conformité bancaire (COBAC) et à la séparation des tâches (ADR-10).

## 1. Modèle Utilisateur personnalisé

Sentinel utilise un modèle utilisateur étendu (`apps.users.models.User`) basé sur `AbstractUser` de Django avec les spécificités suivantes :

- **Identifiant UUID** : Clé primaire unique de type UUID pour une sécurité accrue.
- **Rôle Métier** : Un champ `role` (TextChoices) qui définit les permissions applicatives.
- **Département** : Rattachement à l'organigramme BICEC pour définir le périmètre de visibilité des données (RBAC).
- **Statut "Coquille Vide"** : Un utilisateur sans rôle défini est considéré comme un compte en attente d'activation.

### Les Rôles (RBAC)
| Code | Libellé | Description |
| :--- | :--- | :--- |
| `AUDIT` | Audit Interne | Auditeurs gérant les missions et recommandations. |
| `DM` | Directeur Métier | Responsable de département (auditée). |
| `ETP` | Employé Traitant | Point focal opérationnel pour la mise en œuvre des actions. |
| `DG` | Direction Générale | Accès en lecture seule sur les reportings consolidés. |
| `EXT` | Auditeur Externe | Accès temporaire limité à une mission spécifique (COBAC/BEAC). |
| `RSSI` | Support IT / RSSI | Gestion technique uniquement (accès Django Admin). |

## 2. Le concept de "Coquille Vide" (Story 1.1)

Pour garantir la **Séparation des Tâches (SoD)**, la création d'un compte suit un flux strict :

1.  **Création (IT)** : Le support IT crée le compte utilisateur dans le système. Ce compte n'a initialement **aucun rôle** (`role=""`).
2.  **Connexion** : L'utilisateur peut se connecter, mais il est immédiatement redirigé vers une page d'attente (`/auth/pending/`).
3.  **Habilitation (Audit)** : Le Directeur de l'Audit Interne (ou son délégué `is_audit_admin`) attribue un rôle métier et un périmètre au compte via l'interface d'administration.
4.  **Activation** : Une fois le rôle attribué, l'utilisateur accède à son tableau de bord lors de sa prochaine connexion.

## 3. Flux d'authentification

### Connexion (`SentinelLoginView`)
La vue de connexion personnalisée gère la redirection post-authentification selon la logique suivante :
- Si `user.role` est vide $\rightarrow$ Redirection vers `/auth/pending/`.
- Sinon $\rightarrow$ Redirection vers le tableau de bord métier (ou l'accueil par défaut).
*(Note : Le Support IT / RSSI n'est plus forcé d'aller sur le Django Admin. Il accède à Sentinel et dispose d'un bouton dédié dans la barre de navigation pour ouvrir le panneau d'administration technique).*

### Protection contre la force brute
Sentinel utilise **Django-Axes** :
- Limite de **5 tentatives** infructueuses.
- Verrouillage basé sur le couple `username` + `IP`.
- Période de refroidissement (Cooloff) de **1 heure**.

## 4. Sécurité des Sessions

### Délai d'inactivité (`IdleTimeoutMiddleware`)
Conformément à la norme **NFR-SEC-02**, toute session inactive pendant plus de **30 minutes** est automatiquement fermée.
- Le middleware `IdleTimeoutMiddleware` surveille la dernière activité.
- Si le délai est dépassé, l'utilisateur est déconnecté et redirigé vers la page de login avec un message d'information.

### Contrôle global des rôles (`RoleRequiredMiddleware`)
Ce middleware agit comme un garde-fou permanent :
- Il intercepte chaque requête.
- Si un utilisateur authentifié tente d'accéder à une page métier alors qu'il est encore une "coquille vide", il est renvoyé vers `/auth/pending/`.
- Les routes publiques (`login`, `logout`, `pending`) et les fichiers statiques sont exclus de ce contrôle pour éviter les boucles de redirection.

## 5. Gouvernance et Administration

L'administration des habilitations est décentralisée :
- **Django Admin** : Utilisé par l'IT pour la gestion technique des comptes.
- **Interface Habilitations Sentinel** : Utilisée par l'Audit pour la gestion métier (attributions des rôles et périmètres).

Seuls les utilisateurs ayant le flag `is_audit_admin = True` peuvent gérer les habilitations métier.
