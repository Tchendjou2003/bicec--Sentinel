// Sentinel — helpers Alpine.js
document.addEventListener('alpine:init', () => {
  // Store global pour la sidebar
  Alpine.store('sentinel', {
    // Préférence persistée (desktop on-premise) ; défaut : ouverte si écran large.
    sidebarOpen: (() => {
      try {
        const saved = localStorage.getItem('sentinel.sidebar');
        if (saved !== null) return saved === 'open';
      } catch (e) { }
      return window.innerWidth >= 1024;
    })(),
    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen;
      try { localStorage.setItem('sentinel.sidebar', this.sidebarOpen ? 'open' : 'closed'); } catch (e) { }
    },
    notifications: [],
    notify(msg, type = 'info') {
      const id = Date.now();
      this.notifications.push({ id, msg, type });
      setTimeout(() => { this.notifications = this.notifications.filter(n => n.id !== id); }, 4000);
    }
  });
});

// HTMX — afficher un toast après un htmx:afterRequest réussi qui retourne un header HX-Trigger:notify
document.body.addEventListener('htmx:afterRequest', (evt) => {
  const trigger = evt.detail.xhr.getResponseHeader('HX-Trigger');
  if (trigger) {
    try {
      const data = JSON.parse(trigger);
      if (data.notify && data.notify.msg && typeof Alpine !== 'undefined' && Alpine.store('sentinel')) {
        Alpine.store('sentinel').notify(data.notify.msg, data.notify.type || 'info');
      }
      // Provisioning : déclencher refresh-list sur la table
      if (data.provisioningCreated || data.provisioningUpdated) {
        document.body.dispatchEvent(new CustomEvent('provisioning-created'));
        document.body.dispatchEvent(new CustomEvent('refresh-list'));
      }
    } catch (e) { }
  }
});

// HTMX — erreurs globales (Lot 1.3) : sans ces handlers, un 500 ou une panne
// réseau sur une action HTMX est totalement silencieux pour l'utilisateur.
document.body.addEventListener('htmx:responseError', (evt) => {
  if (typeof Alpine === 'undefined' || !Alpine.store('sentinel')) return;
  const xhr = evt.detail.xhr;
  // Ne pas doubler un toast déjà porté par la réponse (HX-Trigger:notify).
  // Les erreurs de validation re-rendent le formulaire en HTTP 200 et ne
  // passent pas par cet événement.
  if (xhr.getResponseHeader('HX-Trigger')) return;
  if (xhr.status === 403) {
    Alpine.store('sentinel').notify('Action refusée ou session expirée — rechargez la page.', 'error');
  } else if (xhr.status >= 500) {
    Alpine.store('sentinel').notify("Erreur serveur — l'action n'a pas abouti. Réessayez ou contactez le support IT.", 'error');
  }
});

document.body.addEventListener('htmx:sendError', () => {
  if (typeof Alpine !== 'undefined' && Alpine.store('sentinel')) {
    Alpine.store('sentinel').notify('Connexion au serveur impossible — vérifiez le réseau.', 'error');
  }
});

// =============================================================================
// TomSelect — initialisation des sélecteurs organisationnels (Story 6.2.0)
// Vendorisé local : static/vendor/tom-select/
// =============================================================================

/**
 * Initialise TomSelect sur un seul élément <select> porteur de .js-tomselect.
 * Idempotent : ne fait rien si l'élément est déjà transformé.
 *
 * @param {HTMLSelectElement} el
 */
function initOneTomSelect(el) {
  if (typeof TomSelect === 'undefined') {
    // Le script vendor n'est pas chargé — signaler clairement en console.
    if (!window.__tomSelectWarned) {
      console.warn('[Sentinel] TomSelect non chargé : vérifier static/vendor/tom-select/tom-select.complete.min.js');
      window.__tomSelectWarned = true;
    }
    return;
  }
  // Garde anti-double-init (TomSelect expose .tomselect sur l'élément).
  if (el.tomselect || el.classList.contains('tomselected')) return;

  try {
    new TomSelect(el, {
      searchField: ['text', 'value'],   // recherche sur libellé ET code
      placeholder: el.dataset.placeholder || 'Rechercher…',
      allowEmptyOption: true,
      create: false,
      // Le dropdown est rattaché au <body> pour ne PAS être clippé par les
      // conteneurs overflow-hidden / overflow-y-auto des slide-overs.
      dropdownParent: 'body',
      render: {
        option: function (data, escape) {
          return '<div class="py-2 px-3 text-sm">' + escape(data.text) + '</div>';
        },
        item: function (data, escape) {
          return '<div>' + escape(data.text) + '</div>';
        },
        no_results: function () {
          return '<div class="py-2 px-3 text-sm text-gray-400">Aucun résultat</div>';
        },
      },
    });
  } catch (err) {
    console.error('[Sentinel] Échec init TomSelect sur', el, err);
  }
}

/**
 * Scanne un conteneur et initialise tous les .js-tomselect trouvés.
 * @param {ParentNode} root
 */
function initTomSelect(root = document) {
  if (!root || typeof root.querySelectorAll !== 'function') return;
  root.querySelectorAll('select.js-tomselect').forEach(initOneTomSelect);
}

// ── Init au chargement initial ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => initTomSelect(document));

// =============================================================================
// TomSelect — détection robuste des injections dynamiques (MutationObserver)
//
// HTMX + Alpine x-teleport rendent le timing des événements htmx:afterSwap
// peu fiable. Un MutationObserver garantit que TOUT <select.js-tomselect>
// ajouté au DOM (par HTMX, par téléportation Alpine, ou autrement) est
// initialisé immédiatement, sans aucune hypothèse de timing.
// =============================================================================
(function observeTomSelect() {
  const scanNode = (node) => {
    if (node.nodeType !== 1) return; // éléments uniquement
    // L'élément lui-même est-il un select ciblé ?
    if (node.matches && node.matches('select.js-tomselect')) {
      initOneTomSelect(node);
    }
    // Ou contient-il des selects ciblés ?
    if (node.querySelectorAll) {
      node.querySelectorAll('select.js-tomselect').forEach(initOneTomSelect);
    }
  };

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      m.addedNodes.forEach(scanNode);
    }
  });

  const start = () => observer.observe(document.body, { childList: true, subtree: true });
  if (document.body) {
    start();
  } else {
    document.addEventListener('DOMContentLoaded', start);
  }
})();

// Filet de sécurité supplémentaire : après chaque settle HTMX, rescan complet.
document.body.addEventListener('htmx:afterSettle', () => initTomSelect(document));
