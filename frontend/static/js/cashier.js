// Global state
let currentOrder = {
    items: [],
    orderNumber: null,
    tableNumber: 0,
    orderType: 'takeaway', // 'takeaway' or 'delivery'
    submittedItems: [], // Items that have been submitted to kitchen
    discount: 0, // Discount value
    discountType: 'percent', // 'percent' or 'amount'
    numberOfPeople: 1 // Number of people
};
let categories = [];
let products = [];
let filteredProducts = [];
let selectedCategoryId = null;
let ws = null;

// Global AudioContext
let audioContext = null;

function initAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
}

// Initialize audio context on first user interaction
document.addEventListener('click', initAudioContext, { once: true });
document.addEventListener('touchstart', initAudioContext, { once: true });
document.addEventListener('keydown', initAudioContext, { once: true });

// Play notification sound
function playNotificationSound() {
    try {
        initAudioContext();

        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        // Set frequency and type for a pleasant notification sound
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';

        // Set volume envelope
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

        // Play sound
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);

        console.log('Notification sound played');
    } catch (error) {
        console.warn('Could not play notification sound:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check authentication
    const auth = sessionStorage.getItem('authenticated');
    const pageType = sessionStorage.getItem('pageType');
    if (auth !== 'true' || pageType !== 'cashier') {
        window.location.href = '/';
        return;
    }

    // Set default to "All" category
    selectedCategoryId = null;

    loadCategories();
    loadProducts();
    setupWebSocket();
    setupEventListeners();
    setupSearch();
    updatePendingInvoicesCount();
    updateTablesCount();
    updatePendingInvoicesCount();
    updateTablesCount();
    checkCurrentShift();
    checkPlayStationStatus(); // Check PS status on load
    // Update counts with optimized intervals (longer intervals for better performance)
    setInterval(updatePendingInvoicesCount, 8000); // Increased from 5s to 8s
    setInterval(updateTablesCount, 8000); // Increased from 5s to 8s
    setInterval(checkCurrentShift, 15000); // Increased from 10s to 15s
    setInterval(checkShiftOverdue, 90000); // Increased from 60s to 90s

    // Auto-close shift disabled - shifts should only be closed manually
    // setupAutoCloseShift();

    // Fix products scroll
    fixProductsScroll();
    setInterval(fixProductsScroll, 1000);
});

// Setup auto-close shift on page unload
function setupAutoCloseShift() {
    let isClosing = false;

    // Close shift when page is being unloaded
    window.addEventListener('beforeunload', async (e) => {
        if (isClosing) return;
        isClosing = true;

        if (currentShift && currentShift.status === 'open') {
            // Use sendBeacon for reliable delivery even if page is closing
            const shiftId = currentShift.id;
            const data = JSON.stringify({ cash_drawer_amount: 0 });

            // Try to close shift using sendBeacon (more reliable than fetch)
            navigator.sendBeacon(`/api/shifts/${shiftId}/close`, data);

            // Also try with fetch (with keepalive flag)
            try {
                await fetch(`/api/shifts/${shiftId}/close`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: data,
                    keepalive: true
                });
            } catch (err) {
                console.warn('Could not close shift on page unload:', err);
            }
        }
    });

    // Also handle visibility change (tab/window hidden)
    document.addEventListener('visibilitychange', async () => {
        if (document.hidden && currentShift && currentShift.status === 'open') {
            // Page is hidden - check if we should close shift
            // Only close if it's been open for a while (to avoid closing on temporary tab switches)
            // This is a safety measure
        }
    });
}

// Setup WebSocket
function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data.type, data);

        if (data.type === 'new_order' || data.type === 'order_completed' || data.type === 'order_cancelled') {
            updatePendingInvoicesCount();
        } else if (data.type === 'discount_permission_updated') {
            // Real-time update of discount permission
            console.log('Discount permission updated via WebSocket:', data);
            if (window.notificationManager) {
                window.notificationManager.info('تم تحديث صلاحية الخصم');
            }
            // If invoice details modal is open, refresh the permission check
            const invoiceModal = document.getElementById('invoiceDetailsModal');
            if (invoiceModal && !invoiceModal.classList.contains('hidden')) {
                // Re-check permission and update UI
                showInvoiceDetailsModal();
            }
        } else if (data.type === 'table_created' || data.type === 'table_closed') {
            // Update tables count badge
            updateTablesCount();
            // Update tables if modal is open
            const tablesModal = document.getElementById('tablesModal');
            if (tablesModal && !tablesModal.classList.contains('hidden')) {
                loadTables();
            }
        } else if (data.type === 'new_order' && data.order && data.order.table_number > 0) {
            // New order from tablet for a table - update tables count and modal
            console.log('New order received for table:', data.order.table_number, data.order);
            updateTablesCount();
            const tablesModal = document.getElementById('tablesModal');
            if (tablesModal && !tablesModal.classList.contains('hidden')) {
                loadTables();
            }
            // Play sound notification FIRST
            console.log('Playing notification sound for new order');
            playNotificationSound();
            // Show CLEAR and VISIBLE notification message - FORCE display immediately
            setTimeout(() => {
                if (window.notificationManager) {
                    const notifId = window.notificationManager.success(`🔔 طلب جديد للطاولة ${data.order.table_number}`, 5000);
                    console.log('Notification shown for new order, ID:', notifId);
                } else {
                    console.error('NotificationManager not available!');
                    // Fallback: create notification manually
                    createFallbackNotification(`طلب جديد للطاولة ${data.order.table_number}`, 'success');
                }
            }, 200);
            // Auto-open table in cashier if not already open
            if (currentOrder.tableNumber !== data.order.table_number) {
                setTimeout(() => {
                    openTableOrder(data.order.table_number);
                }, 1000);
            } else {
                // If table is already open, reload the order to show new items with additions
                setTimeout(() => {
                    if (data.order && data.order.id) {
                        loadOrder(data.order.id);
                    }
                }, 500);
            }
        } else if (data.type === 'order_updated' && data.order && data.order.table_number > 0) {
            // Order updated for a table - update tables count (NO NOTIFICATIONS)
            console.log('Order updated for table:', data.order.table_number, data.order);
            updateTablesCount();
            const tablesModal = document.getElementById('tablesModal');
            if (tablesModal && !tablesModal.classList.contains('hidden')) {
                loadTables();
            }
            // If current table is the updated one, reload it to show additions (silently, no notifications)
            if (currentOrder.tableNumber === data.order.table_number) {
                setTimeout(() => {
                    if (data.order && data.order.id) {
                        loadOrder(data.order.id);
                    } else {
                        loadTableOrder(data.order.table_number);
                    }
                }, 500);
            }
        } else if (data.type === 'table_updated') {
            // Table updated - could be order update OR PlayStation update
            console.log('Table updated:', data.table);

            // Update PlayStation tables if modal is open - Real-time Sync
            if (window.playstationModalVisible && window.loadPlaystationTables) {
                window.loadPlaystationTables();
            }

            if (data.table && data.table.order_id) {
                // Table updated with new order - notify if it's a new order
                updateTablesCount();
                const tablesModal = document.getElementById('tablesModal');
                if (tablesModal && !tablesModal.classList.contains('hidden')) {
                    loadTables();
                }
                // Check if this is a new order (order_updated should handle this, but just in case)
                // Only notify if we didn't already handle order_updated
                if (currentOrder.tableNumber !== data.table.table_number) {
                    // This might be a new order - play sound and notify
                    console.log('Table updated with new order, playing notification');
                    playNotificationSound();
                    setTimeout(() => {
                        if (window.notificationManager) {
                            window.notificationManager.info(`🔔 تم تحديث الطاولة ${data.table.table_number}`, 4000);
                        }
                    }, 100);
                }
            }
        } else if (data.type === 'order_completed' && data.order && data.order.table_number > 0) {
            // Order completed for a table - close table and update
            updateTablesCount();
            const tablesModal = document.getElementById('tablesModal');
            if (tablesModal && !tablesModal.classList.contains('hidden')) {
                loadTables();
            }
        } else if (data.type === 'table_closed' || data.type === 'table_deleted') {
            // Table closed or deleted - update tables count and modal
            updateTablesCount();
            const tablesModal = document.getElementById('tablesModal');
            if (tablesModal && !tablesModal.classList.contains('hidden')) {
                loadTables();
            }
        } else if (data.type === 'categories_updated') {
            // Categories updated - reload categories
            console.log('Categories updated via WebSocket, reloading...');
            loadCategories();
        } else if (data.type === 'products_updated') {
            // Products updated - reload products
            console.log('Products updated via WebSocket, reloading...');
            loadProducts();
        } else if (data.type === 'shift_opened') {
            // Shift opened - reload shift status
            console.log('Shift opened via WebSocket');
            checkCurrentShift();
        } else if (data.type === 'shift_closed') {
            // Shift closed - reload shift status
            console.log('Shift closed via WebSocket');
            checkCurrentShift();
        } else if (data.type === 'shift_settings_updated') {
            // Shift settings updated - reload available shifts
            console.log('Shift settings updated via WebSocket');
            checkCurrentShift();
            // Reload shift modal to show new shifts
            if (currentShift) {
                // If shift modal is open, refresh it
                const shiftModal = document.getElementById('shiftModal');
                if (shiftModal && !shiftModal.classList.contains('hidden')) {
                    showShiftModal();
                }
            }
        } else if (data.type === 'settings_updated') {
            // Settings updated - reload settings dependent UI
            console.log('Settings updated via WebSocket');
            checkPlayStationStatus();
        }
    };
}

// Setup event listeners
function setupEventListeners() {
    // Table number is now display-only, no event listener needed

    // Exit order button
    const exitOrderBtn = document.getElementById('exitOrderBtn');
    if (exitOrderBtn) {
        exitOrderBtn.onclick = async function (e) {
            e.preventDefault();
            e.stopPropagation();
            try {
                await exitOrder();
            } catch (error) {
                console.error('Error in exitOrder:', error);
                if (window.notificationManager) {
                    window.notificationManager.error('خطأ في الخروج من الفاتورة');
                }
            }
        };
    } else {
        console.error('exitOrderBtn not found!');
    }

    // Order button - prints kitchen receipt and locks order
    const orderBtn = document.getElementById('orderBtn');
    if (orderBtn) {
        // Remove any existing event listeners
        orderBtn.onclick = null;
        // Add new event listener
        orderBtn.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (orderBtn.disabled) return;
            try {
                orderBtn.disabled = true;
                await submitOrder();
            } catch (error) {
                console.error('Error in submitOrder:', error);
                if (window.notificationManager) {
                    window.notificationManager.error('خطأ في تنفيذ الطلب: ' + (error.message || 'خطأ غير معروف'));
                }
            } finally {
                orderBtn.disabled = false;
            }
        });
    } else {
        console.error('orderBtn not found!');
    }

    // Finish button - prints full invoice and completes order
    const finishBtn = document.getElementById('finishBtn');
    if (finishBtn) {
        // Remove any existing event listeners
        finishBtn.onclick = null;
        // Add new event listener
        finishBtn.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (finishBtn.disabled) return;
            try {
                finishBtn.disabled = true;
                await completeOrder();
            } catch (error) {
                console.error('Error in completeOrder:', error);
                if (window.notificationManager) {
                    window.notificationManager.error('خطأ في انهاء الطلب: ' + (error.message || 'خطأ غير معروف'));
                }
            } finally {
                finishBtn.disabled = false;
            }
        });
    } else {
        console.error('finishBtn not found!');
    }

    // Logout button
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            logout();
        });
    }

    // Payment modal event listeners with debouncing
    const paymentPaidInput = document.getElementById('paymentPaid');
    if (paymentPaidInput) {
        paymentPaidInput.addEventListener('input', window.PerformanceUtils ? window.PerformanceUtils.debounce(updatePaymentRemaining, 150) : updatePaymentRemaining);
    }

    const paymentCashAmountInput = document.getElementById('paymentCashAmount');
    if (paymentCashAmountInput) {
        paymentCashAmountInput.addEventListener('input', window.PerformanceUtils ? window.PerformanceUtils.debounce(updatePaymentRemaining, 150) : updatePaymentRemaining);
    }

    const paymentCardAmountInput = document.getElementById('paymentCardAmount');
    if (paymentCardAmountInput) {
        paymentCardAmountInput.addEventListener('input', window.PerformanceUtils ? window.PerformanceUtils.debounce(updatePaymentRemaining, 150) : updatePaymentRemaining);
    }

    const paymentTipInput = document.getElementById('paymentTip');
    if (paymentTipInput) {
        paymentTipInput.addEventListener('input', () => {
            // Tip doesn't affect remaining, but we can update if needed
        });
    }

    // Payment method buttons
    document.querySelectorAll('.payment-method-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const method = e.currentTarget.getAttribute('data-method');
            selectPaymentMethod(method);
        });
    });

    // Payment finish button
    const paymentFinishBtn = document.getElementById('paymentFinishBtn');
    if (paymentFinishBtn) {
        paymentFinishBtn.addEventListener('click', completeOrderWithPayment);
    }

    // Close payment modal button
    const closePaymentModalBtn = document.getElementById('closePaymentModalBtn');
    if (closePaymentModalBtn) {
        closePaymentModalBtn.addEventListener('click', closePaymentModal);
    }

    // Close payment modal on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const paymentModal = document.getElementById('paymentModal');
            if (paymentModal && !paymentModal.classList.contains('hidden')) {
                closePaymentModal();
            }
        }
    });

    // Make closePaymentModal available globally
    window.closePaymentModal = closePaymentModal;

    // Invoice details button
    const invoiceDetailsBtn = document.getElementById('invoiceDetailsBtn');
    if (invoiceDetailsBtn) {
        invoiceDetailsBtn.addEventListener('click', showInvoiceDetailsModal);
    }

    // Invoice details modal close button
    const closeInvoiceDetailsModalBtn = document.getElementById('closeInvoiceDetailsModalBtn');
    if (closeInvoiceDetailsModalBtn) {
        closeInvoiceDetailsModalBtn.addEventListener('click', closeInvoiceDetailsModal);
    }

    // Invoice details cancel button
    const cancelInvoiceDetailsBtn = document.getElementById('cancelInvoiceDetailsBtn');
    if (cancelInvoiceDetailsBtn) {
        cancelInvoiceDetailsBtn.addEventListener('click', closeInvoiceDetailsModal);
    }

    // Invoice details save button
    const saveInvoiceDetailsBtn = document.getElementById('saveInvoiceDetailsBtn');
    if (saveInvoiceDetailsBtn) {
        saveInvoiceDetailsBtn.addEventListener('click', saveInvoiceDetails);
    }

    // Invoice discount input listener
    const invoiceDiscountInput = document.getElementById('invoiceDiscount');
    if (invoiceDiscountInput) {
        invoiceDiscountInput.addEventListener('input', updateInvoiceNetAmount);
    }

    // Discount type buttons
    const discountTypePercentBtn = document.getElementById('discountTypePercent');
    const discountTypeAmountBtn = document.getElementById('discountTypeAmount');
    if (discountTypePercentBtn && discountTypeAmountBtn) {
        discountTypePercentBtn.addEventListener('click', () => {
            currentOrder.discountType = 'percent';
            discountTypePercentBtn.className = 'flex-1 px-4 py-2 bg-teal-600 text-white rounded-lg font-bold text-sm shadow-md border-2 border-teal-700 hover:bg-teal-700 transition';
            discountTypeAmountBtn.className = 'flex-1 px-4 py-2 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-sm shadow-sm hover:bg-gray-50 hover:border-gray-400 transition';
            document.getElementById('discountTypeLabel').textContent = '%';
            const discountInput = document.getElementById('invoiceDiscount');
            if (discountInput) {
                discountInput.max = '100';
                discountInput.placeholder = '0';
            }
            updateInvoiceNetAmount();
        });

        discountTypeAmountBtn.addEventListener('click', () => {
            currentOrder.discountType = 'amount';
            discountTypeAmountBtn.className = 'flex-1 px-4 py-2 bg-teal-600 text-white rounded-lg font-bold text-sm shadow-md border-2 border-teal-700 hover:bg-teal-700 transition';
            discountTypePercentBtn.className = 'flex-1 px-4 py-2 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-sm shadow-sm hover:bg-gray-50 hover:border-gray-400 transition';
            document.getElementById('discountTypeLabel').textContent = 'ج.م';
            const discountInput = document.getElementById('invoiceDiscount');
            if (discountInput) {
                discountInput.removeAttribute('max');
                discountInput.placeholder = '0.00';
            }
            updateInvoiceNetAmount();
        });
    }

    // Additions button
    const additionsBtn = document.getElementById('additionsBtn');
    if (additionsBtn) {
        additionsBtn.addEventListener('click', showAdditionsModal);
    }

    // All Categories Menu Button (three dots)
    const categoriesMenuBtn = document.getElementById('categoriesMenuBtn');
    if (categoriesMenuBtn) {
        categoriesMenuBtn.addEventListener('click', showAllCategoriesModal);
    }

    // Close All Categories Modal Button
    const closeAllCategoriesModalBtn = document.getElementById('closeAllCategoriesModalBtn');
    if (closeAllCategoriesModalBtn) {
        closeAllCategoriesModalBtn.addEventListener('click', closeAllCategoriesModal);
    }

    // Additions modal close button
    const closeAdditionsModalBtn = document.getElementById('closeAdditionsModalBtn');
    if (closeAdditionsModalBtn) {
        closeAdditionsModalBtn.addEventListener('click', closeAdditionsModal);
    }

    // Additions modal cancel button
    const cancelAdditionsBtn = document.getElementById('cancelAdditionsBtn');
    if (cancelAdditionsBtn) {
        cancelAdditionsBtn.addEventListener('click', closeAdditionsModal);
    }

    // Additions modal save button
    const saveAdditionsBtn = document.getElementById('saveAdditionsBtn');
    if (saveAdditionsBtn) {
        saveAdditionsBtn.addEventListener('click', saveAdditions);
    }

    // Product select change listener
    const additionsProductSelect = document.getElementById('additionsProductSelect');
    if (additionsProductSelect) {
        additionsProductSelect.addEventListener('change', loadProductAdditions);
    }

    // Tables button
    const tablesBtn = document.getElementById('tablesBtn');
    if (tablesBtn) {
        tablesBtn.addEventListener('click', showTablesModal);
    }

    // Phone button (call tablet)
    const phoneBtn = document.getElementById('phoneBtn');
    if (phoneBtn) {
        phoneBtn.onclick = async () => {
            await callTablet();
        };
    }

    // Tables modal close button
    const closeTablesModalBtn = document.getElementById('closeTablesModalBtn');
    if (closeTablesModalBtn) {
        closeTablesModalBtn.addEventListener('click', closeTablesModal);
    }

    // New table button
    const newTableBtn = document.getElementById('newTableBtn');
    if (newTableBtn) {
        newTableBtn.addEventListener('click', showNewTableModal);
    }

    // New table modal buttons
    const closeNewTableModalBtn = document.getElementById('closeNewTableModalBtn');
    const cancelNewTableBtn = document.getElementById('cancelNewTableBtn');
    if (closeNewTableModalBtn) {
        closeNewTableModalBtn.addEventListener('click', closeNewTableModal);
    }
    if (cancelNewTableBtn) {
        cancelNewTableBtn.addEventListener('click', closeNewTableModal);
    }

    // Save new table button
    const saveNewTableBtn = document.getElementById('saveNewTableBtn');
    if (saveNewTableBtn) {
        saveNewTableBtn.addEventListener('click', saveNewTable);
    }

    // Open Drawer Button
    const openDrawerBtn = document.getElementById('openDrawerBtn');
    if (openDrawerBtn) {
        openDrawerBtn.addEventListener('click', async () => {
            await openCashDrawer();
        });
    }
}

// Open Cash Drawer
async function openCashDrawer() {
    try {
        const response = await fetch('/api/cash-drawer/open', {
            method: 'POST'
        });

        if (response.ok) {
            if (window.notificationManager) {
                window.notificationManager.success('تم فتح الدرج بنجاح');
            }
        } else {
            console.error('Failed to open drawer');
            if (window.notificationManager) {
                window.notificationManager.error('فشل في فتح الدرج');
            }
        }
    } catch (error) {
        console.error('Error opening drawer:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في الاتصال');
        }
    }
}

// Logout function
function logout() {
    sessionStorage.removeItem('authenticated');
    sessionStorage.removeItem('pageType');
    window.location.href = '/';
}

// Submit order - prints kitchen receipt (without prices) for NEW quantities only
async function submitOrder() {
    // Get items that have new quantities (quantity > submitted_quantity)
    const itemsWithNewQuantity = currentOrder.items.filter(item =>
        item.quantity > item.submitted_quantity
    );

    // Calculate total new pieces IMMEDIATELY (before submitted_quantity is updated)
    const totalNewPieces = itemsWithNewQuantity.reduce((sum, item) => {
        return sum + (item.quantity - (item.submitted_quantity || 0));
    }, 0);

    if (itemsWithNewQuantity.length === 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('لا توجد كميات جديدة للطلب');
        }
        return;
    }

    console.log('Items with new quantity:', itemsWithNewQuantity);

    // Create order if not exists, or update existing order with new items
    let order = null;
    if (!currentOrder.orderNumber) {
        // Create new order with all items
        order = await createOrder();
        if (!order) return;

        // Check for Browser Print Preview
        if (order.print_preview) {
            printImageInBrowser(order.print_preview);
            // Set flag to avoid double printing
            window.lastKitchenPrintTime = Date.now();
        }

        // Mark all items as submitted since this is a new order
        currentOrder.items.forEach(item => {
            item.submitted_quantity = item.quantity;
        });
    } else {
        // Order exists - update it with new items
        try {
            // Get the order by ID directly
            const orderResponse = await fetch(`/api/orders?status=pending`);
            if (!orderResponse.ok) {
                throw new Error('Failed to fetch orders');
            }
            const orders = await orderResponse.json();
            order = orders.find(o => o.order_number === currentOrder.orderNumber);

            if (!order) {
                // Order not found, create new one
                order = await createOrder();
                if (!order) return;
                currentOrder.items.forEach(item => {
                    item.submitted_quantity = item.quantity;
                });
            } else {
                // Get saved items from order
                const savedItems = order.items || [];
                console.log('Saved items:', savedItems);
                console.log('Current items:', currentOrder.items);

                // Find items that need to be added/updated
                const itemsToAdd = [];

                // Compare current items with saved items
                // IMPORTANT: Only add items that have quantity > submitted_quantity
                itemsWithNewQuantity.forEach(currentItem => {
                    // Find if this item exists in saved order
                    const savedItem = savedItems.find(si =>
                        si.product_id === currentItem.product_id &&
                        (si.size || null) === (currentItem.size || null)
                    );

                    if (!savedItem) {
                        // New item - add the new quantity (quantity - submitted_quantity)
                        const newQuantity = currentItem.quantity - currentItem.submitted_quantity;
                        console.log('New item to add:', currentItem, 'new quantity:', newQuantity);
                        if (newQuantity > 0) {
                            itemsToAdd.push({
                                product_id: currentItem.product_id,
                                quantity: newQuantity,
                                size: currentItem.size || null
                            });
                        }
                    } else {
                        // Existing item - check if current quantity > saved quantity
                        // The new quantity is the difference between current and submitted
                        const newQuantity = currentItem.quantity - currentItem.submitted_quantity;
                        if (newQuantity > 0) {
                            console.log('Item quantity increased:', currentItem.product_name, 'new quantity:', newQuantity);
                            itemsToAdd.push({
                                product_id: currentItem.product_id,
                                quantity: newQuantity,
                                size: currentItem.size || null
                            });
                        }
                    }
                });

                console.log('Items to add to order:', itemsToAdd);

                // Update order with new items
                if (itemsToAdd.length > 0) {
                    const updateResponse = await fetch(`/api/orders/${order.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            table_number: currentOrder.tableNumber,
                            items: itemsToAdd
                        })
                    });

                    if (updateResponse.ok) {
                        order = await updateResponse.json();
                        console.log('Order updated successfully:', order);

                        // Check for Browser Print Preview
                        if (order.print_preview) {
                            printImageInBrowser(order.print_preview);
                            // Set flag to avoid double printing
                            window.lastKitchenPrintTime = Date.now();
                        }

                        // Reload order to get updated items
                        const reloadResponse = await fetch(`/api/orders/${order.id}`);
                        if (reloadResponse.ok) {
                            const updatedOrder = await reloadResponse.json();
                            console.log('Reloaded order:', updatedOrder);

                            // Update currentOrder items with submitted quantities from database
                            updatedOrder.items.forEach(savedItem => {
                                const currentItem = currentOrder.items.find(ci =>
                                    ci.product_id === savedItem.product_id &&
                                    (ci.size || null) === (savedItem.size || null)
                                );
                                if (currentItem) {
                                    currentItem.submitted_quantity = savedItem.quantity;
                                    console.log('Updated submitted_quantity for item:', currentItem.product_name, 'to', savedItem.quantity);
                                }
                            });

                            // Update order reference
                            order = updatedOrder;
                        }

                        if (window.notificationManager) {
                            window.notificationManager.success('تم تحديث الطلب بنجاح');
                        }
                    } else {
                        const errorData = await updateResponse.json().catch(() => ({ detail: 'Unknown error' }));
                        console.error('Failed to update order:', errorData);
                        if (window.notificationManager) {
                            window.notificationManager.error('فشل في تحديث الطلب: ' + (errorData.detail || 'خطأ غير معروف'));
                        }
                        return;
                    }
                } else {
                    // No new items to add, but mark current quantities as submitted
                    console.log('No new items to add, marking as submitted');
                    itemsWithNewQuantity.forEach(item => {
                        item.submitted_quantity = item.quantity;
                    });
                }
            }
        } catch (error) {
            console.error('Error fetching/updating order:', error);
            if (window.notificationManager) {
                window.notificationManager.error('خطأ في تحديث الطلب: ' + (error.message || 'خطأ غير معروف'));
            }
            return;
        }

        if (!order) {
            // If update failed, create new order
            console.log('Order not found, creating new one');
            order = await createOrder();
            if (!order) return;

            // Check for Browser Print Preview
            if (order.print_preview) {
                printImageInBrowser(order.print_preview);
                window.lastKitchenPrintTime = Date.now();
            }

            currentOrder.items.forEach(item => {
                item.submitted_quantity = item.quantity;
            });
        }
    }

    // Try to print kitchen ticket for NEW quantities only, but don't block if it fails
    // Only if we haven't printed recently (within 2 seconds)
    if (!window.lastKitchenPrintTime || (Date.now() - window.lastKitchenPrintTime > 2000)) {
        try {
            // Prepare new items for printing (only items with new quantities)
            const newItemsForPrint = itemsWithNewQuantity.map(item => {
                const newQty = item.quantity - (item.submitted_quantity || 0);
                console.log(`[DEBUG] Print Calc: ${item.product_name} - Qty: ${item.quantity}, Submitted: ${item.submitted_quantity}, calcNew: ${newQty}`);

                // Standard Kitchen Logic: Print ONLY the NEW quantity (Delta).
                // Example: Had 1, Add 1. newQty = 1. Print 1.
                // If newQty <= 0, don't print.
                return {
                    product_name: item.product_name,
                    quantity: newQty > 0 ? newQty : 1, // Safety net
                    size: item.size || null,
                    additions: item.additions || null
                };
            }).filter(item => {
                const newQty = (window.currentOrder.items.find(i => i.product_name === item.product_name)?.quantity || 0) - (window.currentOrder.items.find(i => i.product_name === item.product_name)?.submitted_quantity || 0);
                // Actually simpler: we already calculated it above but we lost the ref.
                // Let's rely on the map result.
                // Wait, the map returns objects.
                // If I return NULL in map, I can filter.
                return true;
            }).filter(item => {
                // We need to re-verify or just handle loop better.
                // Let's rewrite the map nicely.
                return item.quantity > 0;
            });

            // Better implementation of the map/filter
            const finalItemsToPrint = itemsWithNewQuantity.reduce((acc, item) => {
                const newQty = item.quantity - (item.submitted_quantity || 0);
                if (newQty > 0) {
                    acc.push({
                        product_name: item.product_name,
                        quantity: newQty,
                        size: item.size || null,
                        additions: item.additions || null
                    });
                }
                return acc;
            }, []);

            if (finalItemsToPrint.length > 0) {
                // Send new items to print
                const printResponse = await fetch(`/api/print/kitchen/${order.id}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_items: finalItemsToPrint })
                });

                if (printResponse.ok) {
                    const printData = await printResponse.json();
                    if (printData.print_preview) {
                        printImageInBrowser(printData.print_preview);
                    }
                }
            }

            // REMOVED Auto-Print Check per user request ("Return it small like it was")

        } catch (error) {
            console.warn('Printer not available, continuing anyway:', error);
        }
    }

    // Calculate total new pieces BEFORE marking as submitted
    // Calculate total new pieces BEFORE marking as submitted
    // (Moved to top of function to ensure accuracy)

    // Mark current quantities as submitted
    itemsWithNewQuantity.forEach(item => {
        item.submitted_quantity = item.quantity;
    });

    // Show visual feedback with checkmark
    const orderBtn = document.getElementById('orderBtn');
    if (orderBtn) {
        orderBtn.innerHTML = 'طلب ✓';
        orderBtn.className = 'flex-1 px-5 py-3.5 bg-green-500 text-white rounded-lg font-bold text-base shadow-md border-2 border-green-600';

        // Re-enable button after 2 seconds so user can add more items
        setTimeout(() => {
            if (orderBtn) {
                orderBtn.innerHTML = 'طلب';
                orderBtn.className = 'flex-1 px-5 py-3.5 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-base shadow-sm hover:bg-gray-50 hover:border-gray-400 transition';
            }
        }, 2000);
    }

    if (window.notificationManager) {
        window.notificationManager.success(`تم طلب ${totalNewPieces} قطعة جديدة للمطبخ`);
    }
    updateOrderDisplay();
    updatePhoneButtonState();
    updatePendingInvoicesCount();
}

// Load categories (with caching)
async function loadCategories() {
    try {
        console.log('Loading categories...');
        const fetchFn = window.PerformanceUtils ? window.PerformanceUtils.cachedFetch : fetch;
        const response = await fetchFn('/api/categories', {}, 'categories');
        console.log('Categories response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            console.error('Failed to load categories:', response.status, errorText);
            if (window.notificationManager) {
                window.notificationManager.error('خطأ في تحميل الفئات: ' + response.status);
            }
            categories = [];
            renderCategories();
            return;
        }

        categories = await response.json();
        console.log('Categories loaded:', categories);

        if (!Array.isArray(categories)) {
            console.error('Categories is not an array:', categories);
            categories = [];
        }

        renderCategories();
    } catch (error) {
        console.error('Error loading categories:', error);
        console.error('Error details:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في تحميل الفئات: ' + (error.message || 'خطأ غير معروف'));
        }
        categories = [];
        renderCategories();
    }
}

// Render categories on top
function renderCategories() {
    const container = document.getElementById('categoryTabs');
    if (!container) return;

    // Use DocumentFragment for better performance
    const fragment = document.createDocumentFragment();

    // "الكل" button - first and default
    const allTab = document.createElement('button');
    allTab.className = `px-4 py-2 rounded-xl font-bold text-base whitespace-nowrap transition-all duration-200 shadow-sm ${selectedCategoryId === null ? 'bg-teal-600 text-white shadow-md transform scale-105' : 'bg-white border-2 border-gray-200 text-gray-700 hover:border-teal-500 hover:text-teal-600 hover:shadow-md'}`;
    allTab.textContent = 'الكل';
    allTab.onclick = () => filterByCategory(null);
    fragment.appendChild(allTab);

    if (categories && categories.length > 0) {
        categories.forEach(cat => {
            const tab = document.createElement('button');
            tab.className = `px-4 py-2 rounded-xl font-bold text-base whitespace-nowrap transition-all duration-200 shadow-sm ${selectedCategoryId === cat.id ? 'bg-teal-600 text-white shadow-md transform scale-105' : 'bg-white border-2 border-gray-200 text-gray-700 hover:border-teal-500 hover:text-teal-600 hover:shadow-md'}`;
            tab.textContent = cat.name;
            tab.onclick = () => filterByCategory(cat.id);
            fragment.appendChild(tab);
        });
    }

    // Single DOM update
    container.innerHTML = '';
    container.appendChild(fragment);

    // Check if scrolling is needed after rendering
    setTimeout(() => {
        checkCategoriesScroll();
    }, 100);
}

// Check if categories need scrolling and adjust accordingly
function checkCategoriesScroll() {
    const container = document.getElementById('categoryTabs');
    if (!container) return;

    // Check if content overflows
    const hasOverflow = container.scrollWidth > container.clientWidth;

    if (hasOverflow) {
        // Enable scrolling
        container.style.overflowX = 'auto';
        container.style.flexWrap = 'nowrap';
    } else {
        // No overflow, keep natural behavior
        container.style.overflowX = 'auto';
        container.style.flexWrap = 'nowrap';
    }
}

// Load products (with caching)
async function loadProducts() {
    try {
        console.log('Loading products...');
        const fetchFn = window.PerformanceUtils ? window.PerformanceUtils.cachedFetch : fetch;
        const response = await fetchFn('/api/products?enabled=true', {}, 'products');
        console.log('Products response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            console.error('Failed to load products:', response.status, errorText);
            if (window.notificationManager) {
                window.notificationManager.error('خطأ في تحميل المنتجات: ' + response.status);
            }
            products = [];
            filteredProducts = [];
            renderProducts();
            return;
        }

        products = await response.json();
        console.log('Products loaded:', products);

        if (!Array.isArray(products)) {
            console.error('Products is not an array:', products);
            products = [];
        }

        filteredProducts = products;
        renderProducts();
        setTimeout(fixProductsScroll, 100);
    } catch (error) {
        console.error('Error loading products:', error);
        console.error('Error details:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في تحميل المنتجات: ' + (error.message || 'خطأ غير معروف'));
        }
        products = [];
        filteredProducts = [];
        renderProducts();
        setTimeout(fixProductsScroll, 100);
    }
}

// Filter by category
function filterByCategory(categoryId) {
    selectedCategoryId = categoryId;

    // Clear search if active
    const searchInput = document.getElementById('searchInput');
    const searchContainer = document.getElementById('searchContainer');
    if (searchInput && searchInput.value) {
        searchInput.value = '';
        searchQuery = '';
        if (searchContainer) {
            searchContainer.style.width = '40px';
            searchInput.classList.remove('opacity-100');
            searchInput.classList.add('opacity-0', 'cursor-pointer');
        }
    }

    renderCategories();

    if (selectedCategoryId === null) {
        // Show all products
        filteredProducts = products;
    } else {
        // Show only products in selected category
        filteredProducts = products.filter(p => p.category_id === selectedCategoryId);
    }

    renderProducts();
    setTimeout(fixProductsScroll, 100);
}

// Fix products scroll (optimized with requestAnimationFrame)
function fixProductsScroll() {
    requestAnimationFrame(() => {
        const middlePanel = document.getElementById('middlePanel');
        const categoriesBar = document.getElementById('categoriesBar');
        const productsContainer = document.getElementById('productsContainer');

        if (!middlePanel || !categoriesBar || !productsContainer) {
            return;
        }

        // Get actual positions and heights using getBoundingClientRect
        const middlePanelRect = middlePanel.getBoundingClientRect();
        const categoriesBarRect = categoriesBar.getBoundingClientRect();

        // Calculate top position (start after categories bar)
        const topPosition = categoriesBarRect.height;

        // Calculate available height
        const availableHeight = middlePanelRect.height - categoriesBarRect.height;

        if (availableHeight > 0) {
            // Batch style updates
            productsContainer.style.cssText = `
                top: ${topPosition}px;
                height: ${availableHeight}px;
                max-height: ${availableHeight}px;
                overflow-y: auto;
            `;
        }
    });
}

// Render products (optimized with DocumentFragment)
// Render products (optimized with DocumentFragment)
function renderProducts() {
    const container = document.getElementById('productsGrid');
    if (!container) return;

    if (filteredProducts.length === 0) {
        container.innerHTML = '<div class="col-span-full text-center text-gray-400 py-12 text-sm">لا توجد منتجات</div>';
        return;
    }

    // Use DocumentFragment for better performance
    const fragment = document.createDocumentFragment();

    filteredProducts.forEach(product => {
        const card = document.createElement('div');
        card.className = 'product-card bg-white border border-gray-200 rounded-lg overflow-hidden cursor-pointer shadow-sm hover:shadow-md transition-all duration-200';

        // Handle image path - check if it exists and is valid
        let imageHtml = '';
        if (product.image_path && product.image_path.trim() !== '') {
            const imagePath = product.image_path.startsWith('/') ? product.image_path : '/' + product.image_path;
            imageHtml = `<img loading="lazy" src="${imagePath}" alt="${product.name}" class="w-full h-full object-cover" onerror="this.parentElement.innerHTML='<div class=\\'text-xs text-gray-400 text-center p-4\\'>لا توجد صورة</div>'">`;
        } else {
            imageHtml = '<div class="text-xs text-gray-400 text-center p-4">لا توجد صورة</div>';
        }

        // Format price badges
        const hasSizes = product.has_sizes === true ||
            product.has_sizes === 1 ||
            product.has_sizes === "1" ||
            (product.price_s && parseFloat(product.price_s) > 0) ||
            (product.price_m && parseFloat(product.price_m) > 0) ||
            (product.price_l && parseFloat(product.price_l) > 0);

        let priceBadges = '';
        if (hasSizes) {
            const prices = [];
            if (product.price_s && product.price_s > 0) prices.push({ value: product.price_s.toFixed(0) });
            if (product.price_m && product.price_m > 0) prices.push({ value: product.price_m.toFixed(0) });
            if (product.price_l && product.price_l > 0) prices.push({ value: product.price_l.toFixed(0) });

            if (prices.length > 0) {
                const badgesToShow = prices.slice(0, 2);
                if (badgesToShow.length === 2) {
                    priceBadges = `
                        <div class="absolute top-2 right-2 bg-white rounded-full w-8 h-8 md:w-9 md:h-9 flex items-center justify-center shadow-md border border-gray-300 font-bold text-[10px] md:text-xs text-gray-800 z-20">
                            ${badgesToShow[0].value}
                        </div>
                        <div class="absolute top-2 right-11 md:right-12 bg-white rounded-full w-8 h-8 md:w-9 md:h-9 flex items-center justify-center shadow-md border border-gray-300 font-bold text-[10px] md:text-xs text-gray-800 z-20">
                            ${badgesToShow[1].value}
                        </div>
                    `;
                } else {
                    priceBadges = `
                        <div class="absolute top-2 right-2 bg-white rounded-full w-8 h-8 md:w-9 md:h-9 flex items-center justify-center shadow-md border border-gray-300 font-bold text-[10px] md:text-xs text-gray-800 z-20">
                            ${badgesToShow[0].value}
                        </div>
                    `;
                }
            } else {
                priceBadges = `
                    <div class="absolute top-2 right-2 bg-white rounded-full w-8 h-8 md:w-9 md:h-9 flex items-center justify-center shadow-md border border-gray-300 font-bold text-[10px] md:text-xs text-gray-800 z-20">
                        ${product.price.toFixed(0)}
                    </div>
                `;
            }
        } else {
            priceBadges = `
                <div class="absolute top-2 right-2 bg-white rounded-full w-8 h-8 md:w-9 md:h-9 flex items-center justify-center shadow-md border border-gray-300 font-bold text-[10px] md:text-xs text-gray-800 z-20">
                    ${product.price.toFixed(0)}
                </div>
            `;
        }

        card.innerHTML = `
            <div class="relative">
                <div class="w-full h-32 sm:h-40 md:h-48 bg-gray-100 flex items-center justify-center overflow-hidden">
                    ${imageHtml}
                    ${priceBadges}
                </div>
                <button onclick="handleProductClick(${product.id})" class="absolute top-2 left-2 bg-blue-600 text-white rounded-md w-8 h-8 md:w-9 md:h-9 flex items-center justify-center text-lg md:text-xl font-bold hover:bg-blue-700 shadow-md transition z-10">
                    +
                </button>
            </div>
            <div class="p-2 md:p-3 text-center bg-white">
                <div class="font-bold text-gray-800 text-sm md:text-base truncate">${product.name}</div>
            </div>
        `;
        card.onclick = (e) => {
            if (!e.target.closest('button')) {
                handleProductClick(product.id);
            }
        };
        fragment.appendChild(card);
    });

    // Single DOM update
    container.innerHTML = '';
    container.appendChild(fragment);

    // Fix scroll after rendering (use requestAnimationFrame for smoother updates)
    requestAnimationFrame(() => {
        fixProductsScroll();
    });
}

// Handle product click - show size modal if has sizes, otherwise add directly
function handleProductClick(productId) {
    console.log('=== handleProductClick called ===');
    console.log('Product ID:', productId);
    console.log('All products:', products);

    const product = products.find(p => p.id === productId);
    if (!product) {
        console.error('Product not found:', productId);
        if (window.notificationManager) {
            window.notificationManager.error('المنتج غير موجود');
        }
        return;
    }

    console.log('Product found:', product);
    console.log('Product has_sizes (raw):', product.has_sizes);
    console.log('Product has_sizes (type):', typeof product.has_sizes);
    console.log('Product price_s:', product.price_s);
    console.log('Product price_m:', product.price_m);
    console.log('Product price_l:', product.price_l);

    // Check if product has sizes (either has_sizes is true OR has any size prices)
    const hasSizes = product.has_sizes === true ||
        product.has_sizes === 1 ||
        product.has_sizes === "1" ||
        (product.price_s && parseFloat(product.price_s) > 0) ||
        (product.price_m && parseFloat(product.price_m) > 0) ||
        (product.price_l && parseFloat(product.price_l) > 0);

    console.log('Should show size modal:', hasSizes);
    console.log('has_sizes === true:', product.has_sizes === true);
    console.log('has_sizes === 1:', product.has_sizes === 1);
    console.log('price_s > 0:', product.price_s && parseFloat(product.price_s) > 0);
    console.log('price_m > 0:', product.price_m && parseFloat(product.price_m) > 0);
    console.log('price_l > 0:', product.price_l && parseFloat(product.price_l) > 0);

    if (hasSizes) {
        console.log('Showing size modal...');
        showSizeModal(product);
    } else {
        console.log('Adding directly to order (no sizes)');
        addToOrder(productId, null, product.price);
    }
}

// Show size selection modal
function showSizeModal(product) {
    console.log('Showing size modal for product:', product);
    const modal = document.getElementById('sizeModal');
    const productName = document.getElementById('sizeModalProductName');
    const sizeOptions = document.getElementById('sizeOptions');

    if (!modal) {
        console.error('Size modal not found!');
        if (window.notificationManager) {
            window.notificationManager.error('خطأ: نافذة اختيار الحجم غير موجودة');
        }
        return;
    }

    if (!productName || !sizeOptions) {
        console.error('Size modal elements not found!');
        return;
    }

    productName.textContent = product.name;
    sizeOptions.innerHTML = '';

    // Add size options - only show sizes that have prices
    console.log('Adding size options for product:', product.name);
    console.log('price_s:', product.price_s, 'price_m:', product.price_m, 'price_l:', product.price_l);

    if (product.price_s && parseFloat(product.price_s) > 0) {
        const sOption = document.createElement('button');
        sOption.className = 'bg-white border-2 border-gray-300 rounded-lg p-6 hover:border-blue-500 hover:bg-blue-50 transition text-center';
        sOption.innerHTML = `
            <div class="text-3xl font-bold text-gray-800 mb-2">${product.price_s.toFixed(0)}</div>
            <div class="text-lg font-semibold text-gray-600">S</div>
        `;
        sOption.onclick = () => {
            addToOrder(product.id, 'S', product.price_s);
            closeSizeModal();
        };
        sizeOptions.appendChild(sOption);
    }

    if (product.price_m && parseFloat(product.price_m) > 0) {
        const mOption = document.createElement('button');
        mOption.className = 'bg-white border-2 border-gray-300 rounded-lg p-6 hover:border-blue-500 hover:bg-blue-50 transition text-center';
        mOption.innerHTML = `
            <div class="text-3xl font-bold text-gray-800 mb-2">${product.price_m.toFixed(0)}</div>
            <div class="text-lg font-semibold text-gray-600">M</div>
        `;
        mOption.onclick = () => {
            addToOrder(product.id, 'M', product.price_m);
            closeSizeModal();
        };
        sizeOptions.appendChild(mOption);
    }

    if (product.price_l && parseFloat(product.price_l) > 0) {
        const lOption = document.createElement('button');
        lOption.className = 'bg-white border-2 border-gray-300 rounded-lg p-6 hover:border-blue-500 hover:bg-blue-50 transition text-center';
        lOption.innerHTML = `
            <div class="text-3xl font-bold text-gray-800 mb-2">${product.price_l.toFixed(0)}</div>
            <div class="text-lg font-semibold text-gray-600">L</div>
        `;
        lOption.onclick = () => {
            addToOrder(product.id, 'L', product.price_l);
            closeSizeModal();
        };
        sizeOptions.appendChild(lOption);
    }

    // If no sizes available, close modal and show error
    if (sizeOptions.children.length === 0) {
        closeSizeModal();
        if (window.notificationManager) {
            window.notificationManager.warning('لا توجد أحجام متاحة لهذا المنتج');
        }
        return;
    }

    modal.classList.remove('hidden');
}

// Close size modal
function closeSizeModal() {
    document.getElementById('sizeModal').classList.add('hidden');
}

// Add product to current order
function addToOrder(productId, size = null, price = null) {
    console.log('Adding to order:', { productId, size, price });
    const product = products.find(p => p.id === productId);
    if (!product) {
        console.error('Product not found:', productId);
        return;
    }

    // Use provided price or product price
    const itemPrice = price !== null ? price : product.price;
    // Don't add size to product_name - we'll display it separately
    const itemName = product.name;

    // Find existing item with same product and size
    const existingItem = currentOrder.items.find(item => {
        if (size) {
            return item.product_id === productId && item.size === size;
        } else {
            return item.product_id === productId && !item.size;
        }
    });

    if (existingItem) {
        existingItem.quantity += 1;
        existingItem.total = existingItem.price * existingItem.quantity;
    } else {
        currentOrder.items.push({
            product_id: product.id,
            product_name: itemName,
            size: size,
            quantity: 1,
            price: itemPrice,
            total: itemPrice,
            submitted_quantity: 0 // Track submitted quantity
        });
    }
    console.log('Current order items:', currentOrder.items);
    updateOrderDisplay();
    updatePhoneButtonState();
}

// Remove from order - decrease quantity or remove if quantity allows
function removeFromOrder(itemIndex) {
    if (itemIndex < 0 || itemIndex >= currentOrder.items.length) return;
    const item = currentOrder.items[itemIndex];
    if (!item) return;

    // Check if we can decrease quantity
    if (item.quantity > item.submitted_quantity) {
        // Decrease by 1
        item.quantity -= 1;
        item.total = item.price * item.quantity;

        // If quantity equals submitted, and submitted is 0, remove item completely
        if (item.quantity === 0) {
            currentOrder.items.splice(itemIndex, 1);
        }
    } else {
        if (window.notificationManager) {
            window.notificationManager.warning('لا يمكن حذف كميات تم طلبها للمطبخ بالفعل');
        }
        return;
    }

    updateOrderDisplay();
    updatePhoneButtonState();
}

// Update order display - matching image exactly with quantity tracking
// Update phone button state based on current order
function updatePhoneButtonState() {
    const phoneBtn = document.getElementById('phoneBtn');
    if (!phoneBtn) return;

    // Enable phone button only if a table is open (tableNumber > 0)
    if (currentOrder && currentOrder.tableNumber && currentOrder.tableNumber > 0) {
        phoneBtn.disabled = false;
        phoneBtn.title = `إشعار الطاولة ${currentOrder.tableNumber} - الطلب جاهز`;
    } else {
        phoneBtn.disabled = true;
        phoneBtn.title = 'يجب فتح طاولة أولاً';
    }
}

// Call tablet to notify that order is ready
async function callTablet() {
    if (!currentOrder || !currentOrder.tableNumber || currentOrder.tableNumber <= 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('يجب فتح طاولة أولاً');
        }
        return;
    }

    try {
        // Call backend endpoint to broadcast notification
        const response = await fetch(`/api/tables/${currentOrder.tableNumber}/call-waiter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const result = await response.json();
            console.log('Waiter called successfully:', result);

            if (window.notificationManager) {
                window.notificationManager.success(`تم استدعاء الويتر للطاولة ${currentOrder.tableNumber}`);
            }
        } else {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to call waiter' }));
            throw new Error(errorData.detail || 'Failed to call waiter');
        }
    } catch (error) {
        console.error('Error calling waiter:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في استدعاء الويتر: ' + (error.message || 'خطأ غير معروف'));
        }
    }
}

// Update order display (optimized with DocumentFragment)
function updateOrderDisplay() {
    requestAnimationFrame(() => {
        const container = document.getElementById('orderItems');
        if (!container) return;

        const subtotal = currentOrder.items.reduce((sum, item) => sum + item.total, 0);

        // Apply discount if exists
        const discount = currentOrder.discount || 0;
        const discountType = currentOrder.discountType || 'percent';
        let discountAmount = 0;
        if (discountType === 'percent') {
            discountAmount = subtotal * (discount / 100);
        } else {
            discountAmount = discount;
        }
        if (discountAmount > subtotal) {
            discountAmount = subtotal;
        }
        const totalAmount = subtotal - discountAmount;

        const totalAmountEl = document.getElementById('totalAmount');
        if (totalAmountEl) {
            totalAmountEl.textContent = totalAmount.toFixed(2);
        }

        if (currentOrder.items.length === 0) {
            container.innerHTML = '<div class="text-center text-gray-400 py-20 text-base">لا توجد أصناف</div>';
            return;
        }

        // Use DocumentFragment for better performance
        const fragment = document.createDocumentFragment();
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = currentOrder.items.map((item, index) => {
            const isLast = index === currentOrder.items.length - 1;
            const hasUnsubmitted = item.quantity > item.submitted_quantity;
            const newQuantity = item.quantity - item.submitted_quantity;

            return `
                <div class="grid grid-cols-12 gap-2 items-center px-4 py-3 border-b border-gray-200 hover:bg-teal-50 transition ${isLast ? 'bg-gradient-to-r from-teal-100 to-teal-50' : 'bg-white'}">
                    <div class="col-span-1 flex items-center justify-center">
                        ${hasUnsubmitted ?
                    `<button onclick="removeFromOrder(${index})" class="text-gray-400 hover:text-red-500 transition">
                                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                                </svg>
                            </button>` :
                    '<svg class="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg>'
                }
                    </div>
                    <div class="col-span-5 text-base font-bold text-gray-800 text-right truncate">
                        ${item.product_name}${item.size ? ` <span class="text-sm text-gray-800 font-bold">(${item.size})</span>` : ''}
                        ${item.additions ? `<div class="text-sm text-blue-700 font-bold mt-1"> + ${item.additions}</div>` : ''}
                        ${item.notes ? ` <div class="text-xs text-gray-500 italic">[${item.notes}]</div>` : ''}
                        ${item.submitted_quantity > 0 && hasUnsubmitted ?
                    `<span class="text-xs text-orange-600 font-bold"> (+${newQuantity} جديد)</span>` : ''
                }
                    </div>
                    <div class="col-span-3 text-center text-base font-bold text-gray-700">${item.quantity}</div>
                    <div class="col-span-3 text-left text-base font-bold text-gray-800">${item.total.toFixed(2)}</div>
                </div>
            `;
        }).join('');

        fragment.appendChild(tempDiv);
        container.innerHTML = '';
        container.appendChild(fragment.firstElementChild || fragment);
    });
}

// Create order in database
async function createOrder() {
    // Check if shift is open
    if (!await checkShiftBeforeOrder()) {
        return null;
    }

    if (currentOrder.items.length === 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء إضافة منتجات للطلب');
        }
        return null;
    }

    try {
        const requestBody = {
            table_number: currentOrder.tableNumber || 0,
            items: currentOrder.items.map(item => ({
                product_id: item.product_id,
                quantity: item.quantity,
                size: item.size || null,
                additions: item.additions || null,
                notes: item.notes || null
            }))
        };

        const response = await fetch('/api/orders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
            console.error('Order creation failed:', response.status, errorData);
            throw new Error(errorData.detail || 'Failed to create order');
        }

        const order = await response.json();
        currentOrder.orderNumber = order.order_number;
        document.getElementById('orderNumberDisplay').textContent = order.order_number;
        return order;
    } catch (error) {
        console.error('Error creating order:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في إنشاء الطلب: ' + (error.message || 'خطأ غير معروف'));
        }
        return null;
    }
}

// Complete order - prints full invoice with prices and ends order
async function completeOrder() {
    if (currentOrder.items.length === 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء إضافة منتجات للطلب');
        }
        return;
    }

    // Create or update order - ensure all current items are saved
    let order = null;
    if (!currentOrder.orderNumber) {
        // Create new order with all items
        order = await createOrder();
        if (!order) return;
    } else {
        // Order exists - get it and update with new items if any
        try {
            const response = await fetch(`/api/orders?status=pending`);
            const orders = await response.json();
            order = orders.find(o => o.order_number === currentOrder.orderNumber);

            if (order) {
                // Find items that are new (not in saved order) or have increased quantity
                const savedItems = order.items || [];
                const itemsToAdd = [];

                currentOrder.items.forEach(currentItem => {
                    const savedItem = savedItems.find(si =>
                        si.product_id === currentItem.product_id &&
                        (si.size || null) === (currentItem.size || null)
                    );

                    if (!savedItem) {
                        // New item - add full quantity
                        itemsToAdd.push({
                            product_id: currentItem.product_id,
                            quantity: currentItem.quantity,
                            size: currentItem.size || null
                        });
                    } else if (currentItem.quantity > savedItem.quantity) {
                        // Existing item with increased quantity - add difference
                        itemsToAdd.push({
                            product_id: currentItem.product_id,
                            quantity: currentItem.quantity - savedItem.quantity,
                            size: currentItem.size || null
                        });
                    }
                });

                // Update order with new items
                if (itemsToAdd.length > 0) {
                    const updateResponse = await fetch(`/api/orders/${order.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            table_number: currentOrder.tableNumber,
                            items: itemsToAdd
                        })
                    });

                    if (updateResponse.ok) {
                        order = await updateResponse.json();
                        // Reload order to get updated total
                        const reloadResponse = await fetch(`/api/orders/${order.id}`);
                        if (reloadResponse.ok) {
                            order = await reloadResponse.json();
                        }
                    } else {
                        const errorData = await updateResponse.json().catch(() => ({ detail: 'Unknown error' }));
                        console.error('Failed to update order:', errorData);
                        if (window.notificationManager) {
                            window.notificationManager.error('فشل في تحديث الطلب: ' + (errorData.detail || 'خطأ غير معروف'));
                        }
                    }
                } else {
                    // Reload order to get current state
                    const reloadResponse = await fetch(`/api/orders/${order.id}`);
                    if (reloadResponse.ok) {
                        order = await reloadResponse.json();
                    }
                }
            } else {
                // Order not found in pending orders, try to get it by ID
                try {
                    const orderByIdResponse = await fetch(`/api/orders/${currentOrder.orderNumber}`);
                    if (orderByIdResponse.ok) {
                        order = await orderByIdResponse.json();
                    }
                } catch (e) {
                    console.error('Error fetching order by ID:', e);
                }
            }
        } catch (error) {
            console.error('Error fetching/updating order:', error);
        }
    }

    if (!order) {
        // Updated Logic: DO NOT create a new order if we have an orderNumber but failed to update it.
        // This prevents phantom orders if the network request failed but actually succeeded on server,
        // or if there's a sync issue.
        if (currentOrder.orderNumber) {
            console.error('Failed to update existing order ' + currentOrder.orderNumber);
            if (window.notificationManager) {
                window.notificationManager.error('فشل في تحديث الطلب الحالي. يرجى المحاولة مرة أخرى.');
            }
            return;
        }

        // Only create new order if we really don't have one
        order = await createOrder();
        if (!order) return;
    }

    // Check if there are unsubmitted quantities - if yes, send to kitchen first
    const itemsWithNewQuantity = currentOrder.items.filter(item =>
        item.quantity > item.submitted_quantity
    );

    if (itemsWithNewQuantity.length > 0) {
        // Send unsubmitted items to kitchen first
        try {
            await fetch(`/api/print/kitchen/${order.id}`, { method: 'POST' });
            // Mark all quantities as submitted since we're completing the order
            currentOrder.items.forEach(item => {
                item.submitted_quantity = item.quantity;
            });
        } catch (error) {
            console.warn('Kitchen printer not available:', error);
        }
    }

    // Print customer invoice - REMOVED to prevent double printing (Check Order + Tax Invoice)
    // Printing is now handled automatically by the backend complete endpoint after payment
    /*
    try {
        await fetch(`/api/print/invoice/${order.id}`, { method: 'POST' });
 
        // Open cash drawer automatically - REMOVED to prevent double opening
        // openCashDrawer();
 
    } catch (error) {
        console.warn('Invoice printer not available:', error);
    }
    */

    // Store order for payment modal
    window.pendingOrderForPayment = order;

    // Calculate total from current order items if order.total_amount is not available
    // Apply discount if exists
    let subtotal = currentOrder.items.reduce((sum, item) => sum + item.total, 0);
    const discount = currentOrder.discount || 0;
    const discountType = currentOrder.discountType || 'percent';
    let discountAmount = 0;
    if (discountType === 'percent') {
        discountAmount = subtotal * (discount / 100);
    } else {
        discountAmount = discount; // Fixed amount in EGP
    }
    // Ensure discount doesn't exceed subtotal
    if (discountAmount > subtotal) {
        discountAmount = subtotal;
    }
    let totalAmount = subtotal - discountAmount;

    if (!totalAmount || totalAmount === 0) {
        totalAmount = order.total_amount || subtotal;
    }

    // Show payment modal instead of completing directly
    console.log('=== COMPLETE ORDER - About to show payment modal ===');
    console.log('Order:', order);
    console.log('Total amount:', totalAmount);
    console.log('Current order items:', currentOrder.items);

    try {
        showPaymentModal(totalAmount);
    } catch (error) {
        console.error('Error showing payment modal:', error);
        // Fallback: complete order directly if modal fails
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في عرض نافذة الدفع: ' + error.message);
        }
        // Complete order directly as fallback
        await completeOrderDirectly(order);
    }
}

// Complete order directly without payment modal (fallback)
async function completeOrderDirectly(order) {
    try {
        const completeResponse = await fetch(`/api/orders/${order.id}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                payment_method: 'cash',
                paid_amount: order.total_amount,
                tip: 0
            })
        });

        if (completeResponse.ok) {
            const orderData = await completeResponse.json();

            if (window.notificationManager) {
                window.notificationManager.success('تم انهاء الطلب بنجاح');
            }

            // Check for Browser Print Preview
            if (orderData.print_preview) {
                printImageInBrowser(orderData.print_preview);
            }

            resetOrder();
            updatePendingInvoicesCount();
        }
    } catch (error) {
        console.error('Error completing order:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في انهاء الطلب');
        }
    }
}

// Show payment modal
function showPaymentModal(totalAmount) {
    console.log('=== SHOW PAYMENT MODAL ===');
    console.log('Total amount:', totalAmount);

    // Force show modal - remove any hidden classes
    const modal = document.getElementById('paymentModal');
    if (!modal) {
        console.error('Payment modal not found in DOM!');
        console.error('Available elements:', document.querySelectorAll('[id*="payment"]'));
        if (window.notificationManager) {
            window.notificationManager.error('خطأ: نافذة الدفع غير موجودة. يرجى إعادة تحميل الصفحة.');
        } else {
            alert('خطأ: نافذة الدفع غير موجودة. يرجى إعادة تحميل الصفحة.');
        }
        throw new Error('Payment modal not found');
    }

    console.log('Modal found, showing...');

    // Remove hidden class and ensure visibility
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    modal.style.zIndex = '99999';
    modal.style.position = 'fixed';
    modal.style.top = '0';
    modal.style.left = '0';
    modal.style.width = '100%';
    modal.style.height = '100%';
    modal.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';

    const netAmountEl = document.getElementById('paymentNetAmount');
    const paidInput = document.getElementById('paymentPaid');
    const remainingEl = document.getElementById('paymentRemaining');
    const tipInput = document.getElementById('paymentTip');

    if (!netAmountEl || !paidInput || !remainingEl || !tipInput) {
        console.error('Payment modal elements not found!', { netAmountEl, paidInput, remainingEl, tipInput });
        alert('خطأ: عناصر نافذة الدفع غير موجودة. يرجى إعادة تحميل الصفحة.');
        return;
    }

    // Set net amount
    const total = parseFloat(totalAmount) || 0;
    netAmountEl.textContent = total.toFixed(2);

    // Reset payment method to cash (default)
    selectPaymentMethod('cash');

    // Reset inputs
    paidInput.value = total.toFixed(2);
    tipInput.value = '0';

    // Update remaining
    updatePaymentRemaining();

    console.log('Payment modal shown successfully');

    // Focus on paid input
    setTimeout(() => {
        paidInput.focus();
        paidInput.select();
    }, 200);
}

// Close payment modal
function closePaymentModal() {
    const modal = document.getElementById('paymentModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
    window.pendingOrderForPayment = null;
}

// Select payment method
function selectPaymentMethod(method) {
    // Reset all buttons
    document.querySelectorAll('.payment-method-btn').forEach(btn => {
        btn.className = 'payment-method-btn px-4 py-3 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-base shadow-sm hover:bg-gray-50 hover:border-gray-400 transition';
    });

    // Highlight selected button
    const selectedBtn = document.querySelector(`[data-method="${method}"]`);
    if (selectedBtn) {
        selectedBtn.className = 'payment-method-btn px-4 py-3 bg-teal-600 text-white rounded-lg font-bold text-base shadow-md border-2 border-teal-700 hover:bg-teal-700 transition';
    }

    window.selectedPaymentMethod = method;

    // Show/hide payment fields based on method
    const singlePaymentField = document.getElementById('singlePaymentField');
    const mixedPaymentFields = document.getElementById('mixedPaymentFields');

    if (method === 'mixed') {
        // Show mixed payment fields
        if (singlePaymentField) singlePaymentField.classList.add('hidden');
        if (mixedPaymentFields) mixedPaymentFields.classList.remove('hidden');

        // Reset mixed payment inputs
        const cashAmount = document.getElementById('paymentCashAmount');
        const cardAmount = document.getElementById('paymentCardAmount');
        if (cashAmount) cashAmount.value = '0';
        if (cardAmount) cardAmount.value = '0';

        // Add event listeners for mixed payment
        if (cashAmount) {
            cashAmount.removeEventListener('input', updatePaymentRemaining);
            cashAmount.addEventListener('input', updatePaymentRemaining);
        }
        if (cardAmount) {
            cardAmount.removeEventListener('input', updatePaymentRemaining);
            cardAmount.addEventListener('input', updatePaymentRemaining);
        }
    } else {
        // Show single payment field
        if (singlePaymentField) singlePaymentField.classList.remove('hidden');
        if (mixedPaymentFields) mixedPaymentFields.classList.add('hidden');
    }

    // Update remaining amount
    updatePaymentRemaining();
}

// Update remaining amount
function updatePaymentRemaining() {
    const netAmount = parseFloat(document.getElementById('paymentNetAmount').textContent) || 0;
    const paymentMethod = window.selectedPaymentMethod || 'cash';

    let paid = 0;

    if (paymentMethod === 'mixed') {
        // Calculate total from cash + card
        const cashAmount = parseFloat(document.getElementById('paymentCashAmount').value) || 0;
        const cardAmount = parseFloat(document.getElementById('paymentCardAmount').value) || 0;
        paid = cashAmount + cardAmount;
    } else {
        // Single payment method
        paid = parseFloat(document.getElementById('paymentPaid').value) || 0;
    }

    const remaining = netAmount - paid;
    const remainingEl = document.getElementById('paymentRemaining');

    remainingEl.textContent = remaining.toFixed(2);

    // Change color based on remaining
    if (remaining > 0) {
        remainingEl.className = 'text-xl font-bold text-red-600';

        // Highlight input fields if insufficient
        if (paymentMethod === 'mixed') {
            const cashInput = document.getElementById('paymentCashAmount');
            const cardInput = document.getElementById('paymentCardAmount');
            if (cashInput) {
                cashInput.classList.add('border-red-500');
                cashInput.classList.remove('border-gray-300');
            }
            if (cardInput) {
                cardInput.classList.add('border-red-500');
                cardInput.classList.remove('border-gray-300');
            }
        } else {
            const paidInput = document.getElementById('paymentPaid');
            if (paidInput) {
                paidInput.classList.add('border-red-500');
                paidInput.classList.remove('border-gray-300');
            }
        }
    } else if (remaining < 0) {
        remainingEl.className = 'text-xl font-bold text-green-600';

        // Reset input borders
        if (paymentMethod === 'mixed') {
            const cashInput = document.getElementById('paymentCashAmount');
            const cardInput = document.getElementById('paymentCardAmount');
            if (cashInput) {
                cashInput.classList.remove('border-red-500');
                cashInput.classList.add('border-gray-300');
            }
            if (cardInput) {
                cardInput.classList.remove('border-red-500');
                cardInput.classList.add('border-gray-300');
            }
        } else {
            const paidInput = document.getElementById('paymentPaid');
            if (paidInput) {
                paidInput.classList.remove('border-red-500');
                paidInput.classList.add('border-gray-300');
            }
        }
    } else {
        remainingEl.className = 'text-xl font-bold text-gray-800';

        // Reset input borders
        if (paymentMethod === 'mixed') {
            const cashInput = document.getElementById('paymentCashAmount');
            const cardInput = document.getElementById('paymentCardAmount');
            if (cashInput) {
                cashInput.classList.remove('border-red-500');
                cashInput.classList.add('border-gray-300');
            }
            if (cardInput) {
                cardInput.classList.remove('border-red-500');
                cardInput.classList.add('border-gray-300');
            }
        } else {
            const paidInput = document.getElementById('paymentPaid');
            if (paidInput) {
                paidInput.classList.remove('border-red-500');
                paidInput.classList.add('border-gray-300');
            }
        }
    }
}

// Complete order with payment
async function completeOrderWithPayment() {
    if (!window.pendingOrderForPayment) {
        if (window.notificationManager) {
            window.notificationManager.error('لا يوجد طلب للإنهاء');
        }
        return;
    }

    const order = window.pendingOrderForPayment;
    const paymentMethod = window.selectedPaymentMethod || 'cash';
    const netAmount = parseFloat(document.getElementById('paymentNetAmount').textContent) || 0;
    const tip = parseFloat(document.getElementById('paymentTip').value) || 0;

    let paid = 0;
    let cashAmount = 0;
    let cardAmount = 0;

    if (paymentMethod === 'mixed') {
        // Get amounts from mixed payment fields
        cashAmount = parseFloat(document.getElementById('paymentCashAmount').value) || 0;
        cardAmount = parseFloat(document.getElementById('paymentCardAmount').value) || 0;
        paid = cashAmount + cardAmount;
    } else {
        // Get amount from single payment field
        paid = parseFloat(document.getElementById('paymentPaid').value) || 0;
    }

    const remaining = netAmount - paid;

    // Validate payment - لا يمكن الدفع بأقل من صافي المبلغ
    if (remaining > 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('المبلغ المدفوع غير كافي. يجب دفع المبلغ كاملاً: ' + netAmount.toFixed(2) + ' ج.م');
        }
        // Focus on appropriate input
        if (paymentMethod === 'mixed') {
            const cashInput = document.getElementById('paymentCashAmount');
            if (cashInput) {
                cashInput.focus();
                cashInput.select();
            }
        } else {
            const paidInput = document.getElementById('paymentPaid');
            if (paidInput) {
                paidInput.focus();
                paidInput.select();
            }
        }
        return;
    }

    // Close modal
    closePaymentModal();

    // AUTO-SAVE: Ensure any unsubmitted items are saved before completing
    // This fixes the "Ghost Items" / Missing Items issue where items added but not "Ordered" (Talab) might be ignored or have 0 quantity issues if not synced.
    // Calculate items to add (using logic from submitOrder)
    const itemsWithNewQuantity = currentOrder.items.filter(item =>
        item.quantity > (item.submitted_quantity || 0)
    );

    if (itemsWithNewQuantity.length > 0) {
        console.log('Auto-saving unsubmitted items before completion:', itemsWithNewQuantity);
        const itemsToAdd = itemsWithNewQuantity.map(item => {
            const newQty = item.quantity - (item.submitted_quantity || 0);
            return {
                product_name: item.product_name,
                product_id: item.product_id,
                quantity: newQty, // Delta
                price: item.price,
                total: item.price * newQty,
                size: item.size || null,
                additions: item.additions || null,
                notes: item.notes || null
            };
        });

        try {
            if (order.id) {
                await fetch(`/api/orders/${order.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        table_number: currentOrder.tableNumber,
                        items: itemsToAdd
                    })
                });
            } else {
                // Should not happen for existing order, but if so, create it?
                // No, payment logic assumes order.id exists.
            }
        } catch (e) {
            console.error('Auto-save failed:', e);
            // Verify if we should stop?
        }
    }

    // Try to print full invoice, but don't block if it fails
    // Printing is now handled automatically by the backend complete endpoint
    // (Drawer -> Slip -> Invoice -> Kitchen)

    // Complete order with payment info
    try {
        // For mixed payment, store both amounts in payment_method
        let finalPaymentMethod = paymentMethod;
        if (paymentMethod === 'mixed') {
            finalPaymentMethod = `mixed_cash_${cashAmount}_card_${cardAmount}`;
        }

        const completeResponse = await fetch(`/api/orders/${order.id}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                payment_method: finalPaymentMethod,
                paid_amount: paid,
                tip: tip
            })
        });

        if (completeResponse.ok) {
            const orderData = await completeResponse.json();

            if (window.notificationManager) {
                window.notificationManager.success('تم انهاء الطلب وطباعة الفاتورة الكاملة');
            }

            // Check for Browser Print Preview
            if (orderData.print_preview) {
                printImageInBrowser(orderData.print_preview);
            }

            // If order was for a table, close the table and update tables
            if (order.table_number > 0) {
                updateTablesCount();
                // Refresh tables modal if open
                const tablesModal = document.getElementById('tablesModal');
                if (tablesModal && !tablesModal.classList.contains('hidden')) {
                    await loadTables();
                }
            }

            // Reset order completely
            currentOrder = { items: [], orderNumber: null, tableNumber: 0, orderType: 'takeaway', submittedItems: [], discount: 0, discountType: 'percent', numberOfPeople: 1 };
            document.getElementById('orderNumberDisplay').textContent = '';
            const tableNumberDisplay = document.getElementById('tableNumberDisplay');
            if (tableNumberDisplay) {
                tableNumberDisplay.textContent = '-';
            }

            // Reset order button
            const orderBtn = document.getElementById('orderBtn');
            orderBtn.innerHTML = 'طلب';
            orderBtn.className = 'flex-1 px-5 py-3.5 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-base shadow-sm hover:bg-gray-50 hover:border-gray-400 transition';
            orderBtn.disabled = false;

            updateOrderDisplay();
            updatePhoneButtonState();
            updatePendingInvoicesCount();
        } else {
            const errorData = await completeResponse.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(errorData.detail || 'Failed to complete order');
        }
    } catch (error) {
        console.error('Error completing order:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في انهاء الطلب: ' + (error.message || 'خطأ غير معروف'));
        }
    }
}

// Exit order function - clears order without saving (only if not already saved as pending)
async function exitOrder() {
    try {
        // If order was already saved (has orderNumber), just reset
        // If order was NOT saved (no orderNumber), clear everything without saving
        if (currentOrder.orderNumber) {
            // Order already saved, just reset
            resetOrder();
            updatePendingInvoicesCount();
        } else {
            // Order not saved yet, just clear everything (don't save)
            resetOrder();
        }
    } catch (error) {
        console.error('Error in exitOrder:', error);
        // Reset anyway even if there's an error
        resetOrder();
    }
}

// Reset order
function resetOrder() {
    currentOrder = { items: [], orderNumber: null, tableNumber: 0, orderType: 'takeaway', submittedItems: [], discount: 0, discountType: 'percent', numberOfPeople: 1 };
    document.getElementById('orderNumberDisplay').textContent = '';
    const tableNumberDisplay = document.getElementById('tableNumberDisplay');
    if (tableNumberDisplay) {
        tableNumberDisplay.textContent = '-';
    }
    updateOrderDisplay();
    updatePhoneButtonState();

    // Reset order button
    const orderBtn = document.getElementById('orderBtn');
    if (orderBtn) {
        orderBtn.innerHTML = 'طلب';
        orderBtn.className = 'flex-1 px-5 py-3.5 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-base shadow-sm hover:bg-gray-50 hover:border-gray-400 transition';
        orderBtn.disabled = false;
    }
}

// Show pending invoices modal
async function showPendingInvoices() {
    const modal = document.getElementById('pendingInvoicesModal');
    const list = document.getElementById('pendingInvoicesList');

    if (!modal) {
        console.error('Pending invoices modal not found');
        return;
    }

    modal.classList.remove('hidden');
    list.innerHTML = '<div class="text-center py-8 text-gray-400">جاري التحميل...</div>';

    try {
        // Get pending orders (orders that are not completed)
        const response = await fetch('/api/orders?status=pending');

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            console.error('Failed to load pending invoices:', response.status, errorText);
            list.innerHTML = '<div class="text-center py-8 text-red-400">خطأ في تحميل الفواتير المعلقة</div>';
            if (window.notificationManager) {
                window.notificationManager.error('خطأ في تحميل الفواتير المعلقة');
            }
            return;
        }

        const orders = await response.json().catch(error => {
            console.error('Error parsing orders JSON:', error);
            throw new Error('Invalid response format');
        });

        if (!Array.isArray(orders)) {
            console.error('Orders is not an array:', orders);
            list.innerHTML = '<div class="text-center py-8 text-red-400">خطأ في تحميل الفواتير المعلقة</div>';
            if (window.notificationManager) {
                window.notificationManager.error('خطأ في تحميل الفواتير المعلقة');
            }
            return;
        }

        // Filter out table orders (table_number > 0) - tables have their own management system
        const nonTableOrders = orders.filter(order => {
            const tableNum = order.table_number || 0;
            return !tableNum || tableNum === 0;
        });

        if (nonTableOrders.length === 0) {
            list.innerHTML = '<div class="text-center py-8 text-gray-400">لا توجد فواتير معلقة</div>';
            return;
        }

        list.innerHTML = nonTableOrders.map(order => {
            try {
                const date = new Date(order.created_at).toLocaleDateString('ar-EG');
                const items = order.items || [];
                const itemsList = items.map(item => {
                    const productName = item.product_name || 'منتج غير معروف';
                    const size = item.size ? ` (${item.size})` : '';
                    const quantity = item.quantity || 0;
                    const total = item.total || 0;
                    return `${productName}${size} × ${quantity} = ${parseFloat(total).toFixed(2)}`;
                }).join('<br>');

                const orderNumber = order.order_number || 'N/A';
                const totalAmount = order.total_amount || 0;
                const tableNumber = order.table_number || 0;

                return `
                    <div class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition mb-3">
                        <div class="flex justify-between items-start mb-3">
                            <div>
                                <div class="font-bold text-lg text-gray-800">طلب #${orderNumber}</div>
                                <div class="text-sm text-gray-600">طاولة: ${tableNumber > 0 ? tableNumber : 'تيك أواي'}</div>
                                <div class="text-xs text-gray-500 mt-1">${date}</div>
                            </div>
                            <div class="text-left">
                                <div class="font-bold text-xl text-blue-600">${parseFloat(totalAmount).toFixed(2)} ج.م</div>
                                <button onclick="loadOrder(${order.id})" class="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-semibold">
                                    فتح
                                </button>
                            </div>
                        </div>
                        <div class="border-t border-gray-200 pt-3 mt-3">
                            <div class="text-sm text-gray-700 mb-2 font-semibold">الأصناف:</div>
                            <div class="text-sm text-gray-600">${itemsList || 'لا توجد أصناف'}</div>
                        </div>
                    </div>
                `;
            } catch (itemError) {
                console.error('Error rendering order item:', itemError, order);
                return `<div class="border border-red-200 rounded-lg p-4 mb-3 text-red-600">خطأ في عرض الطلب #${order.id || 'N/A'}</div>`;
            }
        }).join('');

        // Update count after loading
        updatePendingInvoicesCount();
    } catch (error) {
        console.error('Error loading pending invoices:', error);
        list.innerHTML = '<div class="text-center py-8 text-red-400">خطأ في تحميل الفواتير المعلقة: ' + (error.message || 'خطأ غير معروف') + '</div>';
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في تحميل الفواتير المعلقة: ' + (error.message || 'خطأ غير معروف'));
        }
    }
}

// Close pending invoices modal
function closePendingInvoicesModal() {
    const modal = document.getElementById('pendingInvoicesModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Load order into current order
async function loadOrder(orderId) {
    try {
        if (!orderId) {
            throw new Error('Order ID is required');
        }

        const response = await fetch(`/api/orders/${orderId}`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            console.error('Failed to load order:', response.status, errorText);
            throw new Error(`Failed to load order: ${response.status} ${errorText}`);
        }

        const order = await response.json().catch(error => {
            console.error('Error parsing order JSON:', error);
            throw new Error('Invalid response format');
        });

        if (!order || !order.id) {
            console.error('Invalid order data:', order);
            throw new Error('Invalid order data received');
        }

        // Load order into current order
        // For pending orders, all existing items are considered submitted (already ordered to kitchen)
        // New items added later will have submitted_quantity = 0
        currentOrder = {
            items: (order.items || []).map(item => ({
                product_id: item.product_id,
                product_name: item.product_name || 'منتج غير معروف',
                quantity: item.quantity || 0,
                price: item.price || 0,
                total: item.total || 0,
                size: item.size || null,
                additions: item.additions || null,
                notes: item.notes || null,
                submitted_quantity: item.quantity || 0 // All existing items in pending order are already submitted
            })),
            orderNumber: order.order_number,
            tableNumber: order.table_number || 0,
            orderType: (order.table_number || 0) === 0 ? 'takeaway' : 'dine-in',
            submittedItems: [],
            discount: order.discount_amount || 0,
            discountType: 'percent', // Default to percent
            numberOfPeople: 1
        };

        console.log('Loaded order:', currentOrder);

        const orderNumberDisplay = document.getElementById('orderNumberDisplay');
        if (orderNumberDisplay) {
            orderNumberDisplay.textContent = order.order_number || '';
        }

        const tableNumberDisplay = document.getElementById('tableNumberDisplay');
        if (tableNumberDisplay) {
            tableNumberDisplay.textContent = (order.table_number && order.table_number > 0) ? order.table_number : '-';
        }

        updateOrderDisplay();
        updatePhoneButtonState();

        closePendingInvoicesModal();
        updatePendingInvoicesCount();

        // No notification when loading order
    } catch (error) {
        console.error('Error loading order:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في تحميل الطلب: ' + (error.message || 'خطأ غير معروف'));
        } else {
            alert('خطأ في تحميل الطلب: ' + (error.message || 'خطأ غير معروف'));
        }
    }
}

// Update pending invoices count badge
async function updatePendingInvoicesCount() {
    try {
        const response = await fetch('/api/orders?status=pending');

        if (!response.ok) {
            console.error('Failed to update pending invoices count:', response.status);
            return;
        }

        const orders = await response.json().catch(error => {
            console.error('Error parsing orders JSON in updatePendingInvoicesCount:', error);
            return [];
        });

        if (!Array.isArray(orders)) {
            console.error('Orders is not an array in updatePendingInvoicesCount:', orders);
            return;
        }

        // Filter out table orders (table_number > 0) - tables have their own management system
        const nonTableOrders = orders.filter(order => {
            const tableNum = order.table_number || 0;
            return !tableNum || tableNum === 0;
        });

        const count = nonTableOrders.length;
        const badge = document.getElementById('pendingInvoicesBadge');

        if (badge) {
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count.toString();
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    } catch (error) {
        console.error('Error updating pending invoices count:', error);
        // Don't show error to user for background updates
    }
}

// Make functions global
window.addToOrder = addToOrder;
window.handleProductClick = handleProductClick;
window.closeSizeModal = closeSizeModal;
window.removeFromOrder = removeFromOrder;
window.exitOrder = exitOrder;
window.showPendingInvoices = showPendingInvoices;
window.closePendingInvoicesModal = closePendingInvoicesModal;
// Show invoice details modal
async function showInvoiceDetailsModal() {
    // Check discount permission
    let hasDiscountPermission = false;
    try {
        const response = await fetch('/api/settings/discount_permission');
        console.log('Discount permission response status:', response.status);
        if (response.ok) {
            const data = await response.json();
            console.log('Discount permission data:', data);
            hasDiscountPermission = data.has_discount_permission === true || data.has_discount_permission === 'true' || data.has_discount_permission === 1 || data.has_discount_permission === '1';
            console.log('Has discount permission:', hasDiscountPermission);
        } else {
            const errorText = await response.text().catch(() => 'Unknown error');
            console.error('Failed to get discount permission:', response.status, errorText);
        }
    } catch (error) {
        console.error('Error checking discount permission:', error);
    }

    // Calculate totals
    const totalQuantity = currentOrder.items.reduce((sum, item) => sum + item.quantity, 0);
    const subtotal = currentOrder.items.reduce((sum, item) => sum + item.total, 0);
    const deliveryFees = 0; // Can be added later
    const discount = currentOrder.discount || 0;

    // Calculate net amount with discount
    const discountAmount = subtotal * (discount / 100);
    const netAmount = subtotal - discountAmount + deliveryFees;

    // Update modal fields
    document.getElementById('invoiceTotalQuantity').textContent = totalQuantity;
    document.getElementById('invoiceSubtotal').textContent = subtotal.toFixed(2);
    document.getElementById('invoiceDeliveryFees').textContent = deliveryFees.toFixed(2);
    document.getElementById('invoiceDiscount').value = discount;
    document.getElementById('invoiceNetAmount').textContent = netAmount.toFixed(2);

    // Show/hide discount field based on permission
    const discountField = document.getElementById('discountField');
    console.log('Discount field element:', discountField);
    if (discountField) {
        if (hasDiscountPermission) {
            console.log('Showing discount field');
            discountField.classList.remove('hidden');
            discountField.style.display = 'block';
        } else {
            console.log('Hiding discount field - no permission');
            discountField.classList.add('hidden');
            discountField.style.display = 'none';
            // Reset discount if no permission
            const discountInput = document.getElementById('invoiceDiscount');
            if (discountInput) {
                discountInput.value = '0';
            }
        }
    } else {
        console.error('Discount field element not found!');
    }

    // Show modal
    const modal = document.getElementById('invoiceDetailsModal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
        modal.style.zIndex = '99999';
    }
}

// Close invoice details modal
function closeInvoiceDetailsModal() {
    const modal = document.getElementById('invoiceDetailsModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}

// Update invoice net amount when discount or number of people changes
function updateInvoiceNetAmount() {
    const subtotal = currentOrder.items.reduce((sum, item) => sum + item.total, 0);
    const discount = parseFloat(document.getElementById('invoiceDiscount')?.value || 0);
    const deliveryFees = 0;

    // Calculate discount amount based on type
    let discountAmount = 0;
    if (currentOrder.discountType === 'percent') {
        discountAmount = subtotal * (discount / 100);
    } else {
        discountAmount = discount; // Fixed amount in EGP
    }

    // Ensure discount doesn't exceed subtotal
    if (discountAmount > subtotal) {
        discountAmount = subtotal;
    }

    const netAmount = subtotal - discountAmount + deliveryFees;

    document.getElementById('invoiceNetAmount').textContent = netAmount.toFixed(2);
}

// Save invoice details
async function saveInvoiceDetails() {
    const discount = parseFloat(document.getElementById('invoiceDiscount')?.value || 0);

    // Store in currentOrder for later use
    currentOrder.discount = discount;
    // discountType is already set by the button click handlers

    // Recalculate totals with discount
    const subtotal = currentOrder.items.reduce((sum, item) => sum + item.total, 0);

    // Calculate discount amount based on type
    let discountAmount = 0;
    if (currentOrder.discountType === 'percent') {
        discountAmount = subtotal * (discount / 100);
    } else {
        discountAmount = discount; // Fixed amount in EGP
    }

    // Ensure discount doesn't exceed subtotal
    if (discountAmount > subtotal) {
        discountAmount = subtotal;
    }

    const netAmount = subtotal - discountAmount;

    // Update display
    updateOrderDisplay();
    updatePhoneButtonState();
    document.getElementById('totalAmount').textContent = netAmount.toFixed(2);

    // If there's an existing order, update it with the discount
    // Note: The discount will be applied when completing the order
    // For now, we just store it locally

    // Close modal
    closeInvoiceDetailsModal();

    if (window.notificationManager) {
        window.notificationManager.success('تم حفظ بيانات الفاتورة');
    }
}

// Show additions modal
async function showAdditionsModal() {
    if (currentOrder.items.length === 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء إضافة منتجات للطلب أولاً');
        }
        return;
    }

    // Populate product select
    const productSelect = document.getElementById('additionsProductSelect');
    if (productSelect) {
        productSelect.innerHTML = '<option value="">-- اختر منتج --</option>';
        currentOrder.items.forEach((item, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = `${item.product_name}${item.size ? ` (${item.size})` : ''} x${item.quantity}`;
            productSelect.appendChild(option);
        });
    }

    // Load additions options immediately
    await loadAdditionsOptions();

    // Reset all additions (disable until product is selected)
    document.querySelectorAll('.addition-option-btn').forEach(btn => {
        btn.classList.remove('bg-green-500', 'text-white', 'border-green-600');
        btn.classList.add('bg-white', 'border-gray-300', 'text-gray-800');
        btn.disabled = true;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
    });

    // Show modal
    const modal = document.getElementById('additionsModal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
        modal.style.zIndex = '99999';
    }
}

// Close additions modal
function closeAdditionsModal() {
    const modal = document.getElementById('additionsModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }

    // Reset form
    const productSelect = document.getElementById('additionsProductSelect');
    if (productSelect) productSelect.value = '';

    // Reset selected additions
    document.querySelectorAll('#additionsOptions button').forEach(btn => {
        btn.classList.remove('bg-green-500', 'text-white', 'border-green-600');
        btn.classList.add('bg-white', 'border-gray-300', 'text-gray-800');
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
    });
}

// Load additions options
async function loadAdditionsOptions() {
    try {
        const response = await fetch('/api/additions');
        if (response.ok) {
            const additions = await response.json();
            const optionsContainer = document.getElementById('additionsOptions');
            if (optionsContainer) {
                if (additions.length === 0) {
                    optionsContainer.innerHTML = '<div class="col-span-3 text-center text-gray-500 py-8">لا توجد إضافات متاحة</div>';
                    return;
                }

                optionsContainer.innerHTML = additions.map(addition => `
                    <button class="addition-option-btn w-full px-4 py-4 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-base shadow-sm transition text-center" 
                            data-addition-id="${addition.id}" data-addition-name="${addition.name}">
                        <span class="addition-name">${addition.name}</span>
                    </button>
                `).join('');

                // Add click listeners
                document.querySelectorAll('.addition-option-btn').forEach(btn => {
                    btn.addEventListener('click', function () {
                        toggleAddition(this);
                    });
                });
            }
        } else {
            console.error('Failed to load additions:', response.status);
            const optionsContainer = document.getElementById('additionsOptions');
            if (optionsContainer) {
                optionsContainer.innerHTML = '<div class="col-span-3 text-center text-red-500 py-8">خطأ في تحميل الإضافات</div>';
            }
        }
    } catch (error) {
        console.error('Error loading additions:', error);
        const optionsContainer = document.getElementById('additionsOptions');
        if (optionsContainer) {
            optionsContainer.innerHTML = `<div class="col-span-3 text-center text-red-500 py-8">خطأ في تحميل الإضافات: ${error.message}</div>`;
        }
    }
}

// Toggle addition selection
function toggleAddition(button) {
    const isSelected = button.classList.contains('bg-green-500');

    if (isSelected) {
        // Deselect - remove green styling
        button.classList.remove('bg-green-500', 'text-white', 'border-green-600');
        button.classList.add('bg-white', 'border-gray-300', 'text-gray-800');
    } else {
        // Select - add green styling
        button.classList.remove('bg-white', 'border-gray-300', 'text-gray-800');
        button.classList.add('bg-green-500', 'text-white', 'border-green-600');
    }
}

// Load product additions when product is selected
function loadProductAdditions() {
    const productSelect = document.getElementById('additionsProductSelect');

    // Enable/disable buttons based on product selection
    document.querySelectorAll('.addition-option-btn').forEach(btn => {
        if (!productSelect || !productSelect.value) {
            // No product selected - disable all buttons
            btn.disabled = true;
            btn.classList.remove('bg-green-500', 'text-white', 'border-green-600');
            btn.classList.add('bg-white', 'border-gray-300', 'text-gray-800', 'opacity-50', 'cursor-not-allowed');
        } else {
            // Product selected - enable all buttons
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    });

    if (!productSelect || !productSelect.value) {
        return;
    }

    const itemIndex = parseInt(productSelect.value);
    const item = currentOrder.items[itemIndex];
    if (!item) return;

    // Load existing additions for this item
    const existingAdditions = item.additions ? item.additions.split(',').map(a => a.trim()) : [];

    // Update UI to show existing additions
    document.querySelectorAll('.addition-option-btn').forEach(btn => {
        const additionName = btn.getAttribute('data-addition-name');
        const isSelected = existingAdditions.includes(additionName);

        if (isSelected) {
            btn.classList.remove('bg-white', 'border-gray-300', 'text-gray-800');
            btn.classList.add('bg-green-500', 'text-white', 'border-green-600');
        } else {
            btn.classList.remove('bg-green-500', 'text-white', 'border-green-600');
            btn.classList.add('bg-white', 'border-gray-300', 'text-gray-800');
        }
    });
}

// Save additions
function saveAdditions() {
    const productSelect = document.getElementById('additionsProductSelect');
    if (!productSelect || !productSelect.value) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء اختيار منتج');
        }
        return;
    }

    const itemIndex = parseInt(productSelect.value);
    const item = currentOrder.items[itemIndex];
    if (!item) return;

    // Get selected additions (only one of each)
    const selectedAdditions = [];
    document.querySelectorAll('.addition-option-btn.bg-green-500').forEach(btn => {
        const additionName = btn.getAttribute('data-addition-name');
        selectedAdditions.push(additionName);
    });

    // Update item
    item.additions = selectedAdditions.length > 0 ? selectedAdditions.join(', ') : null;

    // Update display
    updateOrderDisplay();
    updatePhoneButtonState();

    // Close modal
    closeAdditionsModal();

    if (window.notificationManager) {
        window.notificationManager.success('تم حفظ الإضافات بنجاح');
    }
}

// Show all categories modal (three dots button)
async function showAllCategoriesModal() {
    const modal = document.getElementById('allCategoriesModal');
    if (!modal) {
        console.error('All categories modal not found');
        return;
    }

    // Load all categories
    try {
        const response = await fetch('/api/categories');
        if (!response.ok) {
            throw new Error('Failed to load categories');
        }

        const categoriesList = await response.json();
        const container = document.getElementById('allCategoriesList');

        if (!container) {
            console.error('All categories list container not found');
            return;
        }

        if (categoriesList.length === 0) {
            container.innerHTML = '<div class="col-span-3 text-center py-8 text-gray-400">لا توجد فئات متاحة</div>';
        } else {
            container.innerHTML = categoriesList.map(category => `
                <button onclick="filterByCategory(${category.id}); closeAllCategoriesModal();" class="bg-gray-50 border-2 border-gray-200 rounded-lg p-4 text-center hover:bg-gray-100 hover:border-gray-300 transition cursor-pointer">
                    <div class="text-lg font-bold text-gray-800">${category.name}</div>
                </button>
            `).join('');
        }

        modal.classList.remove('hidden');
    } catch (error) {
        console.error('Error loading categories:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في تحميل الفئات');
        }
    }
}

// Close all categories modal
function closeAllCategoriesModal() {
    const modal = document.getElementById('allCategoriesModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

window.loadOrder = loadOrder;
window.updatePendingInvoicesCount = updatePendingInvoicesCount;
window.showInvoiceDetailsModal = showInvoiceDetailsModal;
window.closeInvoiceDetailsModal = closeInvoiceDetailsModal;
window.showAdditionsModal = showAdditionsModal;
window.closeAdditionsModal = closeAdditionsModal;
window.showAllCategoriesModal = showAllCategoriesModal;
window.closeAllCategoriesModal = closeAllCategoriesModal;
window.filterByCategory = filterByCategory;
window.checkCategoriesScroll = checkCategoriesScroll;

// ==================== TABLES FUNCTIONS ====================

// Show tables modal
async function showTablesModal() {
    console.log('showTablesModal called');
    const modal = document.getElementById('tablesModal');
    if (modal) {
        console.log('Modal found, showing...');
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
        modal.style.zIndex = '99999';
        await loadTables();

        // Start real-time time updates every 10 seconds
        if (window.tableTimeUpdateInterval) {
            clearInterval(window.tableTimeUpdateInterval);
        }
        window.tableTimeUpdateInterval = setInterval(updateTableTimes, 10000); // Update every 10 seconds
    } else {
        console.error('Tables modal not found!');
        if (window.notificationManager) {
            window.notificationManager.error('خطأ: نافذة الطاولات غير موجودة');
        }
    }
}

// Close tables modal
function closeTablesModal() {
    const modal = document.getElementById('tablesModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';

        // Stop real-time time updates
        if (window.tableTimeUpdateInterval) {
            clearInterval(window.tableTimeUpdateInterval);
            window.tableTimeUpdateInterval = null;
        }
    }
}

// Update table times in real-time (every 10 seconds)
function updateTableTimes() {
    const tablesModal = document.getElementById('tablesModal');
    if (!tablesModal || tablesModal.classList.contains('hidden')) {
        return; // Don't update if modal is closed
    }

    // Reload tables to get fresh time calculations
    loadTables();
}

// Load tables
async function loadTables() {
    try {
        const response = await fetch('/api/tables?status=open');
        if (response.ok) {
            const tables = await response.json();
            renderTables(tables);
            // Update tables count badge
            updateTablesCount();
        } else {
            console.error('Failed to load tables:', response.status);
            if (window.notificationManager) {
                window.notificationManager.error('خطأ في تحميل الطاولات');
            }
        }
    } catch (error) {
        console.error('Error loading tables:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في تحميل الطاولات: ' + (error.message || 'خطأ غير معروف'));
        }
    }
}

// Update tables count badge
async function updateTablesCount() {
    try {
        const response = await fetch('/api/tables?status=open');
        if (response.ok) {
            const tables = await response.json();
            const count = tables.length;
            const badge = document.getElementById('tablesBadge');

            if (badge) {
                if (count > 0) {
                    badge.textContent = count > 99 ? '99+' : count.toString();
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            }
        }
    } catch (error) {
        console.error('Error updating tables count:', error);
    }
}

// Calculate time ago (real-time, 100% accurate)
function calculateTimeAgo(timestamp) {
    if (!timestamp) return 'الآن';

    const now = new Date();
    let past;

    // Handle timestamp format - could be ISO string or other format
    if (typeof timestamp === 'string') {
        // SQLite datetime format: "YYYY-MM-DD HH:MM:SS" (local time, no timezone)
        // JavaScript Date assumes UTC when parsing "YYYY-MM-DD HH:MM:SS" format
        // We need to treat it as local time

        if (timestamp.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)) {
            // SQLite datetime format: "YYYY-MM-DD HH:MM:SS" - treat as local time
            const parts = timestamp.split(' ');
            const datePart = parts[0].split('-');
            const timePart = parts[1].split(':');

            // Create date in local timezone
            past = new Date(
                parseInt(datePart[0]),      // year
                parseInt(datePart[1]) - 1,   // month (0-indexed)
                parseInt(datePart[2]),       // day
                parseInt(timePart[0]),      // hour
                parseInt(timePart[1]),      // minute
                parseInt(timePart[2] || 0)  // second
            );
        } else {
            // Try to parse as ISO string
            past = new Date(timestamp);
        }

        // If still invalid, log warning
        if (isNaN(past.getTime())) {
            console.warn('Failed to parse timestamp:', timestamp);
            return 'الآن';
        }
    } else {
        past = new Date(timestamp);
    }

    // Ensure valid dates
    if (isNaN(now.getTime()) || isNaN(past.getTime())) {
        console.warn('Invalid timestamp:', timestamp, 'now:', now, 'past:', past);
        return 'الآن';
    }

    const diffMs = now.getTime() - past.getTime();

    // If negative (future time) or less than 1 second, show "الآن"
    if (diffMs < 0) {
        console.warn('Future timestamp detected:', timestamp, 'diff:', diffMs, 'now:', now.toISOString(), 'past:', past.toISOString());
        return 'الآن';
    }

    if (diffMs < 1000) {
        return 'الآن';
    }

    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffDays > 0) {
        return `${diffDays} يوم`;
    } else if (diffHours > 0) {
        return `${diffHours} ساعة`;
    } else if (diffMins > 0) {
        return `${diffMins} دقيقة`;
    } else {
        return `${diffSecs} ثانية`;
    }
}

// Render tables grid
function renderTables(tables) {
    const grid = document.getElementById('tablesGrid');
    if (!grid) return;

    if (tables.length === 0) {
        grid.innerHTML = '<div class="col-span-4 text-center text-gray-400 py-12 text-lg">لا توجد طاولات مفتوحة</div>';
        return;
    }

    // Get current time for real-time calculation
    const now = new Date();

    grid.innerHTML = tables.map(table => {
        const hasOrder = table.order && table.order.items && table.order.items.length > 0;
        const totalAmount = hasOrder ? table.order.total_amount : 0;
        const itemsCount = hasOrder ? table.order.items.reduce((sum, item) => sum + item.quantity, 0) : 0;

        // Calculate time since last update (real-time, 100% accurate)
        const timeAgo = calculateTimeAgo(table.updated_at);

        // Calculate first order time (real-time, 100% accurate)
        // Use order created_at for first order time
        let firstOrderTime = '';
        if (hasOrder && table.order.created_at) {
            const now = new Date();
            const orderCreated = new Date(table.order.created_at.replace(' ', 'T'));
            const diffMs = now.getTime() - orderCreated.getTime();

            console.log(`Table ${table.table_number} - Debug time calculation:`, {
                now: now.toISOString(),
                orderCreated: table.order.created_at,
                parsedOrderCreated: orderCreated.toISOString(),
                diffMs: diffMs,
                diffHours: Math.floor(diffMs / 3600000),
                diffMins: Math.floor(diffMs / 60000)
            });

            firstOrderTime = calculateTimeAgo(table.order.created_at);
        }

        const bgColor = hasOrder ? 'bg-gradient-to-br from-blue-50 to-blue-100' : 'bg-gradient-to-br from-gray-50 to-gray-100';
        const borderColor = hasOrder ? 'border-blue-400' : 'border-gray-300';

        return `
            <div class="table-card ${bgColor} border-2 ${borderColor} rounded-xl p-4 shadow-lg hover:shadow-xl transition-all cursor-pointer" onclick="openTableOrder(${table.table_number})">
                <div class="text-center mb-3">
                    <div class="text-4xl font-bold text-gray-800 mb-2">${table.table_number}</div>
                    ${table.customer_name ? `<div class="text-sm font-bold text-gray-700 mb-1">${table.customer_name}</div>` : ''}
                    ${table.phone ? `<div class="text-xs text-gray-600">${table.phone}</div>` : ''}
                </div>
                ${hasOrder ? `
                    <div class="border-t border-gray-300 pt-3 mt-3">
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-xs text-gray-600">رقم الطلب</span>
                            <span class="text-sm font-bold text-gray-800">${table.order.order_number}</span>
                        </div>
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-xs text-gray-600">الاجمالي</span>
                            <span class="text-lg font-bold text-blue-600">${totalAmount.toFixed(2)} ج.م</span>
                        </div>
                        ${firstOrderTime ? `
                            <div class="flex justify-between items-center mb-2">
                                <span class="text-xs text-gray-600">أول طلب قبل</span>
                                <span class="text-xs text-gray-500" id="firstOrderTime_${table.table_number}">${firstOrderTime}</span>
                            </div>
                        ` : ''}
                        <div class="flex justify-between items-center">
                            <span class="text-xs text-gray-600">آخر طلب قبل</span>
                            <span class="text-xs text-gray-500" id="lastOrderTime_${table.table_number}">${timeAgo}</span>
                        </div>
                    </div>
                ` : `
                    <div class="text-center text-gray-400 text-sm mt-3">لا توجد طلبات</div>
                `}
            </div>
        `;
    }).join('');
}

// Open table order (load order into cashier)
async function openTableOrder(tableNumber) {
    try {
        // [REMOVED] Auto-save logic was causing "ghost orders".
        // Context switch (opening a table) now discards unsubmitted scratchpad items 
        // to ensure 100% accuracy and prevent unintended orders.

        // Open the requested table directly

        // Now open the new table
        const response = await fetch(`/api/tables/${tableNumber}`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            console.error('Failed to get table:', response.status, errorText);
            throw new Error(`Failed to get table: ${response.status}`);
        }

        const table = await response.json().catch(error => {
            console.error('Error parsing table JSON:', error);
            throw new Error('Invalid response format');
        });

        if (table.order && table.order.id) {
            // Load order into cashier
            try {
                await loadOrder(table.order.id);
                closeTablesModal();
                // No notification when opening table/order
            } catch (loadError) {
                console.error('Error loading order for table:', loadError);
                // If loading fails, still open table but with empty order
                currentOrder = { items: [], orderNumber: null, tableNumber: tableNumber, orderType: 'dine-in', submittedItems: [], discount: 0, discountType: 'percent', numberOfPeople: 1 };
                document.getElementById('orderNumberDisplay').textContent = '';
                const tableNumberDisplay = document.getElementById('tableNumberDisplay');
                if (tableNumberDisplay) {
                    tableNumberDisplay.textContent = tableNumber;
                }
                updateOrderDisplay();
                updatePhoneButtonState();
                closeTablesModal();
                if (window.notificationManager) {
                    window.notificationManager.warning('تم فتح الطاولة لكن فشل تحميل الطلب. يمكنك إضافة منتجات جديدة.');
                }
            }
        } else {
            // No order yet, create new order for this table
            // Reset current order first
            currentOrder = { items: [], orderNumber: null, tableNumber: tableNumber, orderType: 'dine-in', submittedItems: [], discount: 0, discountType: 'percent', numberOfPeople: 1 };
            document.getElementById('orderNumberDisplay').textContent = '';
            const tableNumberDisplay = document.getElementById('tableNumberDisplay');
            if (tableNumberDisplay) {
                tableNumberDisplay.textContent = tableNumber;
            }
            updateOrderDisplay();
            updatePhoneButtonState();
            closeTablesModal();
            // No notification when opening table
        }
    } catch (error) {
        console.error('Error opening table order:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في فتح طلب الطاولة: ' + (error.message || 'خطأ غير معروف'));
        }
    }
}

// Show new table modal
function showNewTableModal() {
    console.log('showNewTableModal called');
    const modal = document.getElementById('newTableModal');
    if (modal) {
        console.log('New table modal found, showing...');
        modal.classList.remove('hidden');
        modal.style.display = 'flex';
        modal.style.zIndex = '99999';
        // Reset form
        const tableNumberInput = document.getElementById('newTableNumber');
        const customerNameInput = document.getElementById('newTableCustomerName');
        const phoneInput = document.getElementById('newTablePhone');

        if (tableNumberInput) tableNumberInput.value = '';
        if (customerNameInput) customerNameInput.value = '';
        if (phoneInput) phoneInput.value = '';

        // Focus on table number input
        if (tableNumberInput) {
            setTimeout(() => {
                tableNumberInput.focus();
            }, 100);
        }
    } else {
        console.error('New table modal not found!');
        if (window.notificationManager) {
            window.notificationManager.error('خطأ: نافذة إنشاء طاولة جديدة غير موجودة');
        }
    }
}

// Close new table modal
function closeNewTableModal() {
    const modal = document.getElementById('newTableModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}

// Save new table
async function saveNewTable() {
    console.log('saveNewTable called');
    const tableNumberInput = document.getElementById('newTableNumber');
    const customerNameInput = document.getElementById('newTableCustomerName');
    const phoneInput = document.getElementById('newTablePhone');

    if (!tableNumberInput) {
        console.error('newTableNumber input not found!');
        if (window.notificationManager) {
            window.notificationManager.error('خطأ: حقل رقم الطاولة غير موجود');
        }
        return;
    }

    const tableNumber = parseInt(tableNumberInput.value);
    const customerName = customerNameInput ? customerNameInput.value.trim() : '';
    const phone = phoneInput ? phoneInput.value.trim() : '';

    console.log('Table data:', { tableNumber, customerName, phone });

    if (!tableNumber || tableNumber < 1) {
        console.warn('Invalid table number:', tableNumber);
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء إدخال رقم طاولة صحيح');
        }
        return;
    }

    try {
        console.log('Sending request to create table...');
        const requestBody = {
            table_number: tableNumber,
            customer_name: customerName || null,
            phone: phone || null
        };
        console.log('Request body:', requestBody);

        const response = await fetch('/api/tables', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers);

        if (response.ok) {
            const tableData = await response.json();
            console.log('Table created successfully:', tableData);
            closeNewTableModal();
            await loadTables();
            // Update tables count
            updateTablesCount();
            if (window.notificationManager) {
                window.notificationManager.success(`تم إنشاء الطاولة ${tableNumber} بنجاح`);
            }
        } else {
            const errorText = await response.text().catch(() => 'Unknown error');
            console.error('Failed to create table. Status:', response.status, 'Error:', errorText);
            let errorData;
            try {
                errorData = JSON.parse(errorText);
            } catch (e) {
                errorData = { detail: errorText || 'Unknown error' };
            }
            throw new Error(errorData.detail || `Failed to create table (${response.status})`);
        }
    } catch (error) {
        console.error('Error creating table:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في إنشاء الطاولة: ' + (error.message || 'خطأ غير معروف'));
        } else {
            alert('خطأ في إنشاء الطاولة: ' + (error.message || 'خطأ غير معروف'));
        }
    }
}

// Search functionality
let searchQuery = '';

// Normalize Arabic text for smart search
function normalizeArabic(text) {
    if (!text) return '';
    return text
        .replace(/[أإآ]/g, 'ا') // Normalize Alef
        .replace(/ة/g, 'ه')     // Normalize Teh Marbuta
        .replace(/ى/g, 'ي')     // Normalize Alef Maqsura
        .replace(/ؤ/g, 'و')     // Normalize Waw with Hamza
        .replace(/ئ/g, 'ي')     // Normalize Yeh with Hamza
        .toLowerCase();
}

function setupSearch() {
    const searchContainer = document.getElementById('searchContainer');
    const searchInput = document.getElementById('searchInput');

    if (!searchContainer || !searchInput) return;

    // Expand on click
    searchContainer.addEventListener('click', () => {
        searchContainer.style.width = '250px';
        // Ensure input is visible and interactive
        searchInput.classList.remove('opacity-0', 'pointer-events-none');
        searchInput.classList.add('opacity-100');
        searchInput.focus();
    });

    // Collapse on blur if empty
    searchInput.addEventListener('blur', () => {
        if (!searchInput.value.trim()) {
            searchContainer.style.width = '40px';
            searchInput.classList.remove('opacity-100');
            searchInput.classList.add('opacity-0', 'pointer-events-none');
            searchInput.value = '';
            searchQuery = '';
            // Reset filter
            filterByCategory(selectedCategoryId);
        }
    });

    // Search input handler
    searchInput.addEventListener('input', (e) => {
        const rawQuery = e.target.value.trim();
        searchQuery = normalizeArabic(rawQuery);

        if (searchQuery) {
            // Search across ALL products with normalization
            filteredProducts = products.filter(p => {
                const normalizedName = normalizeArabic(p.name);
                const normalizedDesc = normalizeArabic(p.description || '');
                return normalizedName.includes(searchQuery) || normalizedDesc.includes(searchQuery);
            });
            renderProducts();
        } else {
            // If empty, revert to current category
            filterByCategory(selectedCategoryId);
        }
    });

    // Prevent container click from closing immediately when clicking input
    searchInput.addEventListener('click', (e) => {
        e.stopPropagation();
    });
}

// Legacy function kept to avoid errors if called elsewhere, but logic moved to setupSearch
function performSearch(query) {
    // No-op or redirect to new logic if needed
}

// Shift management
let currentShift = null;

// Check current shift
async function checkCurrentShift() {
    try {
        const response = await fetch('/api/shifts/current');
        if (response.ok) {
            const shiftData = await response.json();
            if (shiftData) {
                currentShift = shiftData;
                updateShiftIcon();

                // Hide required modal if shift is open
                const shiftRequiredModal = document.getElementById('shiftRequiredModal');
                if (shiftRequiredModal) {
                    shiftRequiredModal.classList.add('hidden');
                }
            } else {
                currentShift = null;
                updateShiftIcon();

                // If no shift is open, show required modal
                // ALWAYS enforce shift - blocking mode
                showShiftRequiredModal();
            }
        } else {
            console.warn('Failed to check shift status');
            currentShift = null;
            updateShiftIcon();
            // ALWAYS enforce shift if check fails
            showShiftRequiredModal();
        }
    } catch (error) {
        console.error('Error checking shift:', error);
        currentShift = null;
        updateShiftIcon();
        // ALWAYS enforce shift on error
        showShiftRequiredModal();
    }
}

// Check if shift is overdue (runs periodically)
async function checkShiftOverdue() {
    if (!currentShift) return;

    try {
        const response = await fetch('/api/shifts/current');
        if (response.ok) {
            const shiftData = await response.json();
            if (shiftData) {
                // Update currentShift with latest data (including is_overdue)
                currentShift = shiftData;
                updateShiftIcon();
            }
        }
    } catch (error) {
        console.error('Error checking shift overdue:', error);
    }
}

// Update shift icon status
function updateShiftIcon() {
    const shiftBtn = document.getElementById('shiftBtn');
    const shiftStatusDot = document.getElementById('shiftStatusDot');

    if (shiftBtn && shiftStatusDot) {
        if (currentShift) {
            // Shift is open - check if overdue
            shiftStatusDot.classList.remove('hidden');
            shiftStatusDot.classList.remove('bg-gray-400');

            // Check if shift is overdue (past end time)
            if (currentShift.is_overdue) {
                // Shift is overdue - show red dot
                shiftStatusDot.classList.remove('bg-green-500');
                shiftStatusDot.classList.add('bg-red-500');
                shiftBtn.title = `الشيفت: ${currentShift.shift_name} ${currentShift.shift_number > 1 ? currentShift.shift_number : ''} (متأخر)`;
            } else {
                // Shift is on time - show green dot
                shiftStatusDot.classList.remove('bg-red-500');
                shiftStatusDot.classList.add('bg-green-500');
                shiftBtn.title = `الشيفت: ${currentShift.shift_name} ${currentShift.shift_number > 1 ? currentShift.shift_number : ''}`;
            }
        } else {
            // Shift is closed - show gray dot
            shiftStatusDot.classList.remove('hidden');
            shiftStatusDot.classList.remove('bg-green-500');
            shiftStatusDot.classList.remove('bg-red-500');
            shiftStatusDot.classList.add('bg-gray-400');
            shiftBtn.title = 'الشيفت: غير مفتوح';
        }
    }
}

// Show shift modal
async function showShiftModal() {
    const modal = document.getElementById('shiftModal');
    const header = document.getElementById('shiftModalHeader');
    const title = document.getElementById('shiftModalTitle');
    const content = document.getElementById('shiftModalContent');

    if (!modal || !content) return;

    if (currentShift) {
        // Shift is open - show close option (can be closed normally)
        const overdueClass = currentShift.is_overdue ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200';
        const overdueText = currentShift.is_overdue ? 'text-red-800' : 'text-green-800';
        const overdueBadge = currentShift.is_overdue ? 'bg-red-500' : 'bg-green-500';
        const overdueStatus = currentShift.is_overdue ? ' (متأخر)' : '';

        // Add close button when shift is open
        header.innerHTML = `
            <div class="flex justify-between items-center">
                <h2 id="shiftModalTitle" class="text-2xl font-bold text-gray-800">إدارة الشيفت</h2>
                <button onclick="closeShiftModal()" class="text-gray-500 hover:text-gray-700 text-2xl font-bold w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition">×</button>
            </div>
        `;

        content.innerHTML = `
            <div class="space-y-4">
                <div class="${overdueClass} border-2 rounded-lg p-4">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-lg font-bold ${overdueText}">الشيفت مفتوح${overdueStatus}</span>
                        <span class="px-3 py-1 ${overdueBadge} text-white rounded-full text-sm font-bold">${currentShift.shift_name} ${currentShift.shift_number > 1 ? currentShift.shift_number : ''}</span>
                    </div>
                    <div class="text-sm text-gray-600">
                        <div>تاريخ: ${currentShift.shift_date}</div>
                        <div>فتح في: ${new Date(currentShift.opened_at).toLocaleTimeString('ar-EG')}</div>
                    </div>
                </div>
                <button onclick="closeShift()" class="w-full px-6 py-4 bg-red-600 text-white rounded-lg font-bold text-lg shadow-lg hover:bg-red-700 transition">
                    إغلاق الشيفت
                </button>
            </div>
        `;

        // Allow closing modal when shift is open (click outside or close button)
        modal.onclick = function (e) {
            if (e.target === modal) {
                closeShiftModal();
            }
        };
    } else {
        // No shift open - cannot close modal, must open a shift
        // Remove close button when no shift is open
        header.innerHTML = `
            <h2 id="shiftModalTitle" class="text-2xl font-bold text-gray-800 text-center">فتح شيفت</h2>
        `;

        content.innerHTML = '<div class="text-center py-4 text-gray-400">جاري التحميل...</div>';

        try {
            const response = await fetch('/api/shifts/available');
            if (response.ok) {
                const availableShifts = await response.json();

                if (availableShifts.length === 0) {
                    content.innerHTML = '<div class="text-center py-4 text-red-500">لا توجد شيفتات متاحة. يرجى إعداد الشيفتات من صفحة الإدارة.</div>';
                } else {
                    // Show all available shifts with light mode colors
                    const buttonsHtml = availableShifts.map((shift, index) => {
                        return `
                            <button onclick="openShiftByName('${shift.name}')" class="w-full px-6 py-4 bg-blue-50 border-2 border-blue-200 text-blue-700 rounded-lg font-bold text-lg hover:bg-blue-100 hover:border-blue-300 transition">
                                فتح شيفت ${shift.name}
                            </button>
                        `;
                    }).join('');

                    content.innerHTML = `<div class="space-y-3">${buttonsHtml}</div>`;
                }
            } else {
                content.innerHTML = '<div class="text-center py-4 text-red-500">خطأ في تحميل الشيفتات المتاحة</div>';
            }
        } catch (error) {
            console.error('Error loading available shifts:', error);
            content.innerHTML = '<div class="text-center py-4 text-red-500">خطأ في تحميل الشيفتات المتاحة</div>';
        }

        // Prevent closing modal by clicking outside when no shift is open
        modal.onclick = function (e) {
            if (e.target === modal) {
                // Prevent closing when clicking outside
                e.stopPropagation();
            }
        };
    }

    modal.classList.remove('hidden');
}

// Close shift modal (only allowed when shift is open)
function closeShiftModal() {
    // Only allow closing if a shift is currently open
    if (!currentShift) {
        return; // Don't allow closing when no shift is open
    }
    const modal = document.getElementById('shiftModal');
    if (modal) {
        modal.classList.add('hidden');
        // Reset onclick handler
        modal.onclick = null;
    }
}

// Show shift required modal
async function showShiftRequiredModal() {
    const modal = document.getElementById('shiftRequiredModal');
    const buttonsContainer = document.getElementById('shiftRequiredButtons');

    if (!modal) return;

    // Load available shifts
    if (buttonsContainer) {
        buttonsContainer.innerHTML = '<div class="text-center py-4 text-gray-400">جاري التحميل...</div>';

        try {
            const response = await fetch('/api/shifts/available');
            if (response.ok) {
                const availableShifts = await response.json();

                if (availableShifts.length === 0) {
                    buttonsContainer.innerHTML = '<div class="text-center py-4 text-red-500">لا توجد شيفتات متاحة. يرجى إعداد الشيفتات من صفحة الإدارة.</div>';
                } else {
                    const buttonsHtml = availableShifts.map((shift, index) => {
                        return `
                            <button onclick="openShiftRequiredByName('${shift.name}')" class="w-full px-6 py-4 bg-blue-50 border-2 border-blue-200 text-blue-700 rounded-lg font-bold text-lg hover:bg-blue-100 hover:border-blue-300 transition">
                                فتح شيفت ${shift.name}
                            </button>
                        `;
                    }).join('');

                    buttonsContainer.innerHTML = `<div class="space-y-3">${buttonsHtml}</div>`;
                }
            } else {
                buttonsContainer.innerHTML = '<div class="text-center py-4 text-red-500">خطأ في تحميل الشيفتات المتاحة</div>';
            }
        } catch (error) {
            console.error('Error loading available shifts:', error);
            buttonsContainer.innerHTML = '<div class="text-center py-4 text-red-500">خطأ في تحميل الشيفتات المتاحة</div>';
        }
    }

    modal.classList.remove('hidden');
}

// Open shift by name from required modal
async function openShiftRequiredByName(shiftName) {
    await openShiftByName(shiftName);
    const modal = document.getElementById('shiftRequiredModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Open shift from required modal
async function openShiftRequired(shiftType) {
    await openShift(shiftType);
    const modal = document.getElementById('shiftRequiredModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Open shift by name (new method - uses shift name from settings)
async function openShiftByName(shiftName) {
    try {
        const response = await fetch('/api/shifts/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ shift_name: shiftName })
        });

        if (response.ok) {
            currentShift = await response.json();
            updateShiftIcon();
            closeShiftModal();

            // Hide report page if visible
            hideShiftReportPage();

            if (window.notificationManager) {
                window.notificationManager.success(`تم فتح شيفت ${currentShift.shift_name} ${currentShift.shift_number > 1 ? currentShift.shift_number : ''} بنجاح`);
            }
        } else {
            const error = await response.json();
            if (window.notificationManager) {
                window.notificationManager.error(error.detail || 'خطأ في فتح الشيفت');
            }
        }
    } catch (error) {
        console.error('Error opening shift:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في فتح الشيفت: ' + error.message);
        }
    }
}

// Open shift (backward compatibility - uses shift_type)
async function openShift(shiftType) {
    try {
        const response = await fetch('/api/shifts/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ shift_type: shiftType })
        });

        if (response.ok) {
            currentShift = await response.json();
            updateShiftIcon();
            closeShiftModal();

            // Hide report page if visible
            hideShiftReportPage();

            if (window.notificationManager) {
                window.notificationManager.success(`تم فتح شيفت ${currentShift.shift_name} ${currentShift.shift_number > 1 ? currentShift.shift_number : ''} بنجاح`);
            }
        } else {
            const error = await response.json();
            if (window.notificationManager) {
                window.notificationManager.error(error.detail || 'خطأ في فتح الشيفت');
            }
        }
    } catch (error) {
        console.error('Error opening shift:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في فتح الشيفت: ' + error.message);
        }
    }
}

// Close shift
async function closeShift() {
    if (!currentShift) return;

    // Show cash drawer amount modal
    showCashDrawerModal();
}

// Show cash drawer amount modal
function showCashDrawerModal() {
    const modal = document.getElementById('cashDrawerModal');
    if (!modal) {
        console.error('Cash drawer modal not found');
        return;
    }

    // Expected cash calculation removed - not shown to cashier

    // Reset input
    const cashInput = document.getElementById('cashDrawerAmount');
    if (cashInput) {
        cashInput.value = '';
    }

    modal.classList.remove('hidden');

    // Focus on input
    setTimeout(() => {
        if (cashInput) {
            cashInput.focus();
        }
    }, 200);
}

// Close cash drawer modal
function closeCashDrawerModal() {
    const modal = document.getElementById('cashDrawerModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Confirm close shift with cash amount
async function confirmCloseShift() {
    if (!currentShift) return;

    const cashInput = document.getElementById('cashDrawerAmount');
    if (!cashInput) return;

    const cashDrawerAmount = parseFloat(cashInput.value);
    if (isNaN(cashDrawerAmount) || cashDrawerAmount < 0) {
        if (window.notificationManager) {
            window.notificationManager.error('يرجى إدخال مبلغ النقدية صحيح');
        }
        return;
    }

    try {
        const response = await fetch(`/api/shifts/${currentShift.id}/close`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cash_drawer_amount: cashDrawerAmount
            })
        });

        if (response.ok) {
            const closedShift = await response.json();
            console.log('[DEBUG] Closed shift response:', closedShift);
            console.log('[DEBUG] Has print_preview?', !!closedShift.print_preview);

            closeCashDrawerModal();
            closeShiftModal();

            // Show shift report page
            showShiftReportPage(closedShift);

            // Check for Browser Print Preview (Shift Report)
            if (closedShift.print_preview) {
                console.log('[DEBUG] Calling printImageInBrowser for shift report');
                printImageInBrowser(closedShift.print_preview);
            } else {
                console.log('[DEBUG] No print_preview in shift response');
            }

            if (window.notificationManager) {
                window.notificationManager.success('تم إغلاق الشيفت بنجاح');
            }
        } else {
            const error = await response.json();
            if (window.notificationManager) {
                window.notificationManager.error(error.detail || 'خطأ في إغلاق الشيفت');
            }
        }
    } catch (error) {
        console.error('Error closing shift:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في إغلاق الشيفت: ' + error.message);
        }
    }
}

// Show shift report page (blocks until new shift is opened)
function showShiftReportPage(shift) {
    // Hide main content
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.style.display = 'none';
    }

    // Show shift report
    let reportDiv = document.getElementById('shiftReportPage');
    if (!reportDiv) {
        reportDiv = document.createElement('div');
        reportDiv.id = 'shiftReportPage';
        reportDiv.className = 'fixed inset-0 bg-gray-100 z-50 overflow-y-auto';
        document.body.appendChild(reportDiv);
    }

    const cashDiff = shift.cash_difference || 0;
    const diffClass = cashDiff >= 0 ? 'text-green-600' : 'text-red-600';
    const diffText = cashDiff >= 0 ? `زيادة: ${cashDiff.toFixed(2)}` : `عجز: ${Math.abs(cashDiff).toFixed(2)}`;

    reportDiv.innerHTML = `
        <div class="min-h-screen p-6">
            <div class="max-w-4xl mx-auto bg-white rounded-xl shadow-lg p-8">
                <div class="text-center mb-8">
                    <h1 class="text-3xl font-bold text-gray-800 mb-2">تم إغلاق الشيفت بنجاح</h1>
                    <p class="text-gray-600">${shift.shift_name} ${shift.shift_number > 1 ? shift.shift_number : ''}</p>
                    <p class="text-sm text-gray-500 mt-2">${shift.shift_date} - ${shift.closed_at || ''}</p>
                </div>
                
                <!-- Statistics hidden from cashier - only visible in admin panel -->
                
                <div class="text-center mt-8">
                    <p class="text-lg text-gray-700 mb-4">يجب فتح شيفت جديد للمتابعة</p>
                    <button onclick="openNewShiftFromReport()" class="px-8 py-4 bg-blue-600 text-white rounded-lg font-bold text-lg shadow-lg hover:bg-blue-700 transition">
                        فتح شيفت جديد
                    </button>
                </div>
            </div>
        </div>
    `;

    reportDiv.style.display = 'block';
}

// Open new shift from report page
async function openNewShiftFromReport() {
    // Hide report page first
    hideShiftReportPage();

    // Show shift modal
    showShiftModal();
}

// Update openShift to hide report page when new shift is opened
async function openShift(shiftType) {
    try {
        const response = await fetch('/api/shifts/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ shift_type: shiftType })
        });

        if (response.ok) {
            currentShift = await response.json();
            updateShiftIcon();
            closeShiftModal();

            // Hide report page if visible
            hideShiftReportPage();

            if (window.notificationManager) {
                window.notificationManager.success(`تم فتح شيفت ${currentShift.shift_name} ${currentShift.shift_number > 1 ? currentShift.shift_number : ''} بنجاح`);
            }
        } else {
            const error = await response.json();
            if (window.notificationManager) {
                window.notificationManager.error(error.detail || 'خطأ في فتح الشيفت');
            }
        }
    } catch (error) {
        console.error('Error opening shift:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في فتح الشيفت: ' + error.message);
        }
    }
}

// Hide shift report page
function hideShiftReportPage() {
    const reportDiv = document.getElementById('shiftReportPage');
    if (reportDiv) {
        reportDiv.style.display = 'none';
    }

    // Show main content
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.style.display = 'block';
    }
}

// Check shift before creating order
async function checkShiftBeforeOrder() {
    if (!currentShift) {
        showShiftRequiredModal();
        return false;
    }
    return true;
}

// PlayStation Logic
let playstationModalVisible = false;
let selectedPlaystationType = 'single'; // Default

// Make globally available immediately
window.showPlaystationModal = function () {
    console.log('showPlaystationModal called');
    const typeModal = document.getElementById('playstationTypeModal');
    if (typeModal) {
        console.log('Found typeModal, removing hidden class');
        typeModal.classList.remove('hidden');
        window.loadPlaystationPrices();
    } else {
        console.error('playstationTypeModal NOT FOUND');
    }
};

window.loadPlaystationPrices = async function () {
    console.log('Loading PS prices...');
    try {
        const response = await fetch('/api/settings?t=' + new Date().getTime()); // Cache busting
        if (response.ok) {
            const settings = await response.json();
            console.log('Settings loaded:', settings);
            const single = settings.playstation_price_per_hour || 50;
            const multi = settings.playstation_price_multi || 70;

            const singleEl = document.getElementById('psPriceSingle');
            const multiEl = document.getElementById('psPriceMulti');

            if (singleEl) singleEl.textContent = `${single} ج.م/ساعة`;
            if (multiEl) multiEl.textContent = `${multi} ج.م/ساعة`;
        }
    } catch (e) {
        console.error('Error loading ps prices', e);
    }
};

window.closePlaystationTypeModal = function () {
    document.getElementById('playstationTypeModal').classList.add('hidden');
};

window.selectPlaystationType = function (type) {
    console.log('Selected type:', type);
    selectedPlaystationType = type;
    window.closePlaystationTypeModal();

    const modal = document.getElementById('playstationModal');
    if (modal) {
        modal.classList.remove('hidden');
        playstationModalVisible = true;
        loadPlaystationTables(); // This assumes loadPlaystationTables is also available or needs to be window attached
    } else {
        console.error('playstationModal NOT FOUND');
    }
};

// Force attach event listener
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('playstationBtn');
    if (btn) {
        console.log('Attaching click listener to playstationBtn');
        btn.onclick = window.showPlaystationModal; // Override any inline onclick
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('PlayStation Button Clicked (Event Listener)');
            window.showPlaystationModal();
        });
    } else {
        console.error('playstationBtn NOT FOUND in DOM');
    }
});

function closePlaystationModal() {
    const modal = document.getElementById('playstationModal');
    if (modal) {
        modal.classList.add('hidden');
        playstationModalVisible = false;
    }
}



window.loadPlaystationTables = async function () {
    const grid = document.getElementById('playstationTablesGrid');
    if (!grid) return;

    grid.innerHTML = '<div class="col-span-4 text-center py-8">جاري التحميل...</div>';

    try {
        const response = await fetch('/api/tables');
        if (response.ok) {
            const tables = await response.json();
            window.renderPlaystationTables(tables);
        } else {
            grid.innerHTML = '<div class="col-span-4 text-center py-8 text-red-500">خطأ في تحميل الطاولات</div>';
        }
    } catch (error) {
        console.error('Error loading tables:', error);
        grid.innerHTML = '<div class="col-span-4 text-center py-8 text-red-500">خطأ في الاتصال</div>';
    }
};

window.renderPlaystationTables = function (tables) {
    const grid = document.getElementById('playstationTablesGrid');
    if (!grid) return;

    grid.innerHTML = '';

    tables.forEach(table => {
        const isBusy = table.playstation_start_time != null;
        let timerHtml = '';
        let typeBadge = '';

        if (isBusy) {
            timerHtml = `<div class="mt-2 text-purple-700 font-bold text-lg ps-timer" data-start="${table.playstation_start_time}">جاري الحساب...</div>`;
            const typeText = table.playstation_type === 'multi' ? 'زوجي' : 'فردي';
            const typeColor = table.playstation_type === 'multi' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800';
            typeBadge = `<span class="absolute top-2 right-2 px-2 py-1 rounded text-xs font-bold ${typeColor}">${typeText}</span>`;
        }

        const card = document.createElement('div');
        card.className = `
            relative p-6 rounded-xl border-2 transition-all cursor-pointer shadow-sm
            ${isBusy
                ? 'bg-purple-50 border-purple-500'
                : 'bg-white border-gray-200 hover:border-blue-300 hover:shadow-md'}
        `;

        card.innerHTML = `
            ${typeBadge}
            <div class="flex flex-col items-center gap-2">
                <span class="text-3xl font-bold ${isBusy ? 'text-purple-700' : 'text-gray-700'}">
                    طاولة ${table.table_number}
                </span>
                 ${timerHtml}
                 <div class="mt-2 w-full">
                    ${isBusy
                ? `<button onclick="window.endPlaystationSession(${table.table_number})" class="w-full px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 font-bold transition">إيقاف</button>`
                : `<button onclick="window.startPlaystationSession(${table.table_number})" class="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 font-bold transition">بدء (${selectedPlaystationType === 'multi' ? 'زوجي' : 'فردي'})</button>`
            }
                 </div>
            </div>
        `;

        grid.appendChild(card);
    });

    if (!window.psTimerInterval) {
        window.psTimerInterval = setInterval(window.updatePlaystationTimers, 1000);
    }
    window.updatePlaystationTimers();
};

window.updatePlaystationTimers = function () {
    const timers = document.querySelectorAll('.ps-timer');
    timers.forEach(timer => {
        const startStr = timer.getAttribute('data-start');
        if (startStr) {
            // Treat the date string as local time by replacing space with T to fit ISO format roughly, 
            // but typical SQLite string is "YYYY-MM-DD HH:MM:SS".
            // We need to parse it manually to be safe or ensure it's treated as local.
            const parts = startStr.split(/[- :]/);
            // new Date(year, monthIndex, day, hours, minutes, seconds)
            const startDate = new Date(parts[0], parts[1] - 1, parts[2], parts[3], parts[4], parts[5]);
            const now = new Date();

            const diffMs = now - startDate;
            const diffSec = Math.floor(diffMs / 1000);

            if (diffSec >= 0) {
                const h = Math.floor(diffSec / 3600);
                const m = Math.floor((diffSec % 3600) / 60);
                const s = diffSec % 60;
                timer.textContent = `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
            } else {
                timer.textContent = "0:00:00";
            }
        }
    });
}

window.startPlaystationSession = async function (tableNumber) {
    if (!await checkShiftBeforeOrder()) return;

    try {
        const response = await fetch('/api/playstation/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                table_number: tableNumber,
                type: selectedPlaystationType
            })
        });

        if (response.ok) {
            if (window.notificationManager) window.notificationManager.success('تم بدء الوقت');
            window.loadPlaystationTables();
        } else {
            const err = await response.json();
            if (window.notificationManager) window.notificationManager.error(err.detail || 'خطأ');
        }
    } catch (e) {
        console.error(e);
        if (window.notificationManager) window.notificationManager.error('خطأ في الاتصال');
    }
};

window.endPlaystationSession = async function (tableNumber) {
    try {
        const response = await fetch('/api/playstation/end', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ table_number: tableNumber })
        });

        if (response.ok) {
            const data = await response.json();
            if (window.notificationManager) window.notificationManager.success(`تم إنهاء الوقت. السعر: ${data.total_price.toFixed(2)}`);
            window.loadPlaystationTables();

            // Check if this table is currently open in cashier
            // If so, reload the order to show the added PlayStation item immediately
            if (currentOrder && currentOrder.tableNumber == tableNumber) {
                console.log('Ended session for current table, refreshing order...');
                if (data.order_id) {
                    await loadOrder(data.order_id);
                } else {
                    // Fallback if order_id not in response
                    await loadTableOrder(tableNumber);
                }
            }
        } else {
            const err = await response.json();
            if (window.notificationManager) window.notificationManager.error(err.detail || 'خطأ');
        }
    } catch (e) {
        console.error(e);
        if (window.notificationManager) window.notificationManager.error('خطأ في الاتصال');
    }
}

// Make functions global
window.showPlaystationModal = showPlaystationModal;
window.closePlaystationModal = closePlaystationModal;
window.startPlaystationSession = startPlaystationSession;
window.endPlaystationSession = endPlaystationSession;
window.selectPlaystationType = selectPlaystationType;
window.closePlaystationTypeModal = closePlaystationTypeModal;

window.showTablesModal = showTablesModal;
window.closeTablesModal = closeTablesModal;
window.openTableOrder = openTableOrder;
window.showNewTableModal = showNewTableModal;
window.closeNewTableModal = closeNewTableModal;
window.saveNewTable = saveNewTable;
window.updateTablesCount = updateTablesCount;
window.showShiftModal = showShiftModal;
window.closeShiftModal = closeShiftModal;
window.openShift = openShift;
window.openShiftByName = openShiftByName;
window.closeShift = closeShift;
window.openShiftRequired = openShiftRequired;
window.openShiftRequiredByName = openShiftRequiredByName;

// Fallback notification function
function createFallbackNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = 'fixed top-4 left-4 z-[99999] bg-blue-600 text-white px-6 py-4 rounded-lg shadow-2xl border-2 border-white flex items-center gap-3';
    if (type === 'success') notification.className = notification.className.replace('bg-blue-600', 'bg-green-600');
    if (type === 'error') notification.className = notification.className.replace('bg-blue-600', 'bg-red-600');

    notification.innerHTML = `
        <span class="text-xl font-bold">🔔</span>
        <span class="text-lg font-bold">${message}</span>
    `;

    document.body.appendChild(notification);

    // Remove after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Helper to print image in browser window
function printImageInBrowser(base64Image) {
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
        alert('Please allow popups for this website');
        return;
    }

    const htmlContent = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>Print Invoice</title>
            <style>
                body { margin: 0; padding: 0; display: flex; justify-content: center; align-items: flex-start; background: #eee; }
                img { max-width: 100%; height: auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                @media print {
                    body { background: white; }
                    img { box-shadow: none; width: 100%; }
                }
            </style>
        </head>
        <body>
            <img src="data:image/png;base64,${base64Image}" onload="setTimeout(function(){ window.print(); window.close(); }, 500);" />
        </body>
        </html>
    `;

    printWindow.document.open();
    printWindow.document.write(htmlContent);
    printWindow.document.close();
}
