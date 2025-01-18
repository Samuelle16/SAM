document.addEventListener('DOMContentLoaded', () => {
    // Focus animation on input fields
    const inputs = document.querySelectorAll('input, button');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            input.style.boxShadow = '0 0 5px rgba(0, 0, 0, 0.5)';
        });
        input.addEventListener('blur', () => {
            input.style.boxShadow = 'none';
        });
    });

    // Notification system
    const successMessage = document.querySelector('.success');
    const errorMessage = document.querySelector('.error');
    if (successMessage || errorMessage) {
        setTimeout(() => {
            const message = successMessage || errorMessage;
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 1000); // Remove message after fade out
        }, 3000); // Display for 3 seconds
    }

    // Dropdown toggle
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        const button = dropdown.querySelector('.dropbtn');
        const content = dropdown.querySelector('.dropdown-content');
        button.addEventListener('click', (e) => {
            e.preventDefault();
            content.classList.toggle('show');
        });
    });

    // Close dropdown if clicked outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown-content').forEach(content => {
                content.classList.remove('show');
            });
        }
    });
});
