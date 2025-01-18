document.addEventListener('DOMContentLoaded', () => {
    // Function to sort a table
    const sortTable = (table, colIndex, isNumeric) => {
        const rows = Array.from(table.querySelector('tbody').rows);

        // Determine sort direction (ascending/descending)
        let direction = table.getAttribute('data-sort-direction') === 'asc' ? 'desc' : 'asc';
        table.setAttribute('data-sort-direction', direction);

        rows.sort((rowA, rowB) => {
            const cellA = rowA.cells[colIndex].innerText.trim();
            const cellB = rowB.cells[colIndex].innerText.trim();

            if (isNumeric) {
                return direction === 'asc'
                    ? parseFloat(cellA) - parseFloat(cellB)
                    : parseFloat(cellB) - parseFloat(cellA);
            } else {
                return direction === 'asc'
                    ? cellA.localeCompare(cellB)
                    : cellB.localeCompare(cellA);
            }
        });

        // Append sorted rows to the table
        const tbody = table.querySelector('tbody');
        rows.forEach(row => tbody.appendChild(row));
    };

    // Attach click events to sortable table headers
    document.querySelectorAll('th.sortable').forEach(header => {
        header.addEventListener('click', () => {
            const table = header.closest('table');
            const colIndex = Array.from(header.parentNode.children).indexOf(header);
            const isNumeric = header.dataset.type === 'number';

            // Sort the table by the clicked column
            sortTable(table, colIndex, isNumeric);

            // Update sort icon
            document.querySelectorAll('th').forEach(th => th.classList.remove('sorted-asc', 'sorted-desc'));
            header.classList.add(table.getAttribute('data-sort-direction') === 'asc' ? 'sorted-asc' : 'sorted-desc');
        });
    });
});
