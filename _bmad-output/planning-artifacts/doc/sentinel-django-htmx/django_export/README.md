# SENTINEL — Templates Django + HTMX + Tailwind + Alpine.js

Export du frontend SENTINEL (BICEC) en **templates HTML purs** prêts à intégrer dans un projet Django utilisant `django-fsm-2`, HTMX, Tailwind CLI et Alpine.js.

## Contenu

```
django_export/
├── sentinel_templates/             # À copier dans <ton_app>/templates/sentinel/
│   ├── base/
│   │   ├── base.html               # Layout racine (head, scripts CDN HTMX/Alpine)
│   │   └── app_shell.html          # Layout avec sidebar + topbar (extends base.html)
│   ├── partials/
│   │   ├── topbar.html
│   │   ├── footer.html
│   │   └── sidebar_*.html          # Une sidebar par profil
│   ├── components/                 # Composants réutilisables ({% include %})
│   │   ├── kpi_card.html           # Usage: {% include "sentinel/components/kpi_card.html" with title="..." value="..." %}
│   │   └── status_badge.html       # Usage: {% include "sentinel/components/status_badge.html" with status="ACTIVE" %}
│   └── profiles/
│       ├── rssi/                   # Dashboard, users, organigramme, monitoring
│       ├── dg/                     # Dashboard, directions, rapports
│       ├── audit/                  # Dashboard, recommandations, import, validation, roles
│       ├── etp/                    # Dashboard, soumission, historique
│       ├── dm/                     # Dashboard, validation
│       └── audit_ext/              # Dashboard, consultation, export ZIP
│
├── sentinel_static/                # À copier dans <ton_app>/static/sentinel/
│   ├── src/
│   │   └── input.css               # Source Tailwind avec design tokens BICEC (HSL)
│   ├── css/
│   │   └── output.css              # Généré par `tailwindcss -i src/input.css -o css/output.css`
│   └── js/
│       └── sentinel.js             # Helpers Alpine (sidebar collapse, dropdowns)
│
├── tailwind.config.js              # Config Tailwind (tokens BICEC, fonts, animations)
└── README.md
```

## Installation rapide

### 1. Copier les fichiers
```bash
cp -r sentinel_templates/* <ton_app>/templates/sentinel/
cp -r sentinel_static/*    <ton_app>/static/sentinel/
cp tailwind.config.js      .                    # Racine projet (ou adapter chemin)
```

### 2. Build Tailwind
```bash
npm install -D tailwindcss @tailwindcss/forms tailwindcss-animate
npx tailwindcss -i ./<ton_app>/static/sentinel/src/input.css \
                -o ./<ton_app>/static/sentinel/css/output.css --watch
```

### 3. Charger dans `base.html`
Déjà fait : `base.html` charge HTMX 1.9, Alpine.js 3.x, et `output.css` via `{% static %}`.

### 4. Brancher tes vues Django

Chaque template attend des variables de contexte (mockées en dur pour l'instant via des `{% with ... %}`). Exemple pour `profiles/rssi/dashboard.html` :

```python
# views.py
from django.shortcuts import render

def rssi_dashboard(request):
    context = {
        "kpi_users_active": 247,
        "kpi_users_inactive": 18,
        "alerts": Alert.objects.order_by("-created_at")[:5],
        # ...
    }
    return render(request, "sentinel/profiles/rssi/dashboard.html", context)
```

## Workflow recommandations (django-fsm-2)

États du modèle `Recommandation` (suggestion) :
- `DRAFT` → `ASSIGNED` (Auditeur Interne assigne à un ETP)
- `ASSIGNED` → `IN_PROGRESS` (ETP commence le travail)
- `IN_PROGRESS` → `PENDING_VALIDATION` (ETP soumet preuves)
- `PENDING_VALIDATION` → `VALIDATED` (DM valide) | `IN_PROGRESS` (DM rejette)
- `VALIDATED` → `CLOSED` (Auditeur Interne clôture)

Le composant `status_badge.html` accepte directement ces statuts.

## HTMX — Endpoints suggérés

| Action | Endpoint | Trigger |
|---|---|---|
| Créer compte (RSSI) | `POST /rssi/users/create/` | Formulaire modale |
| Soumettre preuve (ETP) | `POST /etp/preuves/` | `hx-post` + `hx-encoding="multipart/form-data"` |
| Valider preuve (DM) | `POST /dm/validation/<id>/` | Boutons valider/rejeter |
| Filtrer table | `GET /audit/recommandations/?q=...` | `hx-get` + `hx-target="#recos-tbody"` |
| Export ZIP (Audit Ext) | `POST /audit-ext/export/` | `hx-post` avec progression |

## Alpine.js — Patterns utilisés

- **Sidebar collapse** : `x-data="{ open: true }"` sur `<aside>`, toggle via bouton burger
- **Modales** : `x-data="{ open: false }"` + `x-show` + `x-transition`
- **Dropdowns** : `@click.outside="open = false"`
- **Tabs / Accordions** : `x-data="{ tab: 'a' }"` + `:class="{ 'active': tab === 'a' }"`

## Charte graphique BICEC

Définie en HSL dans `tailwind.config.js` et `src/input.css` :
- Primary : `#E87722` (orange BICEC)
- Secondary : `#4A2C2A` (terre brûlée)
- Surface : `#F5F7FA`
- Fonts : Manrope (titres), Inter (corps), JetBrains Mono (refs)

---
**Version** : 1.0 — Export depuis Lovable Sentinel v2.1.0
