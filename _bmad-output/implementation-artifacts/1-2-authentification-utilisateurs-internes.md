# Story 1.2: Authentification des Utilisateurs Internes

Status: done

## Story

As a **Utilisateur Interne (Audit, DM, ETP, DG)**,
I want **m'authentifier via des identifiants locaux et gérer ma session**,
so that **je puisse accéder au système de manière sécurisée**.

## Acceptance Criteria

1. **Given** qu'un utilisateur possède un compte actif, **when** il saisit ses identifiants valides, **then** il est connecté et redirigé vers la page d'accueil (`/` ou la page initialement demandée via le paramètre `?next=`) (FR1).
2. **Given** un utilisateur connecté inactif, **when** 30 minutes s'écoulent sans requête, **then** sa session est automatiquement révoquée (Timeout inactivité réel) (NFR-SEC-02).
3. **Given** un utilisateur non authentifié essayant d'accéder à la page d'accueil `/`, **when** la requête est traitée, **then** il est redirigé vers `/auth/login/` en statut 302.
4. **Given** un utilisateur authentifié, **when** il clique sur "Déconnexion", **then** sa session est révoquée de manière sécurisée (CSRF protégé) et il est redirigé.
5. **Given** une attaque de mots de passe, **when** il y a plus de 5 tentatives échouées, **then** le compte/l'IP est bloqué (via `django-axes`).

## Tasks / Subtasks

- [x] **Task 1: Création des Vues et URLs d'Authentification (HackSoft Pattern)**
  - [x] 1.1: Créer le fichier `code/apps/users/urls.py` en y associant `LoginView` et `LogoutView` de `django.contrib.auth.views`. Penser au `namespace="auth"`.
  - [x] 1.2: Inclure `apps.users.urls` dans `code/config/urls.py` sous le path `auth/`.
  - [x] 1.3: Protéger la route `home` (`/`) via le décorateur `login_required`.
  - [x] 1.4: Vérifier dans `apps/users/models.py` la présence du champ `role` (Audit, DM, ETP, DG) et s'assurer qu'il est exposé dans le `UserAdmin` de Django. On pourra afficher le rôle dans la Navbar (`{{ user.get_role_display }}`) pour prouver que la donnée circule.
- [x] **Task 2: Interface Utilisateur (Templates avec Tailwind CSS)**
  - [x] 2.1: Créer le template `code/templates/auth/login.html` en étendant de `base.html` ou d'un layout vide de connexion. N'oubliez pas d'inclure le champ caché `next` pour gérer la redirection après login.
  - [x] 2.2: Styliser le formulaire avec le thème Sentinel (Jaune et Bleu BICEC), utiliser `django-widget-tweaks` pour injecter les classes Tailwind. Utiliser les messages Django (`django.contrib.messages`) intégrés aux templates pour confirmer la déconnexion ou afficher les erreurs de login (Feedback visuel).
  - [x] 2.3: Implémenter le lien de déconnexion dans la Navbar de `base.html` (via formulaire POST HTMX ex: `hx-post="/auth/logout/"`).
- [x] **Task 3: Sécurisation des Sessions (Idle Timeout & Brute Force)**
  - [x] 3.1: Créer `code/apps/users/middleware.py` contenant `IdleTimeoutMiddleware` (logique de déconnexion forcée via tracking `last_activity` dans `request.session`).
  - [x] 3.2: Ajouter `"apps.users.middleware.IdleTimeoutMiddleware"` aux `MIDDLEWARE` de `base.py` (vérifiez bien l'ordre, après CSRF et AuthenticationMiddleware).
  - [x] 3.3: Mettre à jour `tests/test_smoke.py` : adapter le test `test_home_page_returns_200` en `test_home_page_redirects_to_login_for_anonymous` pour valider le 302 vers `/auth/login/?next=/`.

- [x] **Review Follow-ups (AI)**
  - [x] [AI-Review][High] Écrire les tests automatisés manquants pour `IdleTimeoutMiddleware` (AC2). [tests/test_middleware.py] — 6 tests ajoutés (expiry, renewal, within-limit, public exclusion, anonymous, message)
  - [x] [AI-Review][High] Écrire les tests automatisés manquants pour le blocage force brute `django-axes` (AC5). [apps/users/tests/test_axes_brute_force.py] — 5 tests ajoutés (lockout, pre-limit, reset-on-success)
  - [x] [AI-Review][High] Remplacer les inputs HTML manuels par `django-widget-tweaks` dans le template de login. [templates/auth/login.html] — `{% render_field %}` appliqué aux champs username et password
  - [x] [AI-Review][Medium] Créer un template personnalisé `axes/lockout.html` pour l'erreur 403 de blocage avec le design system Sentinel. [templates/axes/lockout.html] — créé avec Material Symbols + design Sentinel

## Developer Context Section (DEV AGENT GUARDRAILS)

> [!IMPORTANT]
> Vous exécutez la story 1.2 qui est primordiale pour l'architecture sécuritaire du projet de la Banque BICEC. Lisez scrupuleusement les contraintes.

### Technical Requirements

> [!TIP]
> **Check-list RBAC-Ready :** L'agent doit s'assurer que le modèle User personnalisé possède bien les constantes de rôles : `ROLE_CHOICES = [('AUDIT', 'Audit'), ('DM', 'Directeur Métier'), ('ETP', 'Employé Traitant'), ('DG', 'Direction Générale'), ('EXT', 'Auditeur Externe'), ('RSSI', 'RSSI / Support IT')]`.
> **Check-list Inactivité :** Le `IdleTimeoutMiddleware` ne doit pas déconnecter l'utilisateur s'il est sur la page de login, ni impacter les routes publiques, sinon on crée une boucle infinie de redirection.

- **Zéro JWT, zéro API, zéro React** : Sentinel fonctionne en mode pur SSR avec les sessions Django stateful. 
- La vue de login et logout doit capitaliser sur les classes natives de Django `django.contrib.auth.views.LoginView` et `LogoutView`.
- **Déconnexion sécurisée** : Les requêtes de déconnexion DOIVENT se faire en `POST` pour prévenir les attaques CSRF, conformément aux règles Django 5+. Vous pouvez utiliser HTMX pour la requête POST du bouton de déconnection silencieusement : `hx-post="{% url 'auth:logout' %}"`.

### Architecture Compliance
- Ne **JAMAIS** exposer les mots de passe.
- **HackSoft Structure** : Le code de routing doit vivre dans `apps/users/urls.py`, pas dans `config/urls.py`. `config/urls.py` doit uniquement utiliser `include`.

### Library / Framework Requirements
- Tailwind CSS doit être compilé manuellement lors de vos tests, ou vous devez vérifier le code.
- `django-axes` est déjà configuré dans le projet (`base.py`). Assurez-vous simplement que le gabarit supporte les erreurs de formulaire si un compte est verrouillé (via un template global d'erreur ou sur la vue login).
- Utilisez `django-widget-tweaks` dans le gabarit (`{% load widget_tweaks %}`) au lieu de boucler manuellement les champs.

### Testing Requirements
- Les smoke tests actuels vont échouer car `/` va désormais exiger une authentification !
- Vous **DEVEZ IMPÉRATIVEMENT** modifier `d:\bicec--Sentinel\code\tests\test_smoke.py` pour valider que la page d'accueil dresse un 302 vers la page de reconnexion au lieu du 200 par défaut. Pensez également à y valider le chargement sans erreur de `/auth/login/` en statut 200.
- N'hésitez pas à lancer la commande `docker compose exec web python manage.py test` pour vous assurer du statut O.K.

### Previous Story Intelligence
- **Leçon apprise du précédent agent:** Dans la Story 1.1, le fichier `middleware.py` avait été référencé dans les `settings` mais effacé du dépôt Git de l'hôte, créant un plantage cuisant (ModuleNotFoundError) au rebuild du container. **Assurez-vous de bien créer les fichiers métier localement ET qu'ils transpirent dans les commits.** Prenez votre temps pour exécuter et vérifier (via le logs ou pytest) avant de conclure la story.

### Conclusion List
- **Status actuel:** `done`
- **Tous les tests passent:** 69/69 OK (58 originaux + 6 IdleTimeout + 5 Axes)

## Senior Developer Review (AI)

**Date:** 2026-05-02
**Outcome:** Approve (after 1 fix)
**Total Issues:** 1 High, 0 Medium, 0 Low → All fixed

### Audit Summary

| Composant | Fichier | Verdict |
|---|---|---|
| URLs + namespace `auth` | `apps/users/urls.py` | ✅ Conforme HackSoft |
| Include dans config | `config/urls.py` | ✅ `include()` uniquement |
| Route home protégée | `config/urls.py` L14 | ✅ `login_required()` |
| Modèle User + 6 rôles | `apps/users/models.py` | ✅ `TextChoices`, UUID pk |
| UserAdmin + role exposé | `apps/users/admin.py` | ✅ `role` en read-only pour non-superuser |
| Template login (widget_tweaks) | `templates/auth/login.html` | ✅ `{% render_field %}` + Tailwind |
| Template lockout (axes) | `templates/axes/lockout.html` | ✅ Design Sentinel + Material Symbols |
| Déconnexion POST HTMX | `templates/partials/topbar.html` L42 | ✅ `hx-post` sécurisé |
| IdleTimeoutMiddleware | `apps/users/middleware.py` | ✅ `_last_activity`, paths exacts |
| Middleware enregistré | `config/settings/base.py` L84 | ✅ Après AuthenticationMiddleware |
| Smoke tests (8) | `tests/test_smoke.py` | ✅ 302 anonymous, 200 login, logout POST |
| Tests IdleTimeout (6) | `apps/users/tests/test_middleware.py` | ✅ AC2 couvert |
| Tests Axes brute force (5) | `apps/users/tests/test_axes_brute_force.py` | ✅ AC5 couvert |
| Tests unitaires (50+) | `apps/users/tests/` | ✅ Models, services, views, middleware, habilitation |

### Action Items
- [x] H1: `get_success_url()` ne redirigait pas le RSSI vers `/admin/` — corrigé dans `SentinelLoginView`.

### Test Results
```
Ran 69 tests in ~95s — OK
```

### Change Log
- 2026-05-02: Code review — 1 issue (H1: redirect RSSI) corrigée. 58/58 tests OK. Status → done.
- 2026-05-09: Review follow-ups fermés — 4 items (IdleTimeout tests, Axes tests, widget_tweaks, lockout template). 69/69 tests OK. Status → done.

