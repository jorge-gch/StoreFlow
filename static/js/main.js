/**
 * StoreFlow - Javascript Base
 * Manejo interactivo de sidebar y componentes
 */

document.addEventListener('DOMContentLoaded', function () {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const appLayout = document.getElementById('appLayout');

    // Crear overlay para dispositivos móviles
    let overlay = document.querySelector('.sidebar-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        document.body.appendChild(overlay);
    }

    if (sidebarToggle && appLayout) {
        sidebarToggle.addEventListener('click', function (e) {
            e.preventDefault();
            if (window.innerWidth < 992) {
                document.body.classList.toggle('sidebar-open');
            } else {
                appLayout.classList.toggle('sidebar-collapsed');
            }
        });

        // Cerrar sidebar al hacer clic en el overlay (en móvil)
        overlay.addEventListener('click', function () {
            document.body.classList.remove('sidebar-open');
        });
    }

    // Auto-cierre de alertas informativas después de 6 segundos
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            try {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            } catch (err) {
                // Si bootstrap no está disponible o la alerta ya fue cerrada
            }
        }, 6000);
    });
});
