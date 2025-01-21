document.addEventListener('DOMContentLoaded', () => {
    const links = document.querySelectorAll('a');
    const contentContainer = document.getElementById('main-content');

    links.forEach(link => {
        link.addEventListener('click', event => {
            const url = link.getAttribute('href');
            if (url.startsWith('/')) { // Vérifiez que le lien est interne
                event.preventDefault();

                fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                    .then(response => response.text())
                    .then(data => {
                        // Parse and replace content
                        const parser = new DOMParser();
                        const newDoc = parser.parseFromString(data, 'text/html');
                        const newContent = newDoc.getElementById('main-content');
                        if (newContent) {
                            contentContainer.innerHTML = newContent.innerHTML;
                            window.history.pushState(null, '', url);
                        }
                    })
                    .catch(error => console.error('Error loading page:', error));
            }
        });
    });
});
