i18next
  .use(i18nextHttpBackend)
  .use(i18nextBrowserLanguageDetector)
  .init({
    debug: true,
    fallbackLng: 'es',
    backend: {
      loadPath: '/static/locales/{{lng}}.json'
    },
    load: 'languageOnly'
  }, function(err, t) {
    if (err) {
      console.error('❌ Error cargando traducciones:', err);
      return;
    }
    updateContent();

    // Disparamos un evento personalizado para avisar que i18next ya está listo
    document.dispatchEvent(new Event('i18nInitialized'));
  });

function updateContent() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const options = el.dataset.i18nOptions ? JSON.parse(el.dataset.i18nOptions) : {};
    el.innerHTML = i18next.t(key, options);
  });
}

/*
document.addEventListener('DOMContentLoaded', () => {
  const select = document.getElementById('lang-select');
  if (!select) return;

  // Restaurar idioma guardado al recargar la página
  const savedLang = localStorage.getItem('selectedLang');
  if (savedLang) {
    select.value = savedLang;
    i18next.changeLanguage(savedLang, updateContent);
  }

  select.addEventListener('change', () => {
    const newLang = select.value;
    localStorage.setItem('selectedLang', newLang); // Guardar selección de idioma
    i18next.changeLanguage(newLang, () => {
        updateContent(); // actualiza los elementos con data-i18n del HTML

        // Recargar la página automáticamente cada vez que se cambia el idioma
        location.reload();
    });
  });
});
*/

document.addEventListener('DOMContentLoaded', () => {
  const select = document.getElementById('lang-select');
  if (!select) return;

  // Restaurar selección previa en el <select>
  const savedLang = localStorage.getItem('selectedLang');
  if (savedLang) select.value = savedLang;

  // Aplicar idioma una vez i18next esté listo
  const applySavedLang = () => {
    const langToUse = savedLang || select.value;
    // Usamos callback para compatibilidad; updateContent actualizará el DOM
    i18next.changeLanguage(langToUse, () => {
      updateContent();
    });
  };

  if (i18next.isInitialized) {
    applySavedLang();
  } else {
    document.addEventListener('i18nInitialized', applySavedLang, { once: true });
  }

  // Al cambiar el select guardamos y recargamos la página
  select.addEventListener('change', () => {
    const newLang = select.value;
    localStorage.setItem('selectedLang', newLang);
    // No necesitamos llamar a changeLanguage aquí: recargamos y la init utilizará savedLang
    location.reload();
  });
});