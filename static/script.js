

document.addEventListener('DOMContentLoaded', () => {
    const rows = document.querySelectorAll('tbody tr'); // Sélectionne toutes les lignes du tableau
    const contractGroups = {}; // Objet pour regrouper les lignes par numéro de contrat

    // Regrouper les lignes par numéro de contrat
    rows.forEach(row => {
        const contractNumber = row.getAttribute('data-contract-number');
        if (!contractGroups[contractNumber]) {
            contractGroups[contractNumber] = [];
        }
        contractGroups[contractNumber].push(row);
    });

    // Appliquer les styles conditionnels
    Object.entries(contractGroups).forEach(([contractNumber, group]) => {
        let hasVV = false;
        let hasVR = false;

        // Vérifier si le groupe contient VV et/ou VR
        group.forEach(row => {
            const classType = row.getAttribute('data-class-type');
            if (classType === 'VV') {
                hasVV = true;
            }
            if (classType === 'VR') {
                hasVR = true;
            }
        });

        // Appliquer les couleurs si le groupe contient à la fois VV et VR
        group.forEach(row => {
            const classType = row.getAttribute('data-class-type');
            if (classType === 'VR') {
                row.style.backgroundColor = 'green'; // Vert pour VR
            } else if (classType === 'VV' && hasVR) {
                row.style.backgroundColor = 'orange'; // Orange pour VV associé à un VR
            }
        });
    });
});
