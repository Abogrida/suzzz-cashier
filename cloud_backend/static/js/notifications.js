// Professional Notification System
class NotificationManager {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.createContainer());
        } else {
            this.createContainer();
        }
    }

    createContainer() {
        // Create notification container if it doesn't exist
        if (!document.getElementById('notification-container')) {
            if (!document.body) {
                console.error('document.body is null, retrying...');
                setTimeout(() => this.createContainer(), 100);
                return;
            }
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.className = 'fixed top-4 left-4 z-[99999] space-y-2';
            this.container.style.zIndex = '99999';
            this.container.style.pointerEvents = 'none'; // Allow clicks to pass through
            this.container.style.position = 'fixed';
            this.container.style.top = '1rem';
            this.container.style.left = '1rem';
            document.body.appendChild(this.container);
            console.log('Notification container created and appended to body');
        } else {
            this.container = document.getElementById('notification-container');
            console.log('Notification container already exists');
        }
    }

    show(message, type = 'info', duration = 3000) {
        console.log('=== NOTIFICATION SHOW ===', type, message);
        console.log('Container exists:', !!this.container);
        const notification = document.createElement('div');
        const id = 'notif-' + Date.now();
        notification.id = id;

        // Type-based styling
        const typeStyles = {
            success: 'bg-green-500 border-green-600',
            error: 'bg-red-500 border-red-600',
            warning: 'bg-yellow-500 border-yellow-600',
            info: 'bg-blue-500 border-blue-600'
        };

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        notification.className = `${typeStyles[type] || typeStyles.info} text-white px-6 py-4 rounded-lg shadow-2xl border-2 flex items-center gap-3 min-w-[350px] max-w-[500px]`;
        notification.style.zIndex = '99999';
        notification.style.pointerEvents = 'auto'; // Allow clicks on notification
        notification.style.position = 'relative';
        notification.style.transform = 'translateX(100%)';
        notification.style.opacity = '0';
        notification.style.transition = 'all 0.3s ease-out';

        notification.innerHTML = `
            <div class="flex-1 flex items-center gap-3">
                <span class="text-3xl font-bold">${icons[type] || icons.info}</span>
                <span class="flex-1 text-base font-bold">${message}</span>
            </div>
            <button onclick="notificationManager.remove('${id}')" class="text-white hover:text-gray-200 text-2xl font-bold">&times;</button>
        `;

        if (!this.container) {
            this.init();
        }

        // Ensure container is visible and exists
        if (this.container) {
            this.container.style.pointerEvents = 'none';
            this.container.style.display = 'block';
            this.container.style.visibility = 'visible';
            this.container.appendChild(notification);
            console.log('Notification appended to container, container children:', this.container.children.length);

            // Force reflow to ensure animation works
            void notification.offsetHeight;

            // Animate in immediately - use setTimeout to ensure DOM is ready
            setTimeout(() => {
                notification.style.transform = 'translateX(0)';
                notification.style.opacity = '1';
                console.log('Notification animated in, transform:', notification.style.transform, 'opacity:', notification.style.opacity);
            }, 100);
        } else {
            console.error('Notification container not found! Creating fallback...');
            // Fallback: append directly to body
            notification.style.position = 'fixed';
            notification.style.top = '1rem';
            notification.style.left = '1rem';
            document.body.appendChild(notification);
            setTimeout(() => {
                notification.style.transform = 'translateX(0)';
                notification.style.opacity = '1';
            }, 100);
        }

        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                this.remove(id);
            }, duration);
        }

        return id;
    }

    remove(id) {
        const notification = document.getElementById(id);
        if (notification) {
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }

    success(message, duration = 3000) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = 4000) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration = 3500) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = 3000) {
        return this.show(message, 'info', duration);
    }

    // Confirm dialog using notification system
    async confirm(message, confirmText = 'نعم', cancelText = 'إلغاء') {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
            overlay.id = 'confirm-overlay';

            const dialog = document.createElement('div');
            dialog.className = 'bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl';

            dialog.innerHTML = `
                <div class="mb-4">
                    <h3 class="text-xl font-bold text-gray-800 mb-2">تأكيد</h3>
                    <p class="text-gray-600">${message}</p>
                </div>
                <div class="flex gap-3 justify-end">
                    <button id="confirm-cancel" class="px-6 py-2 bg-gray-200 text-gray-800 rounded-lg font-semibold hover:bg-gray-300 transition">
                        ${cancelText}
                    </button>
                    <button id="confirm-ok" class="px-6 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition">
                        ${confirmText}
                    </button>
                </div>
            `;

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            const removeOverlay = () => {
                overlay.remove();
            };

            document.getElementById('confirm-ok').addEventListener('click', () => {
                removeOverlay();
                resolve(true);
            });

            document.getElementById('confirm-cancel').addEventListener('click', () => {
                removeOverlay();
                resolve(false);
            });

            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    removeOverlay();
                    resolve(false);
                }
            });
        });
    }
}

// Global instance
const notificationManager = new NotificationManager();
window.notificationManager = notificationManager;

