## Description
<!-- Décris les changements apportés par cette PR -->

## Stories couvertes
<!-- Ex: Story 3.1, 3.2, 3.3 — Epic 3 -->

## Checklist avant soumission

### Git & CI
- [ ] `git fetch origin && git rebase origin/develop` exécuté — aucun conflit
- [ ] `ruff check code/` passe sans erreur en local
- [ ] `python manage.py test --verbosity=2` passe en local
- [ ] `python manage.py migrate --check` passe (pas de migration manquante)

### PR
- [ ] La PR cible `develop` (jamais `main` directement)
- [ ] Au moins 1 reviewer assigné
- [ ] Le titre suit le format Conventional Commits (`feat:`, `fix:`, `refactor:`, etc.)

### Sécurité & Architecture
- [ ] Les nouvelles vues utilisent un sélecteur RBAC (`get_recommendations_for_user` ou dérivé)
- [ ] Les mutations passent par `services.py` (pas de logique métier dans les vues)
- [ ] Toute transition FSM produit une entrée `AuditLog`

## Type de changement
- [ ] ✨ Feature (nouvelle fonctionnalité)
- [ ] 🐛 Fix (correction de bug)
- [ ] ♻️ Refactor
- [ ] 🏗️ Infrastructure / DevOps
- [ ] 🧪 Tests uniquement
- [ ] 📝 Documentation
