// Global state
let isAuthenticated = false;
let currentCategoryId = null;
let currentProductId = null;
let categories = [];
let products = [];
let productSearchQuery = '';
let isImageDeleted = false;

// Cloud Mode Detection
const IS_CLOUD = window.IS_CLOUD_VIEW || window.CLOUD_MODE || false;
if (IS_CLOUD) {
    console.log('[Admin.js] Running in CLOUD MODE - write operations disabled');
}

// Helper: Check if feature is allowed in cloud mode
function isCloudReadOnly() {
    return IS_CLOUD;
}

// Helper: Show cloud-only message
function showCloudMessage(message = 'هذه الميزة غير متاحة في وضع العرض السحابي') {
    showNotification(message, 'info');
}

// Helper: Execute command on Local System via WebSocket
async function executeCommand(commandType, payload) {
    try {
        const response = await fetch('/api/command/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: commandType,
                payload: payload
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Command failed');
        }

        const result = await response.json();

        if (result.status === 'error') {
            throw new Error(result.error || 'Command failed');
        }

        return result.result || result;

    } catch (error) {
        console.error(`[Command ${commandType}] Error:`, error);

        // Check if it's a connection error
        if (error.message.includes('offline') || error.message.includes('503')) {
            showNotification('النظام المحلي غير متصل حالياً. لا يمكن تنفيذ العملية.', 'error');
        } else {
            showNotification(error.message || 'حدث خطأ أثناء تنفيذ العملية', 'error');
        }

        throw error;
    }
}

// Helper: Check connection status
async function checkConnectionStatus() {
    try {
        const response = await fetch('/api/connection/status');
        const data = await response.json();
        return data.online === true;
    } catch (error) {
        console.error('[Connection Status] Error:', error);
        return false;
    }
}



// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
});

// Check authentication
function checkAuth() {
    const auth = sessionStorage.getItem('authenticated');
    const pageType = sessionStorage.getItem('pageType');
    if (auth === 'true' && pageType === 'admin') {
        isAuthenticated = true;
        showMainContent();
    } else {
        window.location.href = '/';
    }
}

// Show main content
function showMainContent() {
    document.getElementById('mainContent').classList.remove('hidden');
    // Load data first
    loadData().then(() => {
        // Show statistics tab by default
        showTab('statistics');
    });
}

// Setup event listeners
function setupEventListeners() {

    // Tabs
    document.getElementById('statisticsTab').addEventListener('click', () => showTab('statistics'));
    document.getElementById('categoriesTab').addEventListener('click', () => showTab('categories'));
    document.getElementById('productsTab').addEventListener('click', () => showTab('products'));
    document.getElementById('reportsTab').addEventListener('click', () => showTab('reports'));
    document.getElementById('ordersTab').addEventListener('click', () => showTab('orders'));
    document.getElementById('settingsTab').addEventListener('click', () => showTab('settings'));
    document.getElementById('shiftsTab').addEventListener('click', () => showTab('shifts'));
    document.getElementById('backupTab').addEventListener('click', () => showTab('backup'));

    // Orders buttons
    const searchOrdersBtn = document.getElementById('searchOrdersBtn');
    const searchOrdersByTimeCheckbox = document.getElementById('searchOrdersByTimeCheckbox');
    const ordersDateRangeContainer = document.getElementById('ordersDateRangeContainer');

    if (searchOrdersBtn) {
        searchOrdersBtn.addEventListener('click', loadAllOrders);
    }
    if (searchOrdersByTimeCheckbox && ordersDateRangeContainer) {
        searchOrdersByTimeCheckbox.addEventListener('change', function () {
            if (this.checked) {
                ordersDateRangeContainer.style.display = 'flex';
            } else {
                ordersDateRangeContainer.style.display = 'none';
            }
        });
    }

    // Filter inputs for orders - search on Enter key (with debouncing)
    const orderFilterInputs = ['filterOrderNumberForOrders', 'filterOrderCustomerName', 'filterOrderCustomerPhone', 'filterOrderTableNumber', 'filterOrderBranch', 'filterOrderCashier', 'filterOrderStatus'];
    const debouncedLoadOrders = window.PerformanceUtils ? window.PerformanceUtils.debounce(loadAllOrders, 300) : loadAllOrders;
    orderFilterInputs.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    debouncedLoadOrders();
                }
            });
        }
    });

    // Category buttons
    document.getElementById('addCategoryBtn').addEventListener('click', () => openCategoryModal());
    document.getElementById('saveCategoryBtn').addEventListener('click', saveCategory);

    // Product buttons
    const addProductBtn = document.getElementById('addProductBtn');
    const saveProductBtn = document.getElementById('saveProductBtn');

    if (addProductBtn) {
        addProductBtn.addEventListener('click', () => {
            console.log('Add product button clicked');
            openProductModal();
        });
    } else {
        console.error('addProductBtn not found!');
    }

    if (saveProductBtn) {
        saveProductBtn.addEventListener('click', () => {
            console.log('Save product button clicked');
            saveProduct();
        });
    } else {
        console.error('saveProductBtn not found!');
    }

    // Product search input
    const productSearchInput = document.getElementById('productSearchInput');
    if (productSearchInput) {
        // Use debounce for better performance
        const debouncedSearch = window.PerformanceUtils ? window.PerformanceUtils.debounce(filterProducts, 300) : filterProducts;
        productSearchInput.addEventListener('input', function () {
            productSearchQuery = this.value.trim().toLowerCase();
            debouncedSearch();
        });
    }

    // Image upload preview
    const imageInput = document.getElementById('productImageInput');
    if (imageInput) {
        imageInput.addEventListener('change', handleImageSelect);
    }

    // Remove image button
    const removeImageBtn = document.getElementById('removeImageBtn');
    if (removeImageBtn) {
        removeImageBtn.addEventListener('click', handleRemoveImage);
    }

    // Sizes checkbox
    const hasSizesInput = document.getElementById('productHasSizesInput');
    const sizesSection = document.getElementById('sizesSection');
    const priceInput = document.getElementById('productPriceInput');
    if (hasSizesInput && sizesSection) {
        hasSizesInput.addEventListener('change', function () {
            if (this.checked) {
                sizesSection.classList.remove('hidden');
                // Disable main price input when sizes are enabled
                if (priceInput) {
                    priceInput.disabled = true;
                    priceInput.value = '';
                }
            } else {
                sizesSection.classList.add('hidden');
                // Enable main price input when sizes are disabled
                if (priceInput) {
                    priceInput.disabled = false;
                }
                // Clear size inputs
                document.getElementById('productPriceSInput').value = '';
                document.getElementById('productPriceMInput').value = '';
                document.getElementById('productPriceLInput').value = '';
            }
        });
    }

    // Reports
    const dailyReportBtn = document.getElementById('dailyReportBtn');
    const weeklyReportBtn = document.getElementById('weeklyReportBtn');
    const monthlyReportBtn = document.getElementById('monthlyReportBtn');
    const loadDailyReportBtn = document.getElementById('loadDailyReportBtn');
    const loadWeeklyReportBtn = document.getElementById('loadWeeklyReportBtn');
    const loadMonthlyReportBtn = document.getElementById('loadMonthlyReportBtn');

    if (dailyReportBtn) {
        dailyReportBtn.addEventListener('click', () => showReportType('daily'));
    }
    if (weeklyReportBtn) {
        weeklyReportBtn.addEventListener('click', () => showReportType('weekly'));
    }
    if (monthlyReportBtn) {
        monthlyReportBtn.addEventListener('click', () => showReportType('monthly'));
    }
    if (loadDailyReportBtn) {
        loadDailyReportBtn.addEventListener('click', loadDailyReport);
    }
    if (loadWeeklyReportBtn) {
        loadWeeklyReportBtn.addEventListener('click', loadWeeklyReport);
    }
    if (loadMonthlyReportBtn) {
        loadMonthlyReportBtn.addEventListener('click', loadMonthlyReport);
    }

    // Settings
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);

    // Printer selection
    const refreshPrintersBtn = document.getElementById('refreshPrintersBtn');
    if (refreshPrintersBtn) {
        refreshPrintersBtn.addEventListener('click', loadAvailablePrinters);
    }

    loadSettings();

    // Shift Settings
    const numberOfShiftsSelect = document.getElementById('numberOfShifts');
    if (numberOfShiftsSelect) {
        numberOfShiftsSelect.addEventListener('change', function () {
            const shift3Section = document.getElementById('shift3Section');
            if (this.value === '3') {
                shift3Section.classList.remove('hidden');
            } else {
                shift3Section.classList.add('hidden');
            }
        });
    }

    const saveShiftSettingsBtn = document.getElementById('saveShiftSettingsBtn');
    if (saveShiftSettingsBtn) {
        saveShiftSettingsBtn.addEventListener('click', saveShiftSettings);
    }

    const loadShiftReportBtn = document.getElementById('loadShiftReportBtn');
    if (loadShiftReportBtn) {
        loadShiftReportBtn.addEventListener('click', loadShiftReport);
    }

    // Set today's date as default
    const shiftReportDate = document.getElementById('shiftReportDate');
    if (shiftReportDate) {
        shiftReportDate.value = new Date().toISOString().split('T')[0];
    }

    // Backup
    const downloadBackupBtn = document.getElementById('downloadBackupBtn');
    if (downloadBackupBtn) {
        downloadBackupBtn.addEventListener('click', () => {
            window.location.href = '/api/backup/download';
        });
    }

    const downloadMenuBackupBtn = document.getElementById('downloadMenuBackupBtn');
    if (downloadMenuBackupBtn) {
        downloadMenuBackupBtn.addEventListener('click', () => {
            window.location.href = '/api/backup/download-menu';
        });
    }

    const restoreMenuInput = document.getElementById('restoreMenuInput');
    if (restoreMenuInput) {
        restoreMenuInput.addEventListener('change', handleRestoreMenu);
    }

    const restoreFullInput = document.getElementById('restoreFullInput');
    if (restoreFullInput) {
        restoreFullInput.addEventListener('change', handleRestoreFull);
    }

    // Receipt Settings
    const saveReceiptSettingsBtn = document.getElementById('saveReceiptSettingsBtn');
    if (saveReceiptSettingsBtn) {
        saveReceiptSettingsBtn.addEventListener('click', saveReceiptSettings);
    }

    const uploadLogoBtn = document.getElementById('uploadLogoBtn');
    if (uploadLogoBtn) {
        uploadLogoBtn.addEventListener('click', uploadLogo);
    }
}

// Login
// Show tab
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.add('hidden'));

    // Show selected tab
    document.getElementById(`${tabName}Section`).classList.remove('hidden');
    const btn = document.getElementById(`${tabName}Tab`);
    // Update tab button styling (light mode)
    document.querySelectorAll('[id$="Tab"]').forEach(tabBtn => {
        tabBtn.classList.remove('bg-blue-50', 'border-blue-200', 'text-blue-700');
        tabBtn.classList.add('bg-gray-50', 'border-gray-200', 'text-gray-700');
    });
    btn.classList.remove('bg-gray-50', 'border-gray-200', 'text-gray-700');
    btn.classList.add('bg-blue-50', 'border-blue-200', 'text-blue-700');

    // Load data when switching tabs
    if (tabName === 'statistics') {
        loadStatistics();
    } else if (tabName === 'categories') {
        loadCategories();
    } else if (tabName === 'products') {
        loadProducts();
    } else if (tabName === 'reports') {
        // Show daily report by default
        showReportType('daily');
        // Set today's date as default
        const reportDate = document.getElementById('reportDate');
        if (reportDate && !reportDate.value) {
            reportDate.value = new Date().toISOString().split('T')[0];
        }
    } else if (tabName === 'orders') {
        loadAllOrders();
    } else if (tabName === 'settings') {
        loadSettings();
    } else if (tabName === 'shifts') {
        loadShiftSettings();
        loadShiftReport();
    } else if (tabName === 'backup') {
        // No data to load for backup tab
    }
}

// Load data
async function loadData() {
    try {
        await Promise.all([
            loadCategories(),
            loadProducts(),
            loadStatistics()
        ]);
        // Start network monitoring (auto-refresh every 5 seconds)
        startNetworkMonitoring();
        setupWebSocket();
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

// Load network information
let currentNetworkIP = null;
let networkCheckInterval = null;

async function loadNetworkInfo() {
    try {
        const response = await fetch('/api/admin/network/info');
        if (response.ok) {
            const networkInfo = await response.json();
            const networkInfoDiv = document.getElementById('networkInfo');
            if (networkInfoDiv) {
                const isLocalhost = networkInfo.local_ip === '127.0.0.1' || networkInfo.local_ip === 'localhost';

                // Check if IP changed
                const ipChanged = currentNetworkIP && currentNetworkIP !== networkInfo.local_ip;
                currentNetworkIP = networkInfo.local_ip;

                let html = `
                    <div class="flex flex-wrap items-start gap-4">
                        <!-- IP Address -->
                        <div class="flex items-center gap-2">
                            <span class="text-gray-500">🌐 IP الشبكة:</span>
                            <span class="font-semibold text-blue-600 bg-blue-50 px-2 py-1 rounded" dir="ltr">${networkInfo.local_ip}</span>
                            ${ipChanged ? '<span class="text-xs text-green-600 animate-pulse">● تم التحديث</span>' : ''}
                        </div>

                        <!-- Cashier URL with QR -->
                        <div class="flex items-center gap-2">
                            <span class="text-gray-500">📱 الكاشير:</span>
                            <span class="font-semibold text-green-600 bg-green-50 px-2 py-1 rounded cursor-pointer hover:bg-green-100" 
                                  onclick="copyToClipboard('${networkInfo.main_server_url}')" 
                                  title="اضغط للنسخ" dir="ltr">${networkInfo.main_server_url}</span>
                            <button onclick="showQRCode('${networkInfo.main_server_url}', 'الكاشير')" 
                                    class="px-2 py-1 bg-green-100 text-green-700 rounded hover:bg-green-200 transition text-xs font-bold"
                                    title="عرض QR Code">
                                QR
                            </button>
                        </div>

                        <!-- Tablet URL with QR -->
                        <div class="flex items-center gap-2">
                            <span class="text-gray-500">📱 التابلت:</span>
                            <span class="font-semibold text-purple-600 bg-purple-50 px-2 py-1 rounded cursor-pointer hover:bg-purple-100" 
                                  onclick="copyToClipboard('${networkInfo.tablet_server_url}')" 
                                  title="اضغط للنسخ" dir="ltr">${networkInfo.tablet_server_url}</span>
                            <button onclick="showQRCode('${networkInfo.tablet_server_url}', 'التابلت')" 
                                    class="px-2 py-1 bg-purple-100 text-purple-700 rounded hover:bg-purple-200 transition text-xs font-bold"
                                    title="عرض QR Code">
                                QR
                            </button>
                        </div>
                    </div>
                `;

                if (isLocalhost) {
                    html += `
                        <div class="w-full mt-2 text-xs text-orange-600 bg-orange-50 p-2 rounded border border-orange-200">
                            ⚠ تنبيه: لم يتم اكتشاف IP الشبكة. يرجى التأكد من الاتصال بالواي فاي لتشغيل التابلت.
                        </div>
                    `;
                }

                networkInfoDiv.innerHTML = html;

                // Show notification if IP changed
                if (ipChanged && window.notificationManager) {
                    window.notificationManager.success(`تم تحديث IP الشبكة إلى: ${networkInfo.local_ip}`);
                }
            }
        }
    } catch (error) {
        console.error('Error loading network info:', error);
        const networkInfoDiv = document.getElementById('networkInfo');
        if (networkInfoDiv) {
            networkInfoDiv.innerHTML = '<span class="text-red-500">خطأ في تحميل معلومات الشبكة</span>';
        }
    }
}

// Start monitoring network changes
function startNetworkMonitoring() {
    // Initial load
    loadNetworkInfo();

    // Check every 5 seconds for network changes
    if (networkCheckInterval) {
        clearInterval(networkCheckInterval);
    }

    networkCheckInterval = setInterval(() => {
        loadNetworkInfo();
    }, 5000); // Check every 5 seconds
}

// Stop monitoring when leaving the page
window.addEventListener('beforeunload', () => {
    if (networkCheckInterval) {
        clearInterval(networkCheckInterval);
    }
});

// Copy to clipboard function
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        if (window.notificationManager) {
            window.notificationManager.success('تم النسخ: ' + text);
        } else {
            console.log('تم النسخ: ' + text);
        }
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Show QR Code Modal
function showQRCode(url, title) {
    const modal = document.getElementById('qrCodeModal');
    const qrContainer = document.getElementById('qrCodeContainer');
    const qrModalTitle = document.getElementById('qrModalTitle');
    const qrUrlDisplay = document.getElementById('qrUrlDisplay');

    // Set title and URL
    qrModalTitle.textContent = `QR Code - ${title}`;
    qrUrlDisplay.textContent = url;

    // Clear previous QR code
    qrContainer.innerHTML = '';

    // Generate new QR code
    try {
        new QRCode(qrContainer, {
            text: url,
            width: 200,
            height: 200,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.H
        });

        // Show modal
        modal.classList.remove('hidden');
    } catch (error) {
        console.error('Error generating QR code:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في إنشاء QR Code');
        }
    }
}

// Close QR Code Modal
function closeQRModal() {
    const modal = document.getElementById('qrCodeModal');
    modal.classList.add('hidden');
}

// Setup WebSocket for real-time updates
function setupWebSocket() {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        window.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        window.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'categories_updated' || data.type === 'products_updated') {
                    loadCategories();
                    loadProducts();
                }
            } catch (e) {
                // Ignore parse errors
            }
        };

        window.ws.onerror = () => {
            // Silently fail, will retry on next action
        };

        window.ws.onclose = () => {
            // Reconnect after 5 seconds
            setTimeout(setupWebSocket, 5000);
        };
    } catch (e) {
        // WebSocket not available, continue without it
    }
}

// Load statistics
async function loadStatistics() {
    try {
        const fetchFn = window.PerformanceUtils ? window.PerformanceUtils.cachedFetch : fetch;
        const response = await fetchFn('/api/admin/statistics', {}, 'statistics');

        if (!response.ok) {
            console.error('Failed to load statistics:', response.status);
            // Set default values if API fails
            const todaySalesEl = document.getElementById('todaySales');
            const todayOrdersEl = document.getElementById('todayOrders');
            const totalRevenueEl = document.getElementById('totalRevenue');
            const totalOrdersEl = document.getElementById('totalOrders');

            if (todaySalesEl) todaySalesEl.textContent = '0.00';
            if (todayOrdersEl) todayOrdersEl.textContent = '0 طلب';
            if (totalRevenueEl) totalRevenueEl.textContent = '0.00';
            if (totalOrdersEl) totalOrdersEl.textContent = '0 طلب';
            return;
        }

        const stats = await response.json();

        if (!stats || !stats.today || !stats.all_time) {
            console.error('Invalid statistics data:', stats);
            return;
        }

        // Update today's stats
        const todaySalesEl = document.getElementById('todaySales');
        const todayOrdersEl = document.getElementById('todayOrders');
        if (todaySalesEl) todaySalesEl.textContent = parseFloat(stats.today.total_sales || 0).toFixed(2);
        if (todayOrdersEl) todayOrdersEl.textContent = `${stats.today.order_count || 0} طلب`;

        // Update all time stats
        const totalRevenueEl = document.getElementById('totalRevenue');
        const totalOrdersEl = document.getElementById('totalOrders');
        if (totalRevenueEl) totalRevenueEl.textContent = parseFloat(stats.all_time.total_revenue || 0).toFixed(2);
        if (totalOrdersEl) totalOrdersEl.textContent = `${stats.all_time.total_orders || 0} طلب`;

        // Update pending orders
        const pendingOrdersEl = document.getElementById('pendingOrders');
        if (pendingOrdersEl) pendingOrdersEl.textContent = stats.pending_orders || 0;

        // Update total products and categories
        const totalProductsEl = document.getElementById('totalProducts');
        const totalCategoriesEl = document.getElementById('totalCategories');
        if (totalProductsEl) totalProductsEl.textContent = stats.total_products || 0;
        if (totalCategoriesEl) totalCategoriesEl.textContent = `${stats.total_categories || 0} فئة`;

        // Render recent orders as cards
        const recentOrdersCards = document.getElementById('recentOrdersCards');
        if (recentOrdersCards) {
            if (stats.recent_orders && stats.recent_orders.length > 0) {
                // Use DocumentFragment for better performance
                const fragment = document.createDocumentFragment();
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = stats.recent_orders.map(order => {
                    const tableDisplay = (order.table_number && order.table_number > 0) ? order.table_number : 'سفري';
                    return `
                        <div class="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-blue-300 transition">
                            <div class="flex justify-between items-center">
                                <div>
                                    <div class="font-bold text-gray-800">طلب #${order.order_number}</div>
                                    <div class="text-sm text-gray-600">${tableDisplay}</div>
                                </div>
                                <div class="text-left">
                                    <div class="font-bold text-blue-600">${parseFloat(order.total_amount || 0).toFixed(2)}</div>
                                    <span class="px-2 py-1 rounded-full text-xs ${order.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-orange-100 text-orange-800'}">
                                        ${order.status === 'completed' ? 'مكتمل' : 'قيد الانتظار'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
                fragment.appendChild(tempDiv);
                recentOrdersCards.innerHTML = '';
                Array.from(tempDiv.children).forEach(child => recentOrdersCards.appendChild(child));
            } else {
                recentOrdersCards.innerHTML = '<div class="text-center py-8 text-gray-400">لا توجد طلبات</div>';
            }
        }

        // Render top products as cards
        const topProductsCards = document.getElementById('topProductsCards');
        if (topProductsCards) {
            if (stats.top_products && stats.top_products.length > 0) {
                // Use DocumentFragment for better performance
                const fragment2 = document.createDocumentFragment();
                const tempDiv2 = document.createElement('div');
                tempDiv2.innerHTML = stats.top_products.map(product => `
                    <div class="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-blue-300 transition">
                        <div class="flex justify-between items-center">
                            <div class="font-bold text-gray-800">${product.product_name}</div>
                            <div class="text-left">
                                <div class="text-sm text-gray-600">الكمية: ${product.total_quantity || 0}</div>
                                <div class="font-bold text-green-600">${parseFloat(product.total_revenue || 0).toFixed(2)}</div>
                            </div>
                        </div>
                    </div>
                `).join('');
                fragment2.appendChild(tempDiv2);
                topProductsCards.innerHTML = '';
                Array.from(tempDiv2.children).forEach(child => topProductsCards.appendChild(child));
            } else {
                topProductsCards.innerHTML = '<div class="text-center py-8 text-gray-400">لا توجد بيانات</div>';
            }
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Load categories
async function loadCategories() {
    try {
        console.log('Loading categories...');
        const response = await fetch('/api/categories');
        console.log('Categories response status:', response.status);

        if (!response.ok) {
            console.error('Failed to load categories:', response.status, await response.text());
            const tbody = document.getElementById('categoriesTable');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center py-8 text-red-500">خطأ في تحميل الفئات</td></tr>';
            }
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
        const tbody = document.getElementById('categoriesTable');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center py-8 text-red-500">خطأ في تحميل الفئات: ' + error.message + '</td></tr>';
        }
    }
}

// Render categories as cards
function renderCategories() {
    const grid = document.getElementById('categoriesGrid');
    if (!grid) {
        console.error('categoriesGrid element not found');
        return;
    }

    if (!categories || categories.length === 0) {
        grid.innerHTML = '<div class="col-span-3 text-center py-12 text-gray-400">لا توجد فئات</div>';
        return;
    }

    grid.innerHTML = categories.map(cat => `
        <div class="category-card">
            <div class="flex justify-between items-center">
                <div>
                    <div class="text-lg font-bold text-gray-800 mb-1">${cat.name}</div>
                    <div class="text-sm text-gray-500">ID: ${cat.id}</div>
                </div>
                <div class="flex gap-2">
                    <button onclick="editCategory(${cat.id})" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold text-sm transition">
                        تعديل
                    </button>
                    <button onclick="deleteCategory(${cat.id})" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold text-sm transition">
                        حذف
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// Load products
async function loadProducts() {
    try {
        console.log('Loading products...');
        const response = await fetch('/api/products');
        console.log('Products response status:', response.status);

        if (!response.ok) {
            console.error('Failed to load products:', response.status, await response.text());
            const tbody = document.getElementById('productsTable');
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-red-500">خطأ في تحميل المنتجات</td></tr>';
            }
            return;
        }

        products = await response.json();
        console.log('Products loaded:', products);

        if (!Array.isArray(products)) {
            console.error('Products is not an array:', products);
            products = [];
        }

        renderProducts();
    } catch (error) {
        console.error('Error loading products:', error);
        const tbody = document.getElementById('productsTable');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-red-500">خطأ في تحميل المنتجات: ' + error.message + '</td></tr>';
        }
    }
}

// Filter products based on search query
function filterProducts() {
    renderProducts();
}

// Render products as cards
function renderProducts() {
    const grid = document.getElementById('productsGrid');
    if (!grid) {
        console.error('productsGrid element not found');
        return;
    }

    if (!products || products.length === 0) {
        grid.innerHTML = '<div class="col-span-4 text-center py-12 text-gray-400">لا توجد منتجات</div>';
        return;
    }

    // Filter products based on search query
    let filteredProducts = products;
    if (productSearchQuery) {
        filteredProducts = products.filter(prod => {
            const productName = (prod.name || '').toLowerCase();
            const categoryName = (prod.category_name || '').toLowerCase();
            return productName.includes(productSearchQuery) || categoryName.includes(productSearchQuery);
        });
    }

    if (filteredProducts.length === 0) {
        grid.innerHTML = '<div class="col-span-4 text-center py-12 text-gray-400">لا توجد منتجات تطابق البحث</div>';
        return;
    }

    grid.innerHTML = filteredProducts.map(prod => {
        console.log('Rendering product:', prod.name, 'has_sizes:', prod.has_sizes, 'price_s:', prod.price_s, 'price_m:', prod.price_m, 'price_l:', prod.price_l);

        // Check if product has sizes (either has_sizes flag or has any size prices)
        const hasSizes = prod.has_sizes === true ||
            (prod.price_s && prod.price_s > 0) ||
            (prod.price_m && prod.price_m > 0) ||
            (prod.price_l && prod.price_l > 0);

        const priceDisplay = hasSizes
            ? (prod.price_s ? `S: ${prod.price_s.toFixed(0)}` : '') +
            (prod.price_m ? (prod.price_s ? ' | ' : '') + `M: ${prod.price_m.toFixed(0)}` : '') +
            (prod.price_l ? ' | ' + `L: ${prod.price_l.toFixed(0)}` : '')
            : `${prod.price.toFixed(2)}`;

        return `
            <div class="product-card">
                <div class="mb-3">
                    ${prod.image_path && prod.image_path.trim() !== '' ?
                `<img src="${prod.image_path.startsWith('/') ? prod.image_path : '/' + prod.image_path}" alt="${prod.name}" class="w-full h-32 object-cover rounded-lg" onerror="this.src='/static/images/placeholder.png'">` :
                '<div class="w-full h-32 bg-gray-200 rounded-lg flex items-center justify-center text-sm text-gray-400">لا توجد صورة</div>'}
                </div>
                <div class="mb-2">
                    <div class="font-bold text-gray-800 text-sm mb-1">${prod.name}</div>
                    <div class="text-xs text-gray-600 mb-1">${prod.category_name || 'بدون فئة'}</div>
                    <div class="text-sm font-semibold text-blue-600">${priceDisplay}</div>
                    ${hasSizes ? '<div class="text-xs text-green-600 mt-1">✓ يحتوي على أحجام</div>' : ''}
                </div>
                <div class="flex items-center justify-between mb-3">
                    <span class="px-2 py-1 rounded-full text-xs font-semibold ${prod.enabled ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${prod.enabled ? 'مفعل' : 'معطل'}
                    </span>
                    ${prod.hidden_on_tablet ? '<span class="px-2 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-800 mr-1">مخفي من التابلت</span>' : ''}
                    <span class="text-xs text-gray-500">ID: ${prod.id}</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="editProduct(${prod.id})" class="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold text-sm transition">
                        تعديل
                    </button>
                    <button onclick="toggleProduct(${prod.id}, ${prod.enabled})" class="px-3 py-2 ${prod.enabled ? 'bg-yellow-600 hover:bg-yellow-700' : 'bg-green-600 hover:bg-green-700'} text-white rounded-lg font-semibold text-sm transition">
                        ${prod.enabled ? 'تعطيل' : 'تفعيل'}
                    </button>
                    <button onclick="deleteProduct(${prod.id})" class="px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold text-sm transition">
                        حذف
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// Category modal
function openCategoryModal(categoryId = null) {
    currentCategoryId = categoryId;
    const modal = document.getElementById('categoryModal');
    const title = document.getElementById('categoryModalTitle');
    const input = document.getElementById('categoryNameInput');

    if (categoryId) {
        const category = categories.find(c => c.id === categoryId);
        title.textContent = 'تعديل فئة';
        input.value = category.name;
    } else {
        title.textContent = 'إضافة فئة';
        input.value = '';
    }

    modal.classList.remove('hidden');
}

function closeCategoryModal() {
    document.getElementById('categoryModal').classList.add('hidden');
    currentCategoryId = null;
}

async function saveCategory() {
    const name = document.getElementById('categoryNameInput').value.trim();
    if (!name) {
        notificationManager.warning('الرجاء إدخال اسم الفئة');
        return;
    }

    try {
        // Use executeCommand for cloud control
        const commandType = currentCategoryId ? 'edit_category' : 'add_category';
        const payload = { name: name };

        if (currentCategoryId) {
            payload.id = currentCategoryId;
        }

        // Execute command via WebSocket
        await executeCommand(commandType, payload);

        closeCategoryModal();
        await loadCategories();
        notificationManager.success('تم حفظ الفئة بنجاح');

    } catch (error) {
        console.error('Error saving category:', error);
        // Error already shown by executeCommand
    }
}

async function deleteCategory(id) {
    if (!await notificationManager.confirm('هل أنت متأكد من حذف هذه الفئة؟')) return;

    try {
        const response = await fetch(`/api/categories/${id}`, { method: 'DELETE' });
        if (response.ok) {
            await loadCategories();
            // Broadcast update via WebSocket
            if (window.ws && window.ws.readyState === WebSocket.OPEN) {
                window.ws.send(JSON.stringify({ type: 'categories_updated' }));
            }
        } else {
            const error = await response.json();
            notificationManager.error(error.detail || 'خطأ في حذف الفئة');
        }
    } catch (error) {
        console.error('Error deleting category:', error);
        notificationManager.error('خطأ في حذف الفئة');
    }
}

// Product modal
function openProductModal(productId = null) {
    console.log('openProductModal called with productId:', productId);
    currentProductId = productId;
    isImageDeleted = false;
    const modal = document.getElementById('productModal');
    const title = document.getElementById('productModalTitle');

    if (!modal) {
        console.error('Product modal not found!');
        notificationManager.error('خطأ: لم يتم العثور على نافذة المنتج');
        return;
    }

    if (!title) {
        console.error('Product modal title not found!');
    }

    // Update category select - make sure categories are loaded
    const categorySelect = document.getElementById('productCategoryInput');
    if (categorySelect) {
        if (categories && categories.length > 0) {
            categorySelect.innerHTML = '<option value="">اختر الفئة</option>' + categories.map(cat =>
                `<option value="${cat.id}">${cat.name}</option>`
            ).join('');
        } else {
            // Load categories if not loaded
            loadCategories().then(() => {
                if (categories && categories.length > 0) {
                    categorySelect.innerHTML = '<option value="">اختر الفئة</option>' + categories.map(cat =>
                        `<option value="${cat.id}">${cat.name}</option>`
                    ).join('');
                } else {
                    categorySelect.innerHTML = '<option value="">لا توجد فئات - أضف فئة أولاً</option>';
                }
            });
        }
    }

    // Reset image preview
    const imagePreview = document.getElementById('imagePreview');
    const previewImg = document.getElementById('previewImg');
    const imageInput = document.getElementById('productImageInput');
    const imagePathInput = document.getElementById('productImagePath');
    const priceInput = document.getElementById('productPriceInput');

    if (imagePreview) imagePreview.classList.add('hidden');
    if (imageInput) imageInput.value = '';
    if (imagePathInput) imagePathInput.value = '';

    if (productId) {
        const product = products.find(p => p.id === productId);
        if (!product) {
            notificationManager.error('المنتج غير موجود');
            return;
        }
        title.textContent = 'تعديل منتج';
        document.getElementById('productNameInput').value = product.name || '';
        if (priceInput) priceInput.value = product.price || '';
        document.getElementById('productCategoryInput').value = product.category_id || '';
        document.getElementById('productEnabledInput').checked = product.enabled !== false;
        document.getElementById('productHiddenOnTabletInput').checked = product.hidden_on_tablet === true;

        // Handle sizes - check multiple ways
        const hasSizes = product.has_sizes === true ||
            product.has_sizes === 1 ||
            product.has_sizes === "1" ||
            (product.price_s && parseFloat(product.price_s) > 0) ||
            (product.price_m && parseFloat(product.price_m) > 0) ||
            (product.price_l && parseFloat(product.price_l) > 0);
        console.log('Loading product for edit:', product.name, 'hasSizes:', hasSizes, 'has_sizes:', product.has_sizes, 'price_s:', product.price_s, 'price_m:', product.price_m, 'price_l:', product.price_l);
        document.getElementById('productHasSizesInput').checked = hasSizes;
        if (hasSizes) {
            document.getElementById('sizesSection').classList.remove('hidden');
            document.getElementById('productPriceSInput').value = product.price_s || '';
            document.getElementById('productPriceMInput').value = product.price_m || '';
            document.getElementById('productPriceLInput').value = product.price_l || '';
            // Disable main price input when sizes are enabled
            if (priceInput) {
                priceInput.disabled = true;
                priceInput.value = '';
            }
        } else {
            document.getElementById('sizesSection').classList.add('hidden');
            document.getElementById('productPriceSInput').value = '';
            document.getElementById('productPriceMInput').value = '';
            document.getElementById('productPriceLInput').value = '';
            // Enable main price input when sizes are disabled
            if (priceInput) {
                priceInput.disabled = false;
            }
        }

        // Show existing image if available
        if (product.image_path && imagePreview && previewImg) {
            previewImg.src = product.image_path;
            imagePreview.classList.remove('hidden');
            if (imagePathInput) imagePathInput.value = product.image_path;
        }
    } else {
        title.textContent = 'إضافة منتج';
        document.getElementById('productNameInput').value = '';
        if (priceInput) priceInput.value = '';
        document.getElementById('productCategoryInput').value = categories && categories.length > 0 ? categories[0].id : '';
        document.getElementById('productEnabledInput').checked = true;
        document.getElementById('productHiddenOnTabletInput').checked = false;
        document.getElementById('productHasSizesInput').checked = false;
        document.getElementById('sizesSection').classList.add('hidden');
        document.getElementById('productPriceSInput').value = '';
        document.getElementById('productPriceMInput').value = '';
        document.getElementById('productPriceLInput').value = '';
        // Enable main price input
        if (priceInput) {
            priceInput.disabled = false;
        }
    }

    if (modal) {
        modal.classList.remove('hidden');
    } else {
        console.error('Product modal not found!');
    }
}

function closeProductModal() {
    const modal = document.getElementById('productModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    currentProductId = null;
    // Reset image preview
    const imagePreview = document.getElementById('imagePreview');
    const imageInput = document.getElementById('productImageInput');
    const imagePathInput = document.getElementById('productImagePath');
    if (imagePreview) imagePreview.classList.add('hidden');
    if (imageInput) imageInput.value = '';
    if (imagePathInput) imagePathInput.value = '';
}

// Make closeProductModal globally accessible
window.closeProductModal = closeProductModal;

// Handle image selection
function handleImageSelect(event) {
    const file = event.target.files[0];
    const imagePreview = document.getElementById('imagePreview');
    const previewImg = document.getElementById('previewImg');
    const imagePathInput = document.getElementById('productImagePath');

    if (file) {
        // Show preview
        const reader = new FileReader();
        reader.onload = function (e) {
            if (previewImg) {
                previewImg.src = e.target.result;
                if (imagePreview) imagePreview.classList.remove('hidden');
            }
        };
        reader.readAsDataURL(file);
    } else {
        if (imagePreview) imagePreview.classList.add('hidden');
        if (imagePathInput) imagePathInput.value = '';
    }
}

// Handle remove image
function handleRemoveImage() {
    const imagePreview = document.getElementById('imagePreview');
    const imageInput = document.getElementById('productImageInput');
    const imagePathInput = document.getElementById('productImagePath');

    if (imagePreview) imagePreview.classList.add('hidden');
    if (imageInput) imageInput.value = '';
    if (imagePathInput) imagePathInput.value = '';

    isImageDeleted = true;
}

async function saveProduct() {
    console.log('saveProduct called');
    try {
        const nameInput = document.getElementById('productNameInput');
        const priceInput = document.getElementById('productPriceInput');
        const categoryInput = document.getElementById('productCategoryInput');
        const imageInput = document.getElementById('productImageInput');
        const imagePathInput = document.getElementById('productImagePath');
        const enabledInput = document.getElementById('productEnabledInput');
        const hiddenOnTabletInput = document.getElementById('productHiddenOnTabletInput');
        const hasSizesInput = document.getElementById('productHasSizesInput');

        if (!hiddenOnTabletInput) {
            console.error('CRITICAL: productHiddenOnTabletInput not found in DOM');
            alert('Error: productHiddenOnTabletInput not found');
            return;
        }

        const name = nameInput.value.trim();
        const priceInputValue = priceInput ? priceInput.value : '0';
        const categoryIdValue = categoryInput.value;
        const enabled = enabledInput.checked;
        const hiddenOnTablet = hiddenOnTabletInput.checked;
        const hasSizes = hasSizesInput.checked;

        console.log('Form values:', { name, priceInputValue, categoryIdValue, enabled, hiddenOnTablet, hasSizes });

        if (!name) {
            notificationManager.warning('الرجاء إدخال اسم المنتج');
            return;
        }

        if (!categoryIdValue || categoryIdValue === '') {
            notificationManager.warning('الرجاء اختيار فئة للمنتج');
            return;
        }

        const categoryId = parseInt(categoryIdValue);
        if (isNaN(categoryId)) {
            notificationManager.error('فئة غير صحيحة');
            return;
        }

        // Handle price - if has sizes, use first available size price, otherwise use single price
        let price = 0;
        let priceS = null;
        let priceM = null;
        let priceL = null;

        if (hasSizes) {
            // Get any entered size prices (all are optional)
            const sValue = document.getElementById('productPriceSInput').value.trim();
            const mValue = document.getElementById('productPriceMInput').value.trim();
            const lValue = document.getElementById('productPriceLInput').value.trim();

            priceS = sValue ? parseFloat(sValue) : null;
            priceM = mValue ? parseFloat(mValue) : null;
            priceL = lValue ? parseFloat(lValue) : null;

            // At least one size must have a price
            if (!priceS && !priceM && !priceL) {
                notificationManager.warning('الرجاء إدخال سعر واحد على الأقل (S أو M أو L)');
                return;
            }

            // Use first available price as default price for database
            if (priceS) price = priceS;
            else if (priceM) price = priceM;
            else if (priceL) price = priceL;
        } else {
            price = parseFloat(priceInputValue);
            if (isNaN(price) || price <= 0) {
                notificationManager.warning('الرجاء إدخال سعر صحيح');
                return;
            }
        }

        try {
            let imagePath = imagePathInput ? imagePathInput.value : '';

            // Create or update product first (without image)
            const url = currentProductId
                ? `/api/products/${currentProductId}`
                : '/api/products';
            const method = currentProductId ? 'PUT' : 'POST';

            console.log('Sending request to:', url, method);

            const body = {
                name,
                price,
                category_id: categoryId,
                enabled,
                hidden_on_tablet: hiddenOnTablet,
                has_sizes: hasSizes,
                ...(imagePath && { image_path: imagePath })
            };

            // If image was deleted and no new image path, send empty string to clear it
            if (isImageDeleted && !imagePath) {
                body.image_path = '';
            }

            // Always include size prices if has_sizes is true, even if null (to clear old values)
            if (hasSizes) {
                body.price_s = priceS;
                body.price_m = priceM;
                body.price_l = priceL;
            }

            console.log('Request body:', body);

            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            console.log('Response status:', response.status);

            if (response.ok) {
                const product = await response.json();
                console.log('Product saved:', product);

                // Upload image if selected
                if (imageInput && imageInput.files.length > 0) {
                    console.log('Uploading image...');
                    const formData = new FormData();
                    formData.append('file', imageInput.files[0]);

                    const uploadResponse = await fetch(`/api/products/${product.id}/upload-image`, {
                        method: 'POST',
                        body: formData
                    });

                    if (!uploadResponse.ok) {
                        console.error('Image upload failed');
                        notificationManager.warning('تم حفظ المنتج ولكن فشل رفع الصورة');
                    } else {
                        console.log('Image uploaded successfully');
                    }
                }

                closeProductModal();
                await loadProducts();
                notificationManager.success('تم حفظ المنتج بنجاح');

                // Broadcast update via WebSocket
                if (window.ws && window.ws.readyState === WebSocket.OPEN) {
                    window.ws.send(JSON.stringify({ type: 'products_updated' }));
                }
            } else {
                const error = await response.json();
                console.error('Error response:', error);
                notificationManager.error(error.detail || 'خطأ في حفظ المنتج');
                alert('Error saving product: ' + (error.detail || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error in saveProduct fetch:', error);
            notificationManager.error('خطأ في حفظ المنتج: ' + error.message);
            alert('Exception in saveProduct: ' + error.message);
        }
    } catch (e) {
        console.error('CRITICAL ERROR in saveProduct:', e);
        alert('Critical error in saveProduct: ' + e.message);
    }
}

async function toggleProduct(id, currentStatus) {
    try {
        const response = await fetch(`/api/products/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: !currentStatus })
        });

        if (response.ok) {
            await loadProducts();
            // Broadcast update via WebSocket
            if (window.ws && window.ws.readyState === WebSocket.OPEN) {
                window.ws.send(JSON.stringify({ type: 'products_updated' }));
            }
        } else {
            const error = await response.json();
            notificationManager.error(error.detail || 'خطأ في تحديث المنتج');
        }
    } catch (error) {
        console.error('Error toggling product:', error);
        notificationManager.error('خطأ في تحديث المنتج');
    }
}

async function deleteProduct(id) {
    if (!await notificationManager.confirm('هل أنت متأكد من حذف هذا المنتج؟')) return;

    try {
        const response = await fetch(`/api/products/${id}`, { method: 'DELETE' });
        if (response.ok) {
            await loadProducts();
            // Broadcast update via WebSocket
            if (window.ws && window.ws.readyState === WebSocket.OPEN) {
                window.ws.send(JSON.stringify({ type: 'products_updated' }));
            }
        } else {
            const error = await response.json();
            notificationManager.error(error.detail || 'خطأ في حذف المنتج');
        }
    } catch (error) {
        console.error('Error deleting product:', error);
        notificationManager.error('خطأ في حذف المنتج');
    }
}

// Reports
// Show report type
function showReportType(type) {
    // Hide all sections
    document.querySelectorAll('.report-section').forEach(section => section.classList.add('hidden'));

    // Reset all buttons
    document.getElementById('dailyReportBtn').className = 'px-6 py-3 bg-gray-50 border-2 border-gray-200 text-gray-700 rounded-lg hover:bg-gray-100 hover:border-gray-300 font-semibold transition';
    document.getElementById('weeklyReportBtn').className = 'px-6 py-3 bg-gray-50 border-2 border-gray-200 text-gray-700 rounded-lg hover:bg-gray-100 hover:border-gray-300 font-semibold transition';
    document.getElementById('monthlyReportBtn').className = 'px-6 py-3 bg-gray-50 border-2 border-gray-200 text-gray-700 rounded-lg hover:bg-gray-100 hover:border-gray-300 font-semibold transition';

    // Show selected section and highlight button
    if (type === 'daily') {
        document.getElementById('dailyReportSection').classList.remove('hidden');
        document.getElementById('dailyReportBtn').className = 'px-6 py-3 bg-blue-50 border-2 border-blue-200 text-blue-700 rounded-lg hover:bg-blue-100 hover:border-blue-300 font-semibold transition';
    } else if (type === 'weekly') {
        document.getElementById('weeklyReportSection').classList.remove('hidden');
        document.getElementById('weeklyReportBtn').className = 'px-6 py-3 bg-blue-50 border-2 border-blue-200 text-blue-700 rounded-lg hover:bg-blue-100 hover:border-blue-300 font-semibold transition';
    } else if (type === 'monthly') {
        document.getElementById('monthlyReportSection').classList.remove('hidden');
        document.getElementById('monthlyReportBtn').className = 'px-6 py-3 bg-blue-50 border-2 border-blue-200 text-blue-700 rounded-lg hover:bg-blue-100 hover:border-blue-300 font-semibold transition';
    }
}

// Load daily report
async function loadDailyReport() {
    const date = document.getElementById('reportDate').value || new Date().toISOString().split('T')[0];
    const content = document.getElementById('dailyReportContent');

    if (!content) return;

    content.innerHTML = '<div class="text-center py-8 text-gray-400">جاري التحميل...</div>';

    try {
        const response = await fetch(`/api/admin/reports/daily?report_date=${date}`);
        if (!response.ok) throw new Error('Failed to load report');

        const report = await response.json();

        const totalSales = parseFloat(report.total_sales || 0).toFixed(2);
        const orderCount = report.order_count || 0;

        let bestSellersHtml = '';
        if (report.best_sellers && report.best_sellers.length > 0) {
            bestSellersHtml = `
                <div class="mt-6">
                    <h3 class="text-lg font-bold text-gray-800 mb-4">أفضل المنتجات</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full border-collapse">
                            <thead>
                                <tr class="bg-gray-50 border-b-2 border-gray-200">
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">#</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">اسم المنتج</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">الكمية</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">الإيرادات</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${report.best_sellers.map((item, index) => `
                                    <tr class="border-b border-gray-200 hover:bg-gray-50 transition">
                                        <td class="px-4 py-3 text-right">${index + 1}</td>
                                        <td class="px-4 py-3 text-right font-semibold">${item.product_name}</td>
                                        <td class="px-4 py-3 text-right">${item.total_quantity}</td>
                                        <td class="px-4 py-3 text-right font-bold text-green-600">${parseFloat(item.total_revenue).toFixed(2)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        } else {
            bestSellersHtml = '<div class="text-center py-8 text-gray-400">لا توجد منتجات مباعة في هذا التاريخ</div>';
        }

        content.innerHTML = `
            <div class="space-y-6">
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-blue-50 border-2 border-blue-200 rounded-lg p-6">
                        <div class="text-sm text-gray-600 font-semibold mb-2">إجمالي المبيعات</div>
                        <div class="text-3xl font-bold text-blue-700">${totalSales}</div>
                    </div>
                    <div class="bg-green-50 border-2 border-green-200 rounded-lg p-6">
                        <div class="text-sm text-gray-600 font-semibold mb-2">عدد الطلبات</div>
                        <div class="text-3xl font-bold text-green-700">${orderCount}</div>
                    </div>
                </div>
                ${bestSellersHtml}
            </div>
        `;
    } catch (error) {
        console.error('Error loading daily report:', error);
        content.innerHTML = '<div class="text-center py-8 text-red-500">خطأ في تحميل التقرير</div>';
    }
}

// Load weekly report
async function loadWeeklyReport() {
    const week = document.getElementById('reportWeek').value;
    const content = document.getElementById('weeklyReportContent');

    if (!content || !week) {
        if (content) content.innerHTML = '<div class="text-center py-8 text-gray-400">الرجاء اختيار أسبوع</div>';
        return;
    }

    content.innerHTML = '<div class="text-center py-8 text-gray-400">جاري التحميل...</div>';

    try {
        // Parse week to get start and end dates
        const [year, weekNum] = week.split('-W');
        const startDate = getDateOfISOWeek(parseInt(weekNum), parseInt(year));
        const endDate = new Date(startDate);
        endDate.setDate(endDate.getDate() + 6);

        const startDateStr = startDate.toISOString().split('T')[0];
        const endDateStr = endDate.toISOString().split('T')[0];

        // Fetch daily breakdown for the week
        const response = await fetch(`/api/orders?start_date=${startDateStr}&end_date=${endDateStr}&status=completed`);
        if (!response.ok) throw new Error('Failed to load report');

        const orders = await response.json();

        const totalSales = orders.reduce((sum, order) => sum + parseFloat(order.total_amount || 0), 0).toFixed(2);
        const orderCount = orders.length;

        // Group by day
        const dailyBreakdown = {};
        orders.forEach(order => {
            const date = order.created_at.split('T')[0];
            if (!dailyBreakdown[date]) {
                dailyBreakdown[date] = { sales: 0, count: 0 };
            }
            dailyBreakdown[date].sales += parseFloat(order.total_amount || 0);
            dailyBreakdown[date].count += 1;
        });

        const days = Object.keys(dailyBreakdown).sort();

        content.innerHTML = `
            <div class="space-y-6">
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-blue-50 border-2 border-blue-200 rounded-lg p-6">
                        <div class="text-sm text-gray-600 font-semibold mb-2">إجمالي المبيعات</div>
                        <div class="text-3xl font-bold text-blue-700">${totalSales}</div>
                    </div>
                    <div class="bg-green-50 border-2 border-green-200 rounded-lg p-6">
                        <div class="text-sm text-gray-600 font-semibold mb-2">عدد الطلبات</div>
                        <div class="text-3xl font-bold text-green-700">${orderCount}</div>
                    </div>
                </div>
                <div>
                    <h3 class="text-lg font-bold text-gray-800 mb-4">التفصيل اليومي</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full border-collapse">
                            <thead>
                                <tr class="bg-gray-50 border-b-2 border-gray-200">
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">التاريخ</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">عدد الطلبات</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">المبيعات</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${days.length > 0 ? days.map(date => `
                                    <tr class="border-b border-gray-200 hover:bg-gray-50 transition">
                                        <td class="px-4 py-3 text-right">${new Date(date).toLocaleDateString('ar-EG')}</td>
                                        <td class="px-4 py-3 text-right">${dailyBreakdown[date].count}</td>
                                        <td class="px-4 py-3 text-right font-bold text-green-600">${dailyBreakdown[date].sales.toFixed(2)}</td>
                                    </tr>
                                `).join('') : '<tr><td colspan="3" class="text-center py-8 text-gray-400">لا توجد بيانات</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading weekly report:', error);
        content.innerHTML = '<div class="text-center py-8 text-red-500">خطأ في تحميل التقرير</div>';
    }
}

// Load monthly report
async function loadMonthlyReport() {
    const month = document.getElementById('reportMonth').value;
    const content = document.getElementById('monthlyReportContent');

    if (!content || !month) {
        if (content) content.innerHTML = '<div class="text-center py-8 text-gray-400">الرجاء اختيار شهر</div>';
        return;
    }

    content.innerHTML = '<div class="text-center py-8 text-gray-400">جاري التحميل...</div>';

    try {
        const [year, monthNum] = month.split('-');
        const response = await fetch(`/api/admin/reports/monthly?year=${year}&month=${monthNum}`);
        if (!response.ok) throw new Error('Failed to load report');

        const report = await response.json();

        const totalSales = parseFloat(report.total_sales || 0).toFixed(2);
        const orderCount = report.order_count || 0;

        let dailyBreakdownHtml = '';
        if (report.daily_breakdown && report.daily_breakdown.length > 0) {
            dailyBreakdownHtml = `
                <div class="mt-6">
                    <h3 class="text-lg font-bold text-gray-800 mb-4">التفصيل اليومي</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full border-collapse">
                            <thead>
                                <tr class="bg-gray-50 border-b-2 border-gray-200">
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">التاريخ</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">عدد الطلبات</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">المبيعات</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${report.daily_breakdown.map(day => `
                                    <tr class="border-b border-gray-200 hover:bg-gray-50 transition">
                                        <td class="px-4 py-3 text-right">${new Date(day.date).toLocaleDateString('ar-EG')}</td>
                                        <td class="px-4 py-3 text-right">${day.order_count}</td>
                                        <td class="px-4 py-3 text-right font-bold text-green-600">${parseFloat(day.total || 0).toFixed(2)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        } else {
            dailyBreakdownHtml = '<div class="text-center py-8 text-gray-400">لا توجد بيانات لهذا الشهر</div>';
        }

        content.innerHTML = `
            <div class="space-y-6">
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-blue-50 border-2 border-blue-200 rounded-lg p-6">
                        <div class="text-sm text-gray-600 font-semibold mb-2">إجمالي المبيعات</div>
                        <div class="text-3xl font-bold text-blue-700">${totalSales}</div>
                    </div>
                    <div class="bg-green-50 border-2 border-green-200 rounded-lg p-6">
                        <div class="text-sm text-gray-600 font-semibold mb-2">عدد الطلبات</div>
                        <div class="text-3xl font-bold text-green-700">${orderCount}</div>
                    </div>
                </div>
                ${dailyBreakdownHtml}
            </div>
        `;
    } catch (error) {
        console.error('Error loading monthly report:', error);
        content.innerHTML = '<div class="text-center py-8 text-red-500">خطأ في تحميل التقرير</div>';
    }
}

// Helper function to get date of ISO week
function getDateOfISOWeek(w, y) {
    const simple = new Date(y, 0, 1 + (w - 1) * 7);
    const dow = simple.getDay();
    const ISOweekStart = simple;
    if (dow <= 4)
        ISOweekStart.setDate(simple.getDate() - simple.getDay() + 1);
    else
        ISOweekStart.setDate(simple.getDate() + 8 - simple.getDay());
    return ISOweekStart;
}

// Settings
async function loadSettings() {
    try {
        const response = await fetch('/api/auth/passwords');
        const passwords = await response.json();
        const adminPassInput = document.getElementById('adminPassword');
        const cashierPassInput = document.getElementById('cashierPassword');
        if (adminPassInput) adminPassInput.value = passwords.admin_password || '12345';
        if (cashierPassInput) cashierPassInput.value = passwords.cashier_password || '1234';

        // Cache busting added
        const settingsResponse = await fetch('/api/settings?t=' + new Date().getTime());
        const settings = await settingsResponse.json();

        console.log('Loaded Settings (Admin):', settings); // Debug log

        // Load available printers and set the selected one
        await loadAvailablePrinters(settings.printer_ip);

        // Load discount permission
        const discountPermissionResponse = await fetch('/api/settings/discount_permission?t=' + new Date().getTime());
        if (discountPermissionResponse.ok) {
            const discountData = await discountPermissionResponse.json();
            if (document.getElementById('discountPermissionCheckbox')) {
                document.getElementById('discountPermissionCheckbox').checked = discountData.has_discount_permission || false;
            }
        }

        // Load receipt settings
        if (settings.restaurant_name && document.getElementById('restaurantName')) document.getElementById('restaurantName').value = settings.restaurant_name;
        if (settings.restaurant_address && document.getElementById('restaurantAddress')) document.getElementById('restaurantAddress').value = settings.restaurant_address;
        if (settings.footer_text && document.getElementById('footerText')) document.getElementById('footerText').value = settings.footer_text;

        // Fix for 0 values and ensuring elements exist
        if (settings.playstation_price_per_hour !== undefined && settings.playstation_price_per_hour !== null && document.getElementById('playstationPrice')) {
            document.getElementById('playstationPrice').value = settings.playstation_price_per_hour;
        }
        if (settings.playstation_price_multi !== undefined && settings.playstation_price_multi !== null && document.getElementById('playstationPriceMulti')) {
            document.getElementById('playstationPriceMulti').value = settings.playstation_price_multi;
        }

        // Show receipt settings card if user is owner
        const auth = sessionStorage.getItem('pageType');
        if (auth === 'owner' && document.getElementById('receiptSettingsCard')) {
            document.getElementById('receiptSettingsCard').classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Load available printers
async function loadAvailablePrinters(selectedPrinter = null) {
    const printerSelect = document.getElementById('printerSelect');
    if (!printerSelect) return;

    try {
        // Show loading state
        printerSelect.innerHTML = '<option value="">جاري التحميل...</option>';
        printerSelect.disabled = true;

        const response = await fetch('/api/printers/list');
        if (!response.ok) {
            throw new Error('Failed to load printers');
        }

        const data = await response.json();
        const printers = data.printers || [];

        // Clear and populate dropdown
        printerSelect.innerHTML = '';

        // Add default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'اختر طابعة (أو اترك فارغاً للطابعة الافتراضية)';
        printerSelect.appendChild(defaultOption);

        // Add Browser Print option
        const browserPrintOption = document.createElement('option');
        browserPrintOption.value = 'BROWSER_PRINT';
        browserPrintOption.textContent = '🌐 Browser Print (طباعة المتصفح)';
        printerSelect.appendChild(browserPrintOption);

        // Add printers
        printers.forEach(printer => {
            const option = document.createElement('option');
            option.value = printer.name;
            option.textContent = printer.name + (printer.is_default ? ' (افتراضي)' : '');
            printerSelect.appendChild(option);
        });

        // Select the saved printer if provided
        if (selectedPrinter) {
            printerSelect.value = selectedPrinter;
        }

        printerSelect.disabled = false;

        console.log(`Loaded ${printers.length} printers`);
    } catch (error) {
        console.error('Error loading printers:', error);
        printerSelect.innerHTML = '<option value="">خطأ في تحميل الطابعات</option>';
        printerSelect.disabled = false;
        notificationManager.error('خطأ في تحميل قائمة الطابعات');
    }
}

async function saveSettings() {
    const adminPassword = document.getElementById('adminPassword').value;
    const cashierPassword = document.getElementById('cashierPassword').value;
    const printerSelect = document.getElementById('printerSelect');
    const selectedPrinter = printerSelect ? printerSelect.value : '';
    const playstationPrice = document.getElementById('playstationPrice').value;
    const playstationPriceMulti = document.getElementById('playstationPriceMulti').value;
    const discountPermission = document.getElementById('discountPermissionCheckbox').checked;

    try {
        const payload = {
            admin_password: adminPassword || undefined,
            cashier_password: cashierPassword || undefined,
            printer_ip: selectedPrinter || undefined,
            playstation_price_per_hour: playstationPrice ? parseFloat(playstationPrice) : undefined,
            playstation_price_multi: playstationPriceMulti ? parseFloat(playstationPriceMulti) : undefined,
            playstation_enabled: document.getElementById('playstationEnabledCheckbox').checked ? '1' : '0'
        };
        console.log('Sending settings payload:', payload);

        // Save basic settings
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        // Save discount permission
        const discountResponse = await fetch('/api/settings/discount_permission', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: discountPermission })
        });

        let success = true;

        if (!response.ok) {
            success = false;
            const errorText = await response.text();
            console.error('Error saving main settings:', errorText);
            notificationManager.error('خطأ في حفظ الإعدادات الأساسية');
        }

        if (!discountResponse.ok) {
            success = false;
            const errorText = await discountResponse.text();
            console.error('Error saving discount permission:', errorText);
            notificationManager.error('خطأ في حفظ صلاحيات الخصم');
        }

        if (success) {
            notificationManager.success('تم حفظ الإعدادات بنجاح');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        notificationManager.error('خطأ في حفظ الإعدادات: ' + (error.message || 'خطأ غير معروف'));
    }
}

async function saveReceiptSettings() {
    const restaurantName = document.getElementById('restaurantName').value;
    const restaurantAddress = document.getElementById('restaurantAddress').value;
    const footerText = document.getElementById('footerText').value;

    try {
        const response = await fetch('/api/settings/receipt', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                restaurant_name: restaurantName || undefined,
                restaurant_address: restaurantAddress || undefined,
                footer_text: footerText || undefined
            })
        });

        if (response.ok) {
            notificationManager.success('تم حفظ إعدادات الفاتورة بنجاح');
        } else {
            const error = await response.json();
            notificationManager.error('خطأ في حفظ إعدادات الفاتورة: ' + (error.detail || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('Error saving receipt settings:', error);
        notificationManager.error('خطأ في حفظ إعدادات الفاتورة');
    }
}

async function uploadLogo() {
    const logoInput = document.getElementById('logoInput');
    if (!logoInput || !logoInput.files || logoInput.files.length === 0) {
        notificationManager.warning('الرجاء اختيار صورة أولاً');
        return;
    }

    const formData = new FormData();
    formData.append('file', logoInput.files[0]);

    try {
        notificationManager.info('جاري رفع اللوجو...');
        const response = await fetch('/api/settings/logo', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            notificationManager.success('تم رفع اللوجو بنجاح');
            // Clear input
            logoInput.value = '';
        } else {
            const error = await response.json();
            notificationManager.error('خطأ في رفع اللوجو: ' + (error.detail || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('Error uploading logo:', error);
        notificationManager.error('خطأ في رفع اللوجو');
    }
}

// Show order details modal
async function showOrderDetails(orderId) {
    try {
        const response = await fetch(`/api/orders/${orderId}`);
        if (!response.ok) {
            throw new Error('Failed to load order details');
        }

        const order = await response.json();
        const modal = document.getElementById('orderDetailsModal');
        const content = document.getElementById('orderDetailsContent');

        if (!modal || !content) return;

        // Format date and time
        const orderDate = new Date(order.created_at);
        const dateStr = orderDate.toLocaleDateString('ar-EG');
        const timeStr = orderDate.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });

        // Table display
        const tableDisplay = (order.table_number && order.table_number > 0) ? `طاولة ${order.table_number}` : 'سفري';

        // Status text
        const statusText = order.status === 'pending' ? 'قيد الانتظار' :
            order.status === 'completed' ? 'مكتمل' :
                order.status === 'cancelled' ? 'ملغي' : order.status;

        // Get invoice if order is completed
        let invoiceHtml = '';
        if (order.status === 'completed' && order.invoice_number) {
            try {
                const invoiceResponse = await fetch(`/api/invoices?order_number=${order.order_number}`);
                if (invoiceResponse.ok) {
                    const invoices = await invoiceResponse.json();
                    const invoice = invoices.find(inv => inv.order_number === order.order_number.toString());
                    if (invoice) {
                        let cashAmount = 0;
                        let cardAmount = 0;
                        let paymentMethodText = '';

                        if (invoice.payment_method === 'cash') {
                            cashAmount = parseFloat(invoice.net_amount || invoice.total_amount);
                            paymentMethodText = 'نقدي';
                        } else if (invoice.payment_method === 'card') {
                            cardAmount = parseFloat(invoice.net_amount || invoice.total_amount);
                            paymentMethodText = 'بطاقة';
                        } else if (invoice.payment_method && invoice.payment_method.startsWith('mixed_cash_')) {
                            // Parse mixed payment: mixed_cash_XXX_card_YYY
                            const match = invoice.payment_method.match(/mixed_cash_(\d+(?:\.\d+)?)_card_(\d+(?:\.\d+)?)/);
                            if (match) {
                                cashAmount = parseFloat(match[1]);
                                cardAmount = parseFloat(match[2]);
                                paymentMethodText = 'مختلط';
                            } else {
                                paymentMethodText = 'مختلط';
                            }
                        } else {
                            paymentMethodText = invoice.payment_method || 'غير محدد';
                        }

                        invoiceHtml = `
                            <div class="mt-6 p-4 bg-green-50 rounded-lg border-2 border-green-200">
                                <h3 class="text-lg font-bold text-gray-800 mb-3">معلومات الدفع</h3>
                                <div class="grid grid-cols-2 gap-3">
                                    <div>
                                        <span class="text-gray-600 font-semibold">رقم الفاتورة:</span>
                                        <span class="text-gray-800 font-bold">${invoice.invoice_number}</span>
                                    </div>
                                    <div>
                                        <span class="text-gray-600 font-semibold">طريقة الدفع:</span>
                                        <span class="text-gray-800 font-bold">${paymentMethodText}</span>
                                    </div>
                                    ${cashAmount > 0 ? `
                                    <div>
                                        <span class="text-gray-600 font-semibold">المبلغ النقدي:</span>
                                        <span class="text-gray-800 font-bold text-green-600">${cashAmount.toFixed(2)}</span>
                                    </div>
                                    ` : ''}
                                    ${cardAmount > 0 ? `
                                    <div>
                                        <span class="text-gray-600 font-semibold">المبلغ بالبطاقة:</span>
                                        <span class="text-gray-800 font-bold text-blue-600">${cardAmount.toFixed(2)}</span>
                                    </div>
                                    ` : ''}
                                    <div>
                                        <span class="text-gray-600 font-semibold">صافي المبلغ:</span>
                                        <span class="text-gray-800 font-bold">${(invoice.net_amount || invoice.total_amount).toFixed(2)}</span>
                                    </div>
                                    <div>
                                        <span class="text-gray-600 font-semibold">قيمة مضافة:</span>
                                        <span class="text-gray-800 font-bold">${(invoice.vat_amount || 0).toFixed(2)}</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                }
            } catch (error) {
                console.error('Error loading invoice:', error);
            }
        }

        // Build items HTML
        const itemsHtml = order.items && order.items.length > 0 ? order.items.map((item, index) => {
            let itemDetails = item.product_name;
            if (item.size) {
                itemDetails += ` (${item.size})`;
            }
            if (item.additions) {
                try {
                    const additions = typeof item.additions === 'string' ? JSON.parse(item.additions) : item.additions;
                    if (Array.isArray(additions) && additions.length > 0) {
                        itemDetails += ` + ${additions.join(', ')}`;
                    }
                } catch (e) {
                    // Ignore parsing errors
                }
            }
            if (item.notes) {
                itemDetails += ` [${item.notes}]`;
            }

            return `
                <tr class="border-b border-gray-200">
                    <td class="px-4 py-3 text-right">${index + 1}</td>
                    <td class="px-4 py-3 text-right">${itemDetails}</td>
                    <td class="px-4 py-3 text-right">${item.quantity}</td>
                    <td class="px-4 py-3 text-right">${item.price.toFixed(2)}</td>
                    <td class="px-4 py-3 text-right font-semibold">${item.total.toFixed(2)}</td>
                </tr>
            `;
        }).join('') : '<tr><td colspan="5" class="text-center py-4 text-gray-400">لا توجد منتجات</td></tr>';

        content.innerHTML = `
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <span class="text-gray-600 font-semibold">رقم الطلب:</span>
                        <span class="text-gray-800 font-bold text-lg">${order.order_number}</span>
                    </div>
                    <div>
                        <span class="text-gray-600 font-semibold">الحالة:</span>
                        <span class="px-2 py-1 rounded text-xs font-semibold ${order.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                order.status === 'completed' ? 'bg-green-100 text-green-800' :
                    'bg-red-100 text-red-800'
            }">${statusText}</span>
                    </div>
                    <div>
                        <span class="text-gray-600 font-semibold">${tableDisplay}</span>
                    </div>
                    <div>
                        <span class="text-gray-600 font-semibold">التاريخ والوقت:</span>
                        <span class="text-gray-800">${dateStr} ${timeStr}</span>
                    </div>
                    ${order.customer_name ? `
                    <div>
                        <span class="text-gray-600 font-semibold">اسم العميل:</span>
                        <span class="text-gray-800">${order.customer_name}</span>
                    </div>
                    ` : ''}
                    ${order.customer_phone ? `
                    <div>
                        <span class="text-gray-600 font-semibold">هاتف العميل:</span>
                        <span class="text-gray-800">${order.customer_phone}</span>
                    </div>
                    ` : ''}
                    <div>
                        <span class="text-gray-600 font-semibold">الفرع:</span>
                        <span class="text-gray-800">${order.branch || 'الفرع الرئيسي'}</span>
                    </div>
                    <div>
                        <span class="text-gray-600 font-semibold">الكاشير:</span>
                        <span class="text-gray-800">${order.cashier || 'كاشير'}</span>
                    </div>
                </div>
                
                <div class="mt-6">
                    <h3 class="text-lg font-bold text-gray-800 mb-3">المنتجات</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full border-collapse">
                            <thead>
                                <tr class="bg-gray-100 border-b-2 border-gray-300">
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">#</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">المنتج</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">الكمية</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">السعر</th>
                                    <th class="px-4 py-3 text-right font-bold text-gray-700">الإجمالي</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${itemsHtml}
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="mt-6 p-4 bg-blue-50 rounded-lg border-2 border-blue-200">
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <span class="text-gray-600 font-semibold">المبلغ الإجمالي:</span>
                            <span class="text-gray-800 font-bold text-lg">${order.total_amount.toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-gray-600 font-semibold">الخصم:</span>
                            <span class="text-gray-800 font-bold">${(order.discount_amount || 0).toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-gray-600 font-semibold">الضريبة:</span>
                            <span class="text-gray-800 font-bold">${(order.tax_amount || 0).toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-gray-600 font-semibold">ق.م:</span>
                            <span class="text-gray-800 font-bold">${(order.vat_amount || 0).toFixed(2)}</span>
                        </div>
                    </div>
                </div>
                
                ${invoiceHtml}
            </div>
        `;

        modal.classList.remove('hidden');
    } catch (error) {
        console.error('Error loading order details:', error);
        notificationManager.error('خطأ في تحميل تفاصيل الطلب');
    }
}

// Close order details modal
function closeOrderDetailsModal() {
    const modal = document.getElementById('orderDetailsModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Load all orders with filters (with caching)
async function loadAllOrders() {
    try {
        // Build query parameters
        const params = new URLSearchParams();

        const orderNumber = document.getElementById('filterOrderNumberForOrders')?.value;
        const customerName = document.getElementById('filterOrderCustomerName')?.value;
        const customerPhone = document.getElementById('filterOrderCustomerPhone')?.value;
        const tableNumber = document.getElementById('filterOrderTableNumber')?.value;
        const branch = document.getElementById('filterOrderBranch')?.value;
        const cashier = document.getElementById('filterOrderCashier')?.value;
        const status = document.getElementById('filterOrderStatus')?.value;
        const startDate = document.getElementById('orderStartDate')?.value;
        const endDate = document.getElementById('orderEndDate')?.value;

        if (orderNumber) params.append('order_number', orderNumber);
        if (customerName) params.append('customer_name', customerName);
        if (customerPhone) params.append('customer_phone', customerPhone);
        if (tableNumber) params.append('table_number', tableNumber);
        if (branch) params.append('branch', branch);
        if (cashier) params.append('cashier', cashier);
        if (status) params.append('status', status);
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);

        const url = `/api/orders${params.toString() ? '?' + params.toString() : ''}`;
        const fetchFn = window.PerformanceUtils ? window.PerformanceUtils.cachedFetch : fetch;
        const response = await fetchFn(url, {}, url);

        if (response.ok) {
            const orders = await response.json();
            displayOrdersTable(orders);
        } else {
            throw new Error('Failed to load orders');
        }
    } catch (error) {
        console.error('Error loading all orders:', error);
        notificationManager.error('خطأ في تحميل الطلبات');
    }
}

// Display orders in table format (optimized with DocumentFragment)
function displayOrdersTable(orders) {
    requestAnimationFrame(() => {
        const tbody = document.getElementById('ordersTableBody');
        if (!tbody) return;

        if (orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="15" class="text-center py-8 text-gray-400">لا توجد طلبات</td></tr>';
            return;
        }

        // Use DocumentFragment for better performance
        const fragment = document.createDocumentFragment();
        const tempTable = document.createElement('table');
        const tempTbody = document.createElement('tbody');

        tempTbody.innerHTML = orders.map((order, index) => {
            const totalQuantity = order.items ? order.items.reduce((sum, item) => sum + item.quantity, 0) : 0;
            const orderDate = new Date(order.created_at);
            const dateStr = orderDate.toLocaleDateString('ar-EG');
            const timeStr = orderDate.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
            const statusText = order.status === 'pending' ? 'قيد الانتظار' :
                order.status === 'completed' ? 'مكتمل' :
                    order.status === 'cancelled' ? 'ملغي' : order.status;
            const tableDisplay = (order.table_number && order.table_number > 0) ? order.table_number : 'سفري';

            return `
                <tr class="hover:bg-gray-50 transition">
                    <td class="px-4 py-3 text-right border border-gray-300">${index + 1}</td>
                    <td class="px-4 py-3 text-right border border-gray-300 font-semibold">${order.order_number}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${tableDisplay}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${order.customer_name || '-'}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${order.customer_phone || '-'}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${totalQuantity}</td>
                    <td class="px-4 py-3 text-right border border-gray-300 font-semibold">${order.total_amount.toFixed(2)}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${(order.discount_amount || 0).toFixed(2)}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${(order.tax_amount || 0).toFixed(2)}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${(order.vat_amount || 0).toFixed(2)}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">
                        <span class="px-2 py-1 rounded text-xs font-semibold ${order.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                    order.status === 'completed' ? 'bg-green-100 text-green-800' :
                        'bg-red-100 text-red-800'
                }">${statusText}</span>
                    </td>
                    <td class="px-4 py-3 text-right border border-gray-300">${order.branch || 'الفرع الرئيسي'}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${order.cashier || 'كاشير'}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">${dateStr} ${timeStr}</td>
                    <td class="px-4 py-3 text-right border border-gray-300">
                        <button onclick="openPrintModal(${order.id}, '${order.status}')" class="text-purple-600 hover:text-purple-800 font-semibold mr-2" title="طباعة الفاتورة">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path>
                            </svg>
                        </button>
                        <button onclick="showOrderDetails(${order.id})" class="text-blue-600 hover:text-blue-800 font-semibold" title="عرض التفاصيل">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                            </svg>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        tempTable.appendChild(tempTbody);
        fragment.appendChild(tempTable);

        // Single DOM update
        tbody.innerHTML = '';
        Array.from(tempTbody.children).forEach(row => tbody.appendChild(row));
    });
}


// Logout function
async function logout() {
    if (await notificationManager.confirm('هل تريد تسجيل الخروج؟')) {
        sessionStorage.removeItem('authenticated');
        sessionStorage.removeItem('pageType');
        window.location.href = '/';
    }
}

// Shift Settings
async function loadShiftSettings() {
    try {
        const response = await fetch('/api/shifts/settings');
        if (response.ok) {
            const settings = await response.json();
            document.getElementById('numberOfShifts').value = settings.number_of_shifts;
            document.getElementById('shift1Name').value = settings.shift1_name;
            document.getElementById('shift1StartTime').value = settings.shift1_start_time;
            document.getElementById('shift1EndTime').value = settings.shift1_end_time;
            document.getElementById('shift2Name').value = settings.shift2_name;
            document.getElementById('shift2StartTime').value = settings.shift2_start_time;
            document.getElementById('shift2EndTime').value = settings.shift2_end_time;

            if (settings.shift3_name) {
                document.getElementById('shift3Name').value = settings.shift3_name;
                document.getElementById('shift3StartTime').value = settings.shift3_start_time;
                document.getElementById('shift3EndTime').value = settings.shift3_end_time;
            }

            // Show/hide shift 3 section
            const shift3Section = document.getElementById('shift3Section');
            if (settings.number_of_shifts === 3) {
                shift3Section.classList.remove('hidden');
            } else {
                shift3Section.classList.add('hidden');
            }
        }
    } catch (error) {
        console.error('Error loading shift settings:', error);
    }
}

async function saveShiftSettings() {
    const numberOfShifts = parseInt(document.getElementById('numberOfShifts').value);
    const shift1Name = document.getElementById('shift1Name').value;
    const shift1StartTime = document.getElementById('shift1StartTime').value;
    const shift1EndTime = document.getElementById('shift1EndTime').value;
    const shift2Name = document.getElementById('shift2Name').value;
    const shift2StartTime = document.getElementById('shift2StartTime').value;
    const shift2EndTime = document.getElementById('shift2EndTime').value;

    const settings = {
        number_of_shifts: numberOfShifts,
        shift1_name: shift1Name,
        shift1_start_time: shift1StartTime,
        shift1_end_time: shift1EndTime,
        shift2_name: shift2Name,
        shift2_start_time: shift2StartTime,
        shift2_end_time: shift2EndTime
    };

    if (numberOfShifts === 3) {
        settings.shift3_name = document.getElementById('shift3Name').value;
        settings.shift3_start_time = document.getElementById('shift3StartTime').value;
        settings.shift3_end_time = document.getElementById('shift3EndTime').value;
    }

    try {
        const response = await fetch('/api/shifts/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            notificationManager.success('تم حفظ إعدادات الشيفتات بنجاح');
        } else {
            const error = await response.json();
            notificationManager.error('خطأ في حفظ إعدادات الشيفتات: ' + (error.detail || 'خطأ غير معروف'));
        }
    } catch (error) {
        console.error('Error saving shift settings:', error);
        notificationManager.error('خطأ في حفظ إعدادات الشيفتات: ' + error.message);
    }
}

async function loadShiftReport() {
    const date = document.getElementById('shiftReportDate')?.value;
    if (!date) {
        return;
    }

    const list = document.getElementById('shiftsReportList');
    if (!list) return;

    list.innerHTML = '<div class="text-center text-gray-400 py-8">جاري التحميل...</div>';

    try {
        const response = await fetch(`/api/shifts?start_date=${date}&end_date=${date}`);
        if (response.ok) {
            const shifts = await response.json();

            if (shifts.length === 0) {
                list.innerHTML = '<div class="text-center text-gray-400 py-8">لا توجد شيفتات في هذا التاريخ</div>';
                return;
            }

            list.innerHTML = shifts.map(shift => {
                const openedAt = new Date(shift.opened_at);
                const closedAt = shift.closed_at ? new Date(shift.closed_at) : null;
                const statusBadge = shift.status === 'open'
                    ? '<span class="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-bold">مفتوح</span>'
                    : '<span class="px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm font-bold">مغلق</span>';

                return `
                    <div class="border-2 border-gray-200 rounded-lg p-4 hover:border-blue-300 transition cursor-pointer" onclick="viewShiftReport(${shift.id})">
                        <div class="flex justify-between items-start mb-2">
                            <div>
                                <div class="font-bold text-lg text-gray-800">${shift.shift_name} ${shift.shift_number > 1 ? shift.shift_number : ''}</div>
                                <div class="text-sm text-gray-600">${shift.shift_date}</div>
                            </div>
                            ${statusBadge}
                        </div>
                        <div class="grid grid-cols-3 gap-2 mt-3 text-sm">
                            <div class="text-center">
                                <div class="text-gray-500">الإيرادات</div>
                                <div class="font-bold text-green-600">${parseFloat(shift.total_revenue || 0).toFixed(2)}</div>
                            </div>
                            <div class="text-center">
                                <div class="text-gray-500">الطلبات</div>
                                <div class="font-bold text-blue-600">${shift.total_orders || 0}</div>
                            </div>
                            <div class="text-center">
                                <div class="text-gray-500">الفواتير</div>
                                <div class="font-bold text-purple-600">${shift.total_invoices || 0}</div>
                            </div>
                        </div>
                        <div class="text-xs text-gray-500 mt-2">
                            فتح: ${openedAt.toLocaleTimeString('ar-EG')}
                            ${closedAt ? ` | إغلاق: ${closedAt.toLocaleTimeString('ar-EG')}` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            list.innerHTML = '<div class="text-center text-red-400 py-8">خطأ في تحميل التقارير</div>';
        }
    } catch (error) {
        console.error('Error loading shift report:', error);
        list.innerHTML = '<div class="text-center text-red-400 py-8">خطأ في تحميل التقارير</div>';
    }
}

async function viewShiftReport(shiftId) {
    try {
        const response = await fetch(`/api/shifts/${shiftId}/report`);
        if (response.ok) {
            const report = await response.json();
            showShiftReportModal(report);
        } else {
            const error = await response.json();
            if (window.notificationManager) {
                window.notificationManager.error('خطأ في تحميل التقرير: ' + (error.detail || 'خطأ غير معروف'));
            }
        }
    } catch (error) {
        console.error('Error viewing shift report:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في تحميل التقرير: ' + error.message);
        }
    }
}

let currentShiftReport = null;

function showShiftReportModal(report) {
    currentShiftReport = report; // Store for filtering

    // Calculate totals for summary cards
    const totalRevenue = parseFloat(report.shift.total_revenue || 0);
    const totalOrders = report.shift.total_orders || 0;
    const totalInvoices = report.shift.total_invoices || 0;
    const cashExpected = parseFloat(report.shift.cash_expected || 0);
    const cashActual = parseFloat(report.shift.cash_drawer_amount || 0);
    const difference = parseFloat(report.shift.cash_difference || 0);
    const totalCash = parseFloat(report.total_cash || 0);
    const totalCard = parseFloat(report.total_card || 0);

    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-lg w-full max-w-7xl mx-4 h-[90vh] flex flex-col">
            <!-- Header -->
            <div class="p-6 border-b border-gray-200 flex justify-between items-center bg-gray-50 rounded-t-lg">
                <div>
                    <h2 class="text-2xl font-bold text-gray-800">تقرير شيفت: ${report.shift.shift_name} ${report.shift.shift_number > 1 ? report.shift.shift_number : ''}</h2>
                    <p class="text-gray-600 mt-1">
                        <span class="font-semibold">التاريخ:</span> ${report.shift.shift_date} | 
                        <span class="font-semibold">فتح:</span> ${new Date(report.shift.opened_at).toLocaleTimeString('ar-EG')}
                        ${report.shift.closed_at ? ` | <span class="font-semibold">إغلاق:</span> ${new Date(report.shift.closed_at).toLocaleTimeString('ar-EG')}` : ''}
                    </p>
                </div>
                <button onclick="this.closest('.fixed').remove()" class="text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-full p-2 transition">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <!-- Scrollable Content -->
            <div class="flex-1 overflow-y-auto p-6 bg-gray-100">
                
                <!-- Summary Cards Grid -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                    <!-- Revenue -->
                    <div class="bg-white p-4 rounded-lg shadow-sm border border-green-100">
                        <div class="text-sm text-gray-500 font-semibold mb-1">إجمالي الإيرادات</div>
                        <div class="text-2xl font-bold text-green-600">${totalRevenue.toFixed(2)}</div>
                    </div>
                    <!-- Orders/Invoices -->
                    <div class="bg-white p-4 rounded-lg shadow-sm border border-blue-100">
                        <div class="text-sm text-gray-500 font-semibold mb-1">العمليات</div>
                        <div class="flex justify-between items-end">
                            <div><span class="text-sm text-gray-400">طلبات:</span> <span class="font-bold text-blue-600">${totalOrders}</span></div>
                            <div><span class="text-sm text-gray-400">فواتير:</span> <span class="font-bold text-purple-600">${totalInvoices}</span></div>
                        </div>
                    </div>
                    <!-- Payment Methods -->
                    <div class="bg-white p-4 rounded-lg shadow-sm border border-indigo-100">
                        <div class="text-sm text-gray-500 font-semibold mb-1">طرق الدفع</div>
                        <div class="flex justify-between items-end">
                            <div><span class="text-sm text-gray-400">نقدي:</span> <span class="font-bold text-green-600">${totalCash.toFixed(2)}</span></div>
                            <div><span class="text-sm text-gray-400">بطاقة:</span> <span class="font-bold text-blue-600">${totalCard.toFixed(2)}</span></div>
                        </div>
                    </div>
                    <!-- Cash Summary -->
                    <div class="bg-white p-4 rounded-lg shadow-sm border ${difference >= 0 ? 'border-green-100' : 'border-red-100'}">
                         <div class="text-sm text-gray-500 font-semibold mb-1">ملخص النقدية</div>
                         <div class="flex flex-col">
                            <div class="flex justify-between"><span class="text-xs text-gray-400">فعلي:</span> <span class="font-bold">${cashActual.toFixed(2)}</span></div>
                            <div class="flex justify-between"><span class="text-xs text-gray-400">الفرق:</span> <span class="font-bold ${difference >= 0 ? 'text-green-600' : 'text-red-600'}">${difference > 0 ? '+' : ''}${difference.toFixed(2)}</span></div>
                         </div>
                    </div>
                </div>

                <!-- Search Bar -->
                <div class="mb-4 bg-white p-4 rounded-lg shadow-sm">
                    <div class="relative">
                        <input type="text" 
                            id="shiftReportSearch" 
                            placeholder="بحث ذكي: ابحث برقم الطلب، اسم العميل، أو اسم المنتج (مثال: برجر، بيبسي)..." 
                            class="w-full pl-10 pr-12 py-3 border-2 border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg transition"
                            onkeyup="filterShiftOrders(this.value)"
                        >
                        <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-gray-400">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                </div>

                <!-- Detailed Table -->
                <div class="bg-white rounded-lg shadow-sm overflow-hidden">
                    <div class="overflow-x-auto">
                        <table class="w-full whitespace-nowrap">
                            <thead class="bg-gray-50 border-b border-gray-200">
                                <tr>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">#</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">رقم الطلب</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">النوع/الطاولة</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">العميل</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">تفاصيل المنتجات</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">الإجمالي</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">الدفع</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">الوقت</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">الحالة</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">عرض</th>
                                </tr>
                            </thead>
                            <tbody id="shiftDetailsTableBody" class="bg-white divide-y divide-gray-200">
                                <!-- Content will be populated by JS -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    renderShiftOrdersTable(report.orders);
}

function renderShiftOrdersTable(orders) {
    const tbody = document.getElementById('shiftDetailsTableBody');
    if (!tbody) return;

    if (!orders || orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="px-6 py-8 text-center text-gray-500">لا توجد طلبات مطابقة للبحث</td></tr>';
        return;
    }

    // Sort orders by ID (newest first usually, or by ID)
    const sortedOrders = [...orders].sort((a, b) => b.id - a.id);

    tbody.innerHTML = sortedOrders.map((order, index) => {
        // Prepare items summary
        let itemsSummary = '';
        if (order.items && order.items.length > 0) {
            itemsSummary = order.items.map(item => `<span class="inline-block bg-gray-100 rounded px-2 py-1 text-xs text-gray-700 mr-1 mb-1">${item.quantity}x ${item.product_name}</span>`).slice(0, 3).join('');
            if (order.items.length > 3) itemsSummary += `<span class="text-xs text-gray-500 mr-1">+${order.items.length - 3} المزيد</span>`;
        } else {
            itemsSummary = '<span class="text-gray-400 text-xs">-</span>';
        }

        // Determine Payment method from invoice lookups if available, or try to guess/display if passed
        // Since the current report object might not deeply link invoices to orders in a simple way for the table row,
        // we'll check if we can match them.
        // The report object has `invoices` array.
        let paymentInfo = '<span class="text-gray-400 text-xs">غير مدفوع</span>';
        if (order.status === 'completed') {
            // Try to find matching invoice
            if (currentShiftReport && currentShiftReport.invoices) {
                const inv = currentShiftReport.invoices.find(i => i.order_number == order.order_number.toString());
                if (inv) {
                    let methodAr = 'غير محدد';
                    if (inv.payment_method === 'cash') methodAr = 'نقدي';
                    else if (inv.payment_method === 'card') methodAr = 'بطاقة';
                    else if (inv.payment_method && inv.payment_method.includes('mixed')) methodAr = 'مختلط';

                    paymentInfo = `<span class="font-bold text-gray-700">${methodAr}</span>`;
                } else {
                    paymentInfo = '<span class="text-green-600 font-semibold">مكتمل</span>';
                }
            }
        } else if (order.status === 'cancelled') {
            paymentInfo = '<span class="text-red-500 text-xs">ملغي</span>';
        }

        const date = new Date(order.created_at);
        const timeStr = date.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });

        return `
            <tr class="hover:bg-blue-50 transition duration-150">
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${index + 1}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-900">#${order.order_number}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">${order.table_number ? `طاولة ${order.table_number}` : 'سفري'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${order.customer_name || '-'}</td>
                <td class="px-6 py-4 text-sm text-gray-700 max-w-xs break-words whitespace-normal leading-relaxed">
                    ${itemsSummary}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-900">${parseFloat(order.total_amount).toFixed(2)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">${paymentInfo}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500" dir="ltr">${timeStr}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full 
                        ${order.status === 'completed' ? 'bg-green-100 text-green-800' :
                order.status === 'cancelled' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}">
                        ${order.status === 'completed' ? 'مكتمل' : order.status === 'cancelled' ? 'ملغي' : 'معلق'}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-right">
                    <button onclick="showOrderDetails(${order.id})" class="text-blue-600 hover:text-blue-800 transition p-1 rounded-full hover:bg-blue-50" title="تفاصيل الطلب">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function filterShiftOrders(query) {
    if (!currentShiftReport || !currentShiftReport.orders) return;

    const searchTerm = query.toLowerCase().trim();
    if (searchTerm === '') {
        renderShiftOrdersTable(currentShiftReport.orders);
        return;
    }

    const filtered = currentShiftReport.orders.filter(order => {
        // 1. Basic fields search
        const basicMatch =
            (order.order_number && order.order_number.toString().includes(searchTerm)) ||
            (order.customer_name && order.customer_name.toLowerCase().includes(searchTerm)) ||
            (order.customer_phone && order.customer_phone.includes(searchTerm)) ||
            (order.table_number && order.table_number.toString() === searchTerm);

        if (basicMatch) return true;

        // 2. Deep search in Items (Product names)
        if (order.items && order.items.length > 0) {
            const hasProductMatch = order.items.some(item =>
                item.product_name.toLowerCase().includes(searchTerm)
            );
            if (hasProductMatch) return true;
        }

        return false;
    });

    renderShiftOrdersTable(filtered);
}

// Make functions global
window.editCategory = openCategoryModal;
window.deleteCategory = deleteCategory;
window.editProduct = openProductModal;
window.toggleProduct = toggleProduct;
window.deleteProduct = deleteProduct;
window.logout = logout;
window.copyToClipboard = copyToClipboard;
window.viewShiftReport = viewShiftReport;

let currentPrintOrderId = null;

function openPrintModal(orderId, status) {
    currentPrintOrderId = orderId;
    const modal = document.getElementById('printOptionsModal');
    const invoiceBtn = document.getElementById('printInvoiceBtn');

    if (!modal) return;

    // Configure buttons
    if (status === 'completed') {
        invoiceBtn.disabled = false;
        invoiceBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'filter', 'blur-sm');
        invoiceBtn.classList.add('hover:bg-green-100');
        invoiceBtn.title = "";
    } else {
        invoiceBtn.disabled = true;
        invoiceBtn.classList.add('opacity-50', 'cursor-not-allowed', 'filter', 'blur-[1px]');
        invoiceBtn.classList.remove('hover:bg-green-100');
        invoiceBtn.title = "يجب إنهاء الطلب أولاً";
    }

    modal.classList.remove('hidden');
}

async function handlePrintOption(type) {
    if (!currentPrintOrderId) return;

    const endpoint = type === 'check'
        ? `/api/print/check/${currentPrintOrderId}`
        : `/api/print/invoice/${currentPrintOrderId}`;

    document.getElementById('printOptionsModal').classList.add('hidden');

    try {
        notificationManager.info('جاري الطباعة...');
        const response = await fetch(endpoint, { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            notificationManager.success('تم إرسال أمر الطباعة');
        } else {
            notificationManager.error('فشلت الطباعة: ' + (result.error || 'خطأ غير معروف'));
        }
    } catch (e) {
        console.error('Print error:', e);
        notificationManager.error('خطأ في الاتصال');
    }
}

// Updated reprintOrder to use modal
function reprintOrder(id) {
    // We need status to decide. But this function usually just gets ID from onclick.
    // We can try to find the row or fetch order.
    // OPTION: Pass status in the onclick in HTML.
    // Retaining backward compat, let's fetch or find row.
    // Quickest: Look at the row where the button is.

    // But better: Update the HTML generation to pass status.
    // For now, let's fetch order status simply or try to find it in DOM.
    // Actually, `renderDetailedOrdersTable` has full order object.
    // Let's rely on updated HTML calling `openPrintModal(id, 'status')`.
    // But since we can't easily change all onclicks efficiently in one go without context,
    // let's just fetch it quickly if status not passed.

    // Allow calling with status: reprintOrder(id, status)
    // If called from old onclick="reprintOrder(123)", status is undefined.
    // We can fetch it.
    openPrintModal(id, 'unknown'); // 'unknown' will default proper check inside via fetch? 
    // Wait, let's make a quick fetch helper or find it in data.
    // Actually, let's just modify the HTML generators to call openPrintModal directly.
}

window.reprintOrder = reprintOrder;
window.openPrintModal = openPrintModal;

// --- Reset Features ---
async function handleResetData() {
    if (!await notificationManager.confirm('هل أنت متأكد من تصفير البيانات؟\nسيتم حذف جميع الطلبات والفواتير والشيفتات.\nلن يتم حذف المنيو.')) {
        return;
    }

    // Double confirm
    const enteredPass = prompt("الرجاء إدخال كلمة مرور الأدمن للتأكيد:");
    if (!enteredPass) return;

    try {
        notificationManager.info('جاري تصفير البيانات...');
        const response = await fetch('/api/settings/reset-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: enteredPass, page_type: 'admin' })
        });

        if (response.ok) {
            notificationManager.success('تم تصفير البيانات بنجاح');
            setTimeout(() => location.reload(), 1500);
        } else {
            const data = await response.json();
            notificationManager.error(data.detail || 'فشلت العملية');
        }
    } catch (e) {
        console.error('Reset error:', e);
        notificationManager.error('خطأ في الاتصال');
    }
}

async function handleFactoryReset() {
    if (!await notificationManager.confirm('⚠️ تحذير شديد ⚠️\nهل أنت متأكد من إعادة ضبط المصنع؟\nسيتم حذف كل شيء (المنيو، الطلبات، المنتجات).\nلا يمكن التراجع عن هذه الخطوة!')) {
        return;
    }

    // Double confirm
    const enteredPass = prompt("الرجاء إدخال كلمة مرور الأدمن للتأكيد:");
    if (!enteredPass) return;

    try {
        notificationManager.info('جاري إعادة ضبط المصنع...');
        const response = await fetch('/api/settings/factory-reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: enteredPass, page_type: 'admin' })
        });

        if (response.ok) {
            notificationManager.success('تمت إعادة ضبط المصنع بنجاح');
            setTimeout(() => {
                window.location.href = '/login/index.html'; // Force re-login
            }, 1500);
        } else {
            const data = await response.json();
            notificationManager.error(data.detail || 'فشلت العملية');
        }
    } catch (e) {
        console.error('Factory reset error:', e);
        notificationManager.error('خطأ في الاتصال');
    }
}

window.handleResetData = handleResetData;
window.handleFactoryReset = handleFactoryReset;

// Initialize Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // ... existing ... 

    document.getElementById('printCheckBtn')?.addEventListener('click', () => handlePrintOption('check'));
    document.getElementById('printInvoiceBtn')?.addEventListener('click', () => handlePrintOption('invoice'));
});



// Backup Functions
async function handleRestoreMenu(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        if (window.notificationManager) window.notificationManager.info('جاري استعادة القائمة...');

        const response = await fetch('/api/backup/restore-menu', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            notificationManager.success(result.message || 'تم استعادة القائمة بنجاح');
            event.target.value = ''; // Reset input
            // Reload categories and products
            await loadCategories();
            await loadProducts();
        } else {
            const error = await response.json();
            notificationManager.error('خطأ: ' + (error.detail || 'فشل استعادة القائمة'));
        }
    } catch (error) {
        console.error('Error restoring menu:', error);
        notificationManager.error('حدث خطأ أثناء استعادة القائمة');
    }
}

async function handleRestoreFull(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Check file extension
    if (!file.name.endsWith('.db') && !file.name.endsWith('.zip')) {
        notificationManager.error('يجب اختيار ملف قاعدة بيانات (.db) أو ملف مضغوط (.zip)');
        return;
    }

    // Confirm action
    if (!await notificationManager.confirm('تحذير: سيتم حذف جميع البيانات الحالية واستبدالها بالنسخة الاحتياطية. هل أنت متأكد؟')) {
        event.target.value = '';
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        if (window.notificationManager) window.notificationManager.info('جاري استعادة النظام... الرجاء الانتظار');

        // Show loading overlay
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-[100]';
        loadingDiv.innerHTML = '<div class="text-white text-xl font-bold flex flex-col items-center"><span class="text-4xl mb-4 animate-spin">↻</span>جاري استعادة النظام...<br>لا تغلق التطبيق</div>';
        document.body.appendChild(loadingDiv);

        const response = await fetch('/api/backup/restore-full', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            document.body.removeChild(loadingDiv);
            notificationManager.success(result.message || 'تم استعادة النظام بنجاح. سيتم إعادة التشغيل.');
            alert('تم الاستعادة بنجاح. سيتم إعادة تشغيل التطبيق.');
            window.location.reload();
        } else {
            document.body.removeChild(loadingDiv);
            const error = await response.json();
            notificationManager.error('خطأ: ' + (error.detail || 'فشل استعادة النظام'));
            alert('Restore failed: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error restoring full backup:', error);
        // Remove loading div if exists
        const loadingDiv = document.querySelector('.bg-opacity-70');
        if (loadingDiv) document.body.removeChild(loadingDiv);

        notificationManager.error('حدث خطأ أثناء استعادة النظام');
        alert('Error: ' + error.message);
    } finally {
        event.target.value = ''; // Reset input
    }
}
// Detailed Reports Functions
function showDetailedReports() {
    // Hide other report sections
    ['dailyReportSection', 'weeklyReportSection', 'monthlyReportSection', 'detailedReportSection'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });

    // Show detailed report section
    const section = document.getElementById('detailedReportSection');
    if (section) section.classList.remove('hidden');

    // Set default dates (today)
    const today = new Date().toISOString().split('T')[0];
    const startInput = document.getElementById('detailedStartDate');
    const endInput = document.getElementById('detailedEndDate');

    if (startInput && !startInput.value) startInput.value = today;
    if (endInput && !endInput.value) endInput.value = today;
}

async function loadDetailedReport() {
    const startInput = document.getElementById('detailedStartDate');
    const endInput = document.getElementById('detailedEndDate');

    if (!startInput || !endInput) return;

    const startDate = startInput.value;
    const endDate = endInput.value;

    if (!startDate || !endDate) {
        notificationManager.error('برجاء تحديد الفترة من وإلى');
        return;
    }

    const loading = document.getElementById('detailedReportsLoading');
    const tableBody = document.getElementById('detailedReportsTableBody');
    const searchBtn = document.getElementById('searchDetailedReportBtn');

    if (loading) loading.classList.remove('hidden');
    if (tableBody) tableBody.innerHTML = ''; // Clear table
    if (searchBtn) {
        searchBtn.disabled = true;
        searchBtn.classList.add('opacity-75');
    }

    try {
        const response = await fetch(`/api/reports/summary?start_date=${startDate}&end_date=${endDate}`);

        if (response.ok) {
            const data = await response.json();

            // 1. Update Stats Cards
            if (document.getElementById('detailedRevenue')) document.getElementById('detailedRevenue').textContent = formatCurrency(data.total_sales);
            if (document.getElementById('detailedCash')) document.getElementById('detailedCash').textContent = formatCurrency(data.total_cash);
            if (document.getElementById('detailedCard')) document.getElementById('detailedCard').textContent = formatCurrency(data.total_card);
            if (document.getElementById('detailedDeficit')) document.getElementById('detailedDeficit').textContent = formatCurrency(data.total_deficit);
            if (document.getElementById('detailedSurplus')) document.getElementById('detailedSurplus').textContent = formatCurrency(data.total_surplus);

            // 2. Update Orders Count
            if (document.getElementById('detailedOrdersCount')) document.getElementById('detailedOrdersCount').textContent = `${data.total_orders} طلب`;

            // 3. Render Orders Table
            renderDetailedOrdersTable(data.orders);

        } else {
            console.error('Error fetching detailed report:', await response.text());
            notificationManager.error('حدث خطأ أثناء تحميل التقرير');
        }
    } catch (e) {
        console.error('Error loading detailed report:', e);
        notificationManager.error('خطأ في الاتصال بالخادم');
    } finally {
        if (loading) loading.classList.add('hidden');
        if (searchBtn) {
            searchBtn.disabled = false;
            searchBtn.classList.remove('opacity-75');
        }
    }
}

function renderDetailedOrdersTable(orders) {
    const tableBody = document.getElementById('detailedReportsTableBody');
    if (!tableBody) return;

    tableBody.innerHTML = '';

    if (!orders || orders.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="15" class="px-6 py-4 text-center text-gray-500">لا توجد طلبات في هذه الفترة</td></tr>';
        return;
    }

    orders.forEach((order, index) => {
        const orderQuantity = order.items ? order.items.length : (order.quantity || 0);

        // Status Badge
        let statusBadge = '';
        switch (order.status) {
            case 'completed': statusBadge = '<span class="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs font-bold">مكتمل</span>'; break;
            case 'pending': statusBadge = '<span class="px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs font-bold">قيد الانتظار</span>'; break;
            case 'cancelled': statusBadge = '<span class="px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs font-bold">ملغي</span>'; break;
            default: statusBadge = `<span class="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-xs font-bold">${order.status}</span>`;
        }

        // Format Date
        const dateObj = new Date(order.created_at);
        const timeStr = dateObj.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
        const dateStr = dateObj.toLocaleDateString('ar-EG');
        const total = parseFloat(order.total_amount || 0);
        const discount = parseFloat(order.discount_amount || 0);
        const tax = parseFloat(order.tax_amount || 0);
        const vat = parseFloat(order.vat_amount || 0);

        const row = document.createElement('tr');
        row.className = "bg-white border-b hover:bg-gray-50";
        row.innerHTML = `
            <td class="px-4 py-3 font-medium text-gray-900">${index + 1}</td>
            <td class="px-4 py-3 font-bold text-gray-900">#${order.order_number}</td>
            <td class="px-4 py-3">${order.table_number > 0 ? order.table_number : '-'}</td>
            <td class="px-4 py-3">${order.customer_name || '-'}</td>
            <td class="px-4 py-3 text-xs">${order.customer_phone || '-'}</td>
            <td class="px-4 py-3 text-center font-bold text-blue-600">${orderQuantity}</td>
            <td class="px-4 py-3 font-bold text-gray-900">${total.toFixed(2)}</td>
            <td class="px-4 py-3 text-red-500">${discount > 0 ? discount.toFixed(2) : '-'}</td>
            <td class="px-4 py-3 text-sm">${tax > 0 ? tax.toFixed(2) : '-'}</td>
            <td class="px-4 py-3 text-sm">${vat > 0 ? vat.toFixed(2) : '-'}</td>
            <td class="px-4 py-3">${statusBadge}</td>
            <td class="px-4 py-3 text-xs">${order.branch || 'الفرع الرئيسي'}</td>
            <td class="px-4 py-3 text-xs">${order.cashier || 'كاشير'}</td>
            <td class="px-4 py-3 text-xs text-gray-500">
                <div>${dateStr}</div>
                <div>${timeStr}</div>
            </td>
            <td class="px-4 py-3 flex gap-2">
                 <button onclick="showOrderDetails(${order.id})" class="text-blue-600 hover:text-blue-800" title="تفاصيل">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                </button>
                <button onclick="openPrintModal(${order.id}, '${order.status}')" class="text-gray-600 hover:text-gray-800" title="طباعة">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/></svg>
                </button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

function formatCurrency(value) {
    return parseFloat(value || 0).toFixed(2);
}

// Global Exports
window.showDetailedReports = showDetailedReports;
window.loadDetailedReport = loadDetailedReport;

// Initialize Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Detailed Reports Listeners
    const detailedReportBtn = document.getElementById('detailedReportBtn');
    if (detailedReportBtn) {
        detailedReportBtn.addEventListener('click', () => {
            // Reset styles of all report buttons
            ['dailyReportBtn', 'weeklyReportBtn', 'monthlyReportBtn', 'detailedReportBtn'].forEach(id => {
                const b = document.getElementById(id);
                if (b) b.classList.replace('bg-blue-50', 'bg-gray-50');
                if (b) b.classList.replace('border-blue-200', 'border-gray-200');
                if (b) b.classList.replace('text-blue-700', 'text-gray-700');
            });
            // Activate this button
            detailedReportBtn.classList.replace('bg-gray-50', 'bg-blue-50');
            detailedReportBtn.classList.replace('border-gray-200', 'border-blue-200');
            detailedReportBtn.classList.replace('text-gray-700', 'text-blue-700');

            showDetailedReports();
        });
    }

    // Search Button
    const searchDetailedBtn = document.getElementById('searchDetailedReportBtn');
    if (searchDetailedBtn) {
        searchDetailedBtn.addEventListener('click', loadDetailedReport);
    }
});
