document.addEventListener("DOMContentLoaded", () => {
    const audio = document.getElementById("background-audio");
    const mainContent = document.getElementById("main-content");
    const links = document.querySelectorAll("a");

    // Fonction pour charger une nouvelle page via AJAX
    const loadPage = (url) => {
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.text();
            })
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, "text/html");
                const newContent = doc.querySelector("#main-content").innerHTML;

                // Met à jour le contenu principal
                mainContent.innerHTML = newContent;

                // Met à jour l'URL sans recharger la page
                window.history.pushState({}, "", url);

                // Réinitialise les événements pour les nouveaux liens
                attachLinkEvents();
            })
            .catch(error => console.error("Erreur lors du chargement de la page :", error));
    };

    // Ajoute des événements aux liens
    const attachLinkEvents = () => {
        const links = document.querySelectorAll("a");
        links.forEach(link => {
            link.addEventListener("click", (event) => {
                event.preventDefault(); // Empêche le comportement par défaut
                const url = link.href;
                loadPage(url); // Charge la nouvelle page via AJAX
            });
        });
    };

    // Charge la première page si nécessaire
    attachLinkEvents();

    // S'assure que l'audio continue à jouer
    if (!audio.playing) {
        audio.play().catch(error => {
            console.log("Autoplay bloqué : interaction utilisateur requise.");
        });
    }
});
