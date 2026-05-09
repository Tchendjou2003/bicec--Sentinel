// Sentinel — helpers Alpine.js
document.addEventListener('alpine:init', () => {
  // Store global pour la sidebar
  Alpine.store('sentinel', {
    sidebarOpen: window.innerWidth >= 1024,
    toggleSidebar() { this.sidebarOpen = !this.sidebarOpen; },
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
      if (data.notify) Alpine.store('sentinel').notify(data.notify.msg, data.notify.type || 'info');
    } catch(e) {}
  }
});
