# Security Issues — Sentinel (Stories 1.1 → 3.5)

**Généré le :** 2026-05-23  
**Branche analysée :** `feat/story-3.5-3.6-validation-dm-To-Audit-And-demande-report-echeance`  
**Scope :** Audit complet du diff depuis `main` (Stories 1.1 à 3.5)  
**Statut :** ⏳ Non corrigé — corrections à planifier

---

## Résumé des vulnérabilités

| # | Sévérité | Fichier | Catégorie | Statut |
|---|----------|---------|-----------|--------|
| 1 | 🔴 HIGH | `docker-compose.yml:46` + `gunicorn.conf.py:17` | Exposition directe Gunicorn + IP Spoofing | ⏳ Ouvert |
| 2 | 🔴 HIGH | `apps/workflow/selectors.py:89-138` | RBAC bypass inter-départemental | ⏳ Ouvert |
| 3 | 🔴 HIGH | `nginx/nginx.conf:15` + `:52-98` | TLS inactif en production | ⏳ Ouvert |
| 4 | 🟡 MEDIUM | `apps/workflow/selectors.py:185-229` | Fuite de métadonnées preuves | ⏳ Ouvert |
| 5 | 🟡 MEDIUM | `config/settings/prod.py:25` | `localhost` dans CSRF_TRUSTED_ORIGINS | ⏳ Ouvert |

---

## Vuln 1 — Exposition directe Gunicorn + IP Spoofing

**Sévérité :** 🔴 HIGH  
**Confiance :** 0.95  
**Catégorie :** Infrastructure / Authentication bypass

### Fichiers concernés

- [`code/docker-compose.yml:46`](code/docker-compose.yml#L46)
- [`code/gunicorn.conf.py:17`](code/gunicorn.conf.py#L17)

### Description

Deux configurations combinées créent une vulnérabilité d'infrastructure sérieuse :

**`docker-compose.yml:46`** — le service `web` (Gunicorn) expose le port 8000 directement sur l'hôte :
```yaml
ports:
  - "8000:8000"   # ← Expose Gunicorn directement, bypasse nginx
```

**`gunicorn.conf.py:17`** — Gunicorn fait confiance à TOUTE IP pour l'en-tête `X-Forwarded-For` :
```python
forwarded_allow_ips = "*"  # Confiance au proxy Nginx devant Gunicorn
```

Cette directive ne pose aucun problème quand Gunicorn est **uniquement** accessible via nginx (seul nginx peut injecter `X-Forwarded-For`). Mais puisque le port 8000 est exposé, n'importe qui sur le réseau peut contacter Gunicorn directement et forger cet en-tête.

### Scénario d'exploitation

1. Un attaquant sur le réseau interne BICEC accède directement à `http://sentinel-host:8000/`
2. Il envoie une requête HTTP avec `X-Forwarded-For: 127.0.0.1` (ou l'IP d'un administrateur whitelisté)
3. Django/Axes voit l'IP comme `127.0.0.1` → les logs d'audit enregistrent une IP forgée
4. Les éventuelles restrictions IP futures (whitelist admin) seraient bypassées
5. La traçabilité des accès (audit log) est compromise — les IPs dans `AuditLog` sont non-fiables

### Correction recommandée

**`docker-compose.yml`** — Remplacer `ports:` par `expose:` pour le service `web` :
```yaml
# web service
expose:
  - "8000"     # Accessible uniquement depuis d'autres containers (nginx)
# Supprimer: ports: - "8000:8000"
```

**`gunicorn.conf.py`** — Restreindre `forwarded_allow_ips` à l'IP du container nginx :
```python
# Option 1 : IP fixe du container nginx dans le réseau Docker
forwarded_allow_ips = "nginx"  # DNS Docker interne (si même réseau)

# Option 2 : IP du sous-réseau Docker (172.x.x.x)
forwarded_allow_ips = "172.16.0.0/12"

# Option 3 : Via variable d'environnement
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
```

---

## Vuln 2 — RBAC bypass inter-départemental (selectors.py)

**Sévérité :** 🔴 HIGH  
**Confiance :** 0.90  
**Catégorie :** Authorization bypass / Unauthorized data access

### Fichiers concernés

- [`code/apps/workflow/selectors.py:89-112`](code/apps/workflow/selectors.py#L89) — `get_recommendation_by_id()`
- [`code/apps/workflow/selectors.py:115-138`](code/apps/workflow/selectors.py#L115) — `get_recommendation_detail()`

### Description

Les deux sélecteurs utilisés pour les vues de détail ignorent le filtrage départemental :

**`get_recommendation_by_id(pk, user)`** — Le paramètre `user` est accepté mais **ignoré**. Aucun filtre département :
```python
def get_recommendation_by_id(*, pk, user) -> Recommendation:
    # Le commentaire dit "Le mixin AuditRequiredMixin a déjà vérifié le rôle."
    # Mais AuditRequiredMixin vérifie seulement que l'utilisateur EST un DM/ETP,
    # pas qu'il peut accéder À CETTE recommandation spécifique.
    return get_object_or_404(
        Recommendation.objects.select_related(...),
        pk=pk,  # ← Aucun filtre department ici
    )
```

**`get_recommendation_detail(pk)`** — Pas de paramètre `user` du tout :
```python
def get_recommendation_detail(*, pk) -> Recommendation:
    return get_object_or_404(
        Recommendation.objects.select_related(...)
        .prefetch_related("deliverables"),
        pk=pk,  # ← Aucun filtre RBAC
    )
```

**Contraste** avec `get_recommendations_for_user()` (liste) qui applique correctement le filtrage par département (lignes 41-54). La protection RBAC existe pour la liste mais est absente pour la vue détail.

### Scénario d'exploitation

1. Le DM de la Direction Comptabilité connaît (ou devine par énumération) un UUID de recommandation appartenant à la Direction RH
2. Il accède directement à `/audit/recommandations/<uuid-rh>/` 
3. `WorkflowAccessMixin` vérifie qu'il a le rôle DM ✅ — mais pas qu'il est DM de la bonne direction
4. `get_recommendation_detail(pk=<uuid-rh>)` renvoie la recommandation RH sans contrôle
5. Le DM Comptabilité voit les observations d'audit, dossiers anomaleux, et les preuves soumises par les ETP RH

**Note :** Les UUIDs v4 sont 128 bits aléatoires — l'énumération brute est impraticable. Mais les UUIDs peuvent fuiter via :
- Notifications email (lien cliquable)
- Logs serveur accessibles en interne
- Capture de trafic réseau (si HTTP, cf. Vuln 3)

### Correction recommandée

Modifier `get_recommendation_by_id()` et `get_recommendation_detail()` pour appliquer le même filtre RBAC que `get_recommendations_for_user()` :

```python
def get_recommendation_detail(*, pk, user) -> Recommendation:
    """
    Retourne une recommandation avec contrôle RBAC strict par département.
    """
    from apps.users.models import User

    qs = Recommendation.objects.select_related(
        "created_by", "department", "controlled_department",
        "assigned_dm", "assigned_etp",
    ).prefetch_related("deliverables")

    # RBAC : AUDIT et superusers voient tout
    if not (user.role == User.Role.AUDIT or user.is_superuser):
        if user.role in [User.Role.DM, User.Role.DG]:
            if user.department:
                dept_ids = get_department_and_descendants_ids(user.department)
                qs = qs.filter(department_id__in=dept_ids)
            else:
                from django.http import Http404
                raise Http404
        elif user.role == User.Role.ETP:
            qs = qs.filter(assigned_etp=user)
        else:
            from django.http import Http404
            raise Http404

    return get_object_or_404(qs, pk=pk)
```

Mettre à jour tous les appels dans `views.py` pour passer `user=request.user`.

---

## Vuln 3 — TLS inactif en production (nginx)

**Sévérité :** 🔴 HIGH  
**Confiance :** 0.95  
**Catégorie :** Transport Security / Data exposure

### Fichiers concernés

- [`code/nginx/nginx.conf:15`](code/nginx/nginx.conf#L15) — Redirection HTTP→HTTPS commentée
- [`code/nginx/nginx.conf:52-98`](code/nginx/nginx.conf#L52) — Bloc HTTPS entier commenté

### Description

Le fichier nginx.conf est désigné comme la configuration de production (ADR-02), mais le TLS n'est pas activé. Le `server_name localhost` et les `TODO:` suggèrent que c'est intentionnel pendant le développement. Cependant, ce même fichier est utilisé en production via Docker Compose, créant un risque réel si déployé tel quel.

```nginx
# Bloc 1 : Redirection HTTP -> HTTPS — COMMENTÉE
# return 301 https://$host$request_uri;   ← La redirection n'est pas active

# Bloc 2 : Serveur HTTPS — ENTIÈREMENT COMMENTÉ
# server {
#     listen 443 ssl http2;
#     ...  tout le bloc HTTPS est commenté
# }
```

**Conséquences si déployé en l'état sur le réseau BICEC :**
- Identifiants de connexion transmis en clair (HTTP)
- Tokens CSRF et cookies de session interceptables
- Contenu des recommandations d'audit (données sensibles) exposé en clair
- L'en-tête HSTS configuré dans `prod.py` n'a aucun effet si le HTTPS n'est pas actif

### Correction recommandée

**Étape 1 — Obtenir les certificats TLS** auprès de l'IT BICEC (CA interne ou Let's Encrypt si accès internet).

**Étape 2 — Activer dans `nginx.conf`** :
```nginx
server {
    listen 80;
    server_name sentinel.intra.bicec.local;
    return 301 https://$host$request_uri;  # ← Décommenter cette ligne
}

server {
    listen 443 ssl http2;
    server_name sentinel.intra.bicec.local;
    
    ssl_certificate /etc/nginx/ssl/sentinel.crt;
    ssl_certificate_key /etc/nginx/ssl/sentinel.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    # ... (décommenter le bloc complet)
}
```

**Étape 3 — Monter le volume certificats dans `docker-compose.yml`** :
```yaml
# nginx service
volumes:
  - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
  - sentinel_static:/app/staticfiles:ro
  - sentinel_certs:/etc/nginx/ssl:ro   # ← Décommenter cette ligne
```

---

## Vuln 4 — Fuite de métadonnées preuves (impact Vuln 2)

**Sévérité :** 🟡 MEDIUM  
**Confiance :** 0.85  
**Catégorie :** Data exposure / RBAC indirect bypass

### Fichiers concernés

- [`code/apps/workflow/selectors.py:185-229`](code/apps/workflow/selectors.py#L185) — `get_evidence_for_recommendation()`

### Description

Cette vulnérabilité est **causée par** la Vuln 2. Le sélecteur `get_evidence_for_recommendation()` applique correctement un filtre RBAC sur les soumissions de preuves (Audit ne voit que les ACCEPTED, les rôles EXT ne voient que les ACCEPTED). Cependant, ce sélecteur reçoit une `recommendation` déjà chargée sans contrôle RBAC — si la Vuln 2 est exploitée, l'attaquant voit aussi les preuves.

**Données exposées via la fuite :**
- Noms des fichiers uploadés par l'ETP (potentiellement nominatifs)
- Commentaires de résolution ETP
- Dates de soumission
- Fichiers EvidenceFile (si servis sans contrôle — voir la vue `EvidenceFileDownloadView`)

### Correction recommandée

Cette vulnérabilité se résout automatiquement en corrigeant la Vuln 2. Aucune modification supplémentaire de `get_evidence_for_recommendation()` n'est nécessaire — son RBAC interne est correct.

Vérifier en plus que `EvidenceFileDownloadView` (vue de téléchargement) applique le même contrôle département que la vue détail. Si elle utilise aussi `get_object_or_404(EvidenceFile, pk=pk)` sans filtre, appliquer le même patch.

---

## Vuln 5 — `https://localhost` dans CSRF_TRUSTED_ORIGINS (prod)

**Sévérité :** 🟡 MEDIUM  
**Confiance :** 0.80  
**Catégorie :** CSRF / Authorization

### Fichiers concernés

- [`code/config/settings/prod.py:23-26`](code/config/settings/prod.py#L23)

### Description

```python
CSRF_TRUSTED_ORIGINS = [
    "https://sentinel.intra.bicec.local",
    "https://localhost",   # ← Problématique en production
]
```

En production, `https://localhost` dans `CSRF_TRUSTED_ORIGINS` signifie que Django accepte des requêtes POST avec l'en-tête `Origin: https://localhost` comme légitimes. Dans un environnement d'entreprise où les développeurs ont accès au réseau interne BICEC, une application web malveillante tournant sur `localhost:PORT` d'un poste de travail connecté au réseau pourrait soumettre des requêtes CSRF vers Sentinel sans que le middleware CSRF les bloque.

### Scénario d'exploitation

1. Un développeur malveillant (ou un poste compromis) exécute une application locale sur port quelconque
2. L'application forge une requête POST vers Sentinel avec `Origin: https://localhost`
3. Le middleware CSRF accepte cette origin comme de confiance
4. Les actions (créer/modifier/supprimer des recommandations) sont exécutées sans vérification CSRF

### Correction recommandée

```python
# prod.py — Supprimer https://localhost
CSRF_TRUSTED_ORIGINS = [
    "https://sentinel.intra.bicec.local",
    # "https://localhost"  ← SUPPRIMER en production
]
```

Ajouter `https://localhost` uniquement dans `dev.py` si nécessaire pour les tests locaux.

---

## Plan de correction suggéré

### Priorité 1 — Avant tout déploiement production (Bloquer le merge vers `main`)

| Action | Effort | Risque de régression |
|--------|--------|---------------------|
| Vuln 1 : `expose:` au lieu de `ports:` pour `web` | 5 min | Nul (aucun test Docker) |
| Vuln 5 : Supprimer `https://localhost` de `prod.py` | 1 min | Nul |

### Priorité 2 — Avant activation production (Doit être fait avant accès BICEC)

| Action | Effort | Risque de régression |
|--------|--------|---------------------|
| Vuln 2 : RBAC dans `get_recommendation_detail()` et `get_recommendation_by_id()` | 1-2h | Tests views à vérifier |
| Vuln 3 : Obtenir certificats TLS + activer bloc nginx HTTPS | Dépend IT BICEC | Coordination réseau |

### Priorité 3 — Automatiquement résolu par Priorité 2

| Action |
|--------|
| Vuln 4 : Se résout avec Vuln 2 |

---

## Notes contextuelles

- **Les vulnérabilités 1, 3 sont marquées TODO dans le code** — elles sont connues et documentées comme "à faire avant la production". Ce rapport formalise le risque pour éviter qu'un déploiement prématuré les ignore.
- **La vulnérabilité 2 est non documentée** — c'est un écart silencieux entre la liste (correctement protégée) et le détail (non protégé). À corriger en priorité parmi le code applicatif.
- **L'exploitation de la Vuln 2 est conditionnelle à la connaissance d'un UUID** — difficile par énumération brute mais possible par d'autres vecteurs (email, logs, trafic réseau non chiffré si Vuln 3 active).

---

*Rapport généré par Claude Code (Security Review) — Branche `feat/story-3.5-3.6-validation-dm-To-Audit-And-demande-report-echeance`*
