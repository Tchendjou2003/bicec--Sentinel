# Design Thinking Session: Amélioration UI/UX Import Excel

**Date:** 2026-06-14
**Facilitator:** Dave Lahe
**Design Challenge:** Refondre l'expérience utilisateur de la page d'import massif de recommandations Excel pour la rendre plus fluide, intuitive et moins sujette aux erreurs de manipulation.

---

## 🎯 Design Challenge

**Le constat actuel (Mauvaises pratiques UI/UX identifiées) :**

1. **Parcours utilisateur en "Zigzag" (Flow disruptif) :**
   - L'utilisateur doit télécharger le modèle (gauche), uploader (gauche), cliquer sur Analyser (gauche), lire les résultats (droite), et enfin confirmer (droite). Ce balayage visuel gauche-droite constant crée une charge cognitive inutile.
2. **Stepper illusoire :**
   - Le stepper (1, 2, 3, 4) laisse penser à un parcours étape par étape (wizard), mais toute l'interface est présentée sur une seule page statique. L'utilisateur voit tout en même temps, ce qui dilue le focus.
3. **Gestion des erreurs (Friction) :**
   - Le bouton "Fichier corrigé" utilise du JavaScript brut pour vider le panneau de droite. Le lien entre le retour d'erreur (droite) et la nécessité de re-déposer un fichier (gauche) n'est pas optimisé.
4. **Hiérarchie de l'information :**
   - Les "Colonnes obligatoires" sont reléguées en bas à gauche, loin du bouton de téléchargement du modèle, alors que c'est une information cruciale *avant* de remplir le fichier.

**Challenge Statement proposé :**
*Comment pourrions-nous transformer l'import Excel en un véritable parcours guidé (wizard step-by-step), où l'utilisateur est focalisé sur une seule action à la fois, tout en rendant la résolution d'erreurs (validation) transparente et encourageante ?*
