// Confort d'édition des champs JSON de l'admin : reformate et valide le texte
// sans jamais l'envoyer au serveur. Le back-office reste seul juge du contenu.
(function () {
  "use strict";

  function prettyPrint(value) {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch (error) {
      return null;
    }
  }

  function setStatus(element, text, isError) {
    element.textContent = text;
    element.className = isError
      ? "pretty-json-status pretty-json-error"
      : "pretty-json-status pretty-json-ok";
  }

  function setup(textarea) {
    if (textarea.dataset.prettyJsonReady) return;
    textarea.dataset.prettyJsonReady = "1";

    var formatted = prettyPrint(textarea.value);
    if (formatted !== null) {
      textarea.value = formatted;
    }

    var toolbar = document.createElement("div");
    toolbar.className = "pretty-json-toolbar";

    var button = document.createElement("button");
    button.type = "button";
    button.className = "button pretty-json-format";
    button.textContent = "Formater le JSON";

    var status = document.createElement("span");
    status.className = "pretty-json-status";

    button.addEventListener("click", function () {
      var result = prettyPrint(textarea.value);
      if (result === null) {
        setStatus(status, "JSON invalide", true);
        return;
      }
      textarea.value = result;
      setStatus(status, "JSON formaté", false);
    });

    textarea.addEventListener("input", function () {
      status.textContent = "";
      status.className = "pretty-json-status";
    });

    toolbar.appendChild(button);
    toolbar.appendChild(status);
    textarea.parentNode.insertBefore(toolbar, textarea);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("textarea.pretty-json").forEach(setup);
  });
})();
