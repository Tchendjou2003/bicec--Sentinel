# 🌿 Guide Git & GitHub — Projet Sentinel BICEC

## Philosophie : Ne jamais pousser sur `main` directement

> **Règle cardinale :** La branche `main` est **sacrée**. Elle représente toujours le code qui tourne en production (ou qui est prêt pour). On ne la touche jamais directement.

---

## 1. Structure des Branches

```
main          ← Production. Protégée. Jamais de push direct.
│
└── develop   ← Intégration. Tout le travail se rejoint ici.
    │
    ├── story/1.2-authentication      ← Une story = une branche
    ├── story/1.3-external-auditor
    ├── fix/login-session-bug
    └── chore/update-dependencies
```

### Conventions de nommage

| Type de travail | Préfixe | Exemple |
|---|---|---|
| Nouvelle Story (Epic) | `story/` | `story/2.1-creation-recommandation` |
| Correction de bug | `fix/` | `fix/session-timeout-bug` |
| Refactoring/amélioration | `refactor/` | `refactor/audit-model` |
| Tâche technique (CI, deps) | `chore/` | `chore/update-tailwind` |

---

## 2. Votre Flux de Travail Quotidien (Pas à pas)

### Début d'une nouvelle Story

```bash
# 1. Toujours repartir de develop à jour
git checkout develop
git pull origin develop

# 2. Créer votre branche de travail
git checkout -b story/1.2-authentication

# --- Coder, coder, coder... ---

# 3. Sauvegarder votre avancement régulièrement
git add .
git commit -m "feat(auth): add login form with HTMX validation"

# 4. Envoyer votre branche sur GitHub (PAS dans main !)
git push origin story/1.2-authentication
```

### Terminer une Story : Ouvrir une Pull Request (PR)

1. Allez sur GitHub → votre repository
2. Cliquez sur **"Compare & pull request"**
3. **Base :** `develop` ← **Compare :** `story/1.2-authentication`
4. GitHub va **automatiquement déclencher** :
   - ✅ Le pipeline **CI** (tests Django + Ruff lint)
   - 🔐 L'analyse **CodeQL** (failles de sécurité)
   - 🤖 La revue **Qodo AI** (commentaires automatiques sur le code)
5. Relisez les commentaires, corrigez si nécessaire
6. Mergez dans `develop` ✅

---

## 3. Les 3 Workflows GitHub Actions Créés

### `ci.yml` — Tests & Lint
- **Quand :** Sur toute PR vers `main` ou `develop`
- **Ce qu'il fait :**
  - Lance une vraie base PostgreSQL 16 dans le cloud CI
  - Vérifie la qualité du code avec **Ruff** (équivalent moderne de flake8)
  - Exécute tous vos tests Django (`python manage.py test`)
  - Vérifie qu'il n'y a pas de migration manquante

### `codeql.yml` — Analyse Sécurité
- **Quand :** Sur toute PR + Push sur `main`/`develop` + **Chaque lundi à 4h du matin**
- **Ce qu'il fait :**
  - Analyse 100% de votre code Python à la recherche de failles connues (injections SQL, XSS, expositions de données)
  - Utilise le mode `security-extended` (niveau bancaire/réglementaire)
  - Rapport disponible dans l'onglet **Security > Code scanning** de GitHub

### `qodo-review.yml` — AI Code Review
- **Quand :** Sur toute PR ouverte ou mise à jour
- **Ce qu'il fait :**
  - Un bot 🤖 analyse votre PR automatiquement
  - Poste des commentaires directement sur les lignes de code problématiques
  - Suggère des améliorations (logique, sécurité, lisibilité)

---

## 4. Protéger les Branches (Configuration GitHub — À faire une fois)

Allez dans : **GitHub → Settings → Branches → Branch protection rules**

### Règle pour `main`
| Option | Valeur |
|---|---|
| Require pull request before merging | ✅ Activer |
| Required approvals | 1 |
| Require status checks to pass | ✅ Activer |
| Status checks requis | `Tests Django + Lint` + `CodeQL` |
| Restrict who can push | Cochez "Restrict pushes" |

### Règle pour `develop`
| Option | Valeur |
|---|---|
| Require pull request before merging | ✅ Activer |
| Required approvals | 0 (vous travaillez seul) |
| Require status checks to pass | ✅ Activer |
| Status checks requis | `Tests Django + Lint` |

---

## 5. Configurer le Secret Qodo (Obligatoire)

Pour activer la revue Qodo AI, configurez le secret dans GitHub :

1. Créez un compte sur [qodo.ai](https://www.qodo.ai) et récupérez votre clé API
2. GitHub → **Settings → Secrets and variables → Actions**
3. Cliquez **"New repository secret"**
4. Nom : `QODO_API_KEY` | Valeur : *votre clé API Qodo*

> CodeQL ne nécessite aucune configuration supplémentaire : il fonctionne nativement sur les repositories GitHub publics et privés (plan GitHub Free inclus pour les dépôts privés avec CodeQL activé).

---

## 6. Messages de Commit — Convention

Utilisez la convention **Conventional Commits** pour que l'historique soit lisible :

```
<type>(<scope>): <description courte>
```

| Type | Quand l'utiliser |
|---|---|
| `feat` | Nouvelle fonctionnalité (nouvelle story) |
| `fix` | Correction d'un bug |
| `refactor` | Amélioration du code sans changer le comportement |
| `test` | Ajout ou correction de tests |
| `chore` | Mise à jour de dépendances, configuration |
| `docs` | Mise à jour de documentation |

**Exemples :**
```bash
git commit -m "feat(auth): add login page with 30min session timeout (NFR-SEC-02)"
git commit -m "fix(workflow): fix FSM transition for OVERDUE state"
git commit -m "test(audit): add smoke test for HMAC seal generation"
git commit -m "chore(deps): upgrade Django to 5.2.13"
```
