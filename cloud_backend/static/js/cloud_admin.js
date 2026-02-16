// Cloud Admin - Simplified Read-Only Version
// Designed specifically for cloud dashboard (no local-only features)

let categories = [];
let products = [];
let shifts = [];
let orders = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    showMainContent();

    // Setup event listeners
    const tabs = ['statistics', 'categories', 'products', 'reports', 'orders', 'shifts'];
    tabs.forEach(tab => {
        const tabEl = document.getElementById(`${tab}Tab`);
        if (tabEl) {
            tabEl.addEventListener('click', () => showTab(tab));
        }
    });

    // Reports button
    const loadReportBtn = document.getElementById('loadReportBtn');
    if (loadReportBtn) {
        loadReportBtn.addEventListener('click', loadReports);
    }

    // Logout button
    const logoutBtn = document.querySelector('button[onclick="logout()"]');
    if (logoutBtn) {
        logoutBtn.onclick = logout;
    }
});

function showMainContent() {
    document.getElementById('mainContent').classList.remove('hidden');
    loadData().then(() => {
        showTab('statistics');
    });
}

// Load all data
async function loadData() {
    try {
        await Promise.all([
            loadCategories(),
            loadProducts(),
            loadShifts(),
            loadOrders()
        ]);
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        categories = await response.json();
        console.log('Categories loaded:', categories.length);
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        products = await response.json();
        console.log('Products loaded:', products.length);
    } catch (error) {
        console.error('Error loading products:', error);
    }
}

async function loadShifts() {
    try {
        const response = await fetch('/api/shifts');
        shifts = await response.json();
        console.log('Shifts loaded:', shifts.length);
    } catch (error) {
        console.error('Error loading shifts:', error);
    }
}

async function loadOrders() {
    try {
        const response = await fetch('/api/orders');
        orders = await response.json();
        console.log('Orders loaded:', orders.length);
    } catch (error) {
        console.error('Error loading orders:', error);
    }
}

// Show tab
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.add('hidden'));

    // Show selected tab
    const section = document.getElementById(`${tabName}Section`);
    if (section) {
        section.classList.remove('hidden');
    }

    // Update tab styling
    document.querySelectorAll('[id$="Tab"]').forEach(btn => {
        btn.classList.remove('bg-blue-50', 'border-blue-200', 'text-blue-700');
        btn.classList.add('bg-gray-50', 'border-gray-200', 'text-gray-700');
    });

    const activeTab = document.getElementById(`${tabName}Tab`);
    if (activeTab) {
        activeTab.classList.remove('bg-gray-50', 'border-gray-200', 'text-gray-700');
        activeTab.classList.add('bg-blue-50', 'border-blue-200', 'text-blue-700');
    }

    // Load tab-specific data
    switch (tabName) {
        case 'statistics':
            loadStatistics();
            break;
        case 'shifts':
            renderShifts();
            break;
        case 'orders':
            renderOrders();
            break;
        case 'reports':
            // Reports load on date selection
            break;
        case 'categories':
            renderCategories();
            break;
        case 'products':
            renderProducts();
            break;
    }
}

// Statistics
async function loadStatistics() {
    try {
        const response = await fetch('/api/admin/statistics');
        const stats = response.json();

        // Update statistics display
        document.getElementById('todaySales').textContent = stats.today?.total_sales?.toFixed(2) || '0.00';
        document.getElementById('todayOrders').textContent = stats.today?.total_orders || '0';
        document.getElementById('totalProducts').textContent = stats.total_products || '0';
        document.getElementById('totalCategories').textContent = stats.total_categories || '0';
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Render Categories (Read-Only)
function renderCategories() {
    const grid = document.getElementById('categoriesGrid');
    if (!grid) return;

    if (categories.length === 0) {
        grid.innerHTML = '<div class="col-span-full text-center py-8 text-gray-400">لا توجد فئات</div>';
        return;
    }

    grid.innerHTML = categories.map(cat => `
        <div class="category-card p-4 border-2 border-gray-200 rounded-lg">
            <h3 class="text-lg font-bold text-gray-800">${cat.name}</h3>
            <p class="text-sm text-gray-600">ID: ${cat.id}</p>
        </div>
    `).join('');
}

// Render Products (Read-Only)
function renderProducts() {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;

    if (products.length === 0) {
        grid.innerHTML = '<div class="col-span-full text-center py-8 text-gray-400">لا توجد منتجات</div>';
        return;
    }

    grid.innerHTML = products.map(product => `
        <div class="product-card p-4 border-2 border-gray-200 rounded-lg">
            <h3 class="text-lg font-bold text-gray-800">${product.name}</h3>
            <p class="text-blue-600 font-semibold">${product.price || 0} جنيه</p>
            <p class="text-sm text-gray-600">الفئة: ${product.category_name || '-'}</p>
        </div>
    `).join('');
}

// Render Shifts
function renderShifts() {
    const container = document.getElementById('shiftsContainer');
    if (!container) return;

    if (shifts.length === 0) {
        container.innerHTML = '<div class="text-center py-8 text-gray-400">لا توجد شيفتات</div>';
        return;
    }

    container.innerHTML = shifts.map(shift => {
        const isOpen = !shift.closed_at;
        const statusClass = isOpen ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700';
        const statusText = isOpen ? 'مفتوح' : 'مغلق';

        return `
            <div class="border-2 border-gray-200 rounded-lg p-4 hover:border-blue-300 transition cursor-pointer"
                 onclick="viewShiftDetails(${shift.id})">
                <div class="flex justify-between items-start mb-2">
                    <h3 class="text-xl font-bold text-gray-800">${shift.shift_name || `شيفت #${shift.id}`}</h3>
                    <span class="px-3 py-1 rounded-full text-sm font-semibold ${statusClass}">${statusText}</span>
                </div>
                <div class="grid grid-cols-2 gap-2 text-sm">
                    <div><span class="text-gray-600">الإيرادات:</span> <span class="font-bold">${shift.total_revenue || 0} جنيه</span></div>
                    <div><span class="text-gray-600">فتح:</span> ${shift.opened_at || '-'}</div>
                    <div><span class="text-gray-600">بواسطة:</span> ${shift.opened_by || '-'}</div>
                    ${shift.closed_at ? `<div><span class="text-gray-600">إغلاق:</span> ${shift.closed_at}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// View Shift Details
async function viewShiftDetails(shiftId) {
    try {
        const response = await fetch(`/api/shift/${shiftId}`);
        const shift = await response.json();

        const modal = document.getElementById('shiftDetailsModal');
        const content = document.getElementById('shiftDetailsContent');

        if (!modal || !content) return;

        const isOpen = !shift.closed_at;
        const statusClass = isOpen ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700';
        const statusText = isOpen ? 'مفتوح' : 'مغلق';

        content.innerHTML = `
            <div class="space-y-4">
                <div class="flex justify-between items-center pb-4 border-b">
                    <h3 class="text-2xl font-bold">${shift.shift_name}</h3>
                    <span class="px-4 py-2 rounded-full font-bold ${statusClass}">${statusText}</span>
                </div>
                
                <div class="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-lg">
                    <div><span class="font-semibold">فتح الشيفت:</span> ${shift.opened_at || '-'}</div>
                    <div><span class="font-semibold">بواسطة:</span> ${shift.opened_by || '-'}</div>
                    ${shift.closed_at ? `
                        <div><span class="font-semibold">إغلاق الشيفت:</span> ${shift.closed_at}</div>
                        <div><span class="font-semibold">بواسطة:</span> ${shift.closed_by || '-'}</div>
                    ` : ''}
                    <div><span class="font-semibold">الرصيد الافتتاحي:</span> ${shift.initial_cash || 0} جنيه</div>
                    <div><span class="font-semibold">إجمالي الإيرادات:</span> <span class="text-blue-600 font-bold">${shift.total_revenue || 0} جنيه</span></div>
                    <div><span class="font-semibold">عدد الطلبات:</span> ${shift.orders_count || 0}</div>
                </div>
                
                ${shift.orders && shift.orders.length > 0 ? `
                    <div>
                        <h4 class="font-bold text-lg mb-2">آخر الطلبات:</h4>
                        <div class="space-y-2">
                            ${shift.orders.slice(0, 10).map(order => `
                                <div class="flex justify-between p-2 bg-gray-50 rounded">
                                    <span>طلب #${order.id}</span>
                                    <span class="font-semibold">${order.total} جنيه</span>
                                    <span class="text-sm text-gray-600">${order.created_at}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        modal.classList.remove('hidden');
    } catch (error) {
        console.error('Error loading shift details:', error);
        showNotification('error', 'خطأ في تحميل تفاصيل الشيفت');
    }
}

function closeShiftDetailsModal() {
    const modal = document.getElementById('shiftDetailsModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// Render Orders
function renderOrders() {
    const container = document.getElementById('ordersTableBody');
    if (!container) return;

    if (orders.length === 0) {
        container.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-gray-400">لا توجد طلبات</td></tr>';
        return;
    }

    container.innerHTML = orders.map(order => {
        const statusClass = order.status === 'completed' ? 'bg-green-100 text-green-700' :
            order.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                'bg-red-100 text-red-700';
        const statusText = order.status === 'completed' ? 'مكتمل' :
            order.status === 'pending' ? 'قيد الانتظار' : order.status;

        return `
            <tr class="border-b hover:bg-gray-50">
                <td class="px-4 py-3">#${order.order_number || order.id}</td>
                <td class="px-4 py-3">${order.table_number || '-'}</td>
                <td class="px-4 py-3">${order.customer_name || '-'}</td>
                <td class="px-4 py-3 font-bold">${order.total_amount || 0} جنيه</td>
                <td class="px-4 py-3"><span class="px-2 py-1 rounded text-sm ${statusClass}">${statusText}</span></td>
                <td class="px-4 py-3">
                    <button onclick="viewOrder(${order.id})" 
                            class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600">
                        عرض
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Load Reports
async function loadReports() {
    const dateInput = document.getElementById('reportDateInput');
    if (!dateInput || !dateInput.value) {
        showNotification('error', 'الرجاء اختيار تاريخ');
        return;
    }

    try {
        const response = await fetch(`/api/reports/daily?report_date=${dateInput.value}`);
        const data = await response.json();

        const container = document.getElementById('reportsTableBody');
        if (!container) return;

        if (!data.orders || data.orders.length === 0) {
            container.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-gray-400">لا توجد طلبات في هذا التاريخ</td></tr>';
            return;
        }

        container.innerHTML = data.orders.map(order => {
            const statusClass = order.status === 'completed' ? 'bg-green-100 text-green-700' :
                order.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-red-100 text-red-700';
            const statusText = order.status === 'completed' ? 'مكتمل' :
                order.status === 'pending' ? 'قيد الانتظار' : order.status;

            return `
                <tr class="border-b hover:bg-gray-50">
                    <td class="px-4 py-3">#${order.order_number || order.id}</td>
                    <td class="px-4 py-3">${order.created_at || '-'}</td>
                    <td class="px-4 py-3 font-bold">${order.total_amount || 0} جنيه</td>
                    <td class="px-4 py-3"><span class="px-2 py-1 rounded text-sm ${statusClass}">${statusText}</span></td>
                    <td class="px-4 py-3">
                        <button onclick="viewOrder(${order.id})" 
                                class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600">
                            👁️ عرض
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // Update summary
        document.getElementById('reportTotalSales').textContent = `${data.total_sales?.toFixed(2) || '0.00'} جنيه`;
        document.getElementById('reportTotalOrders').textContent = data.order_count || 0;

    } catch (error) {
        console.error('Error loading reports:', error);
        showNotification('error', 'خطأ في تحميل التقارير');
    }
}

// Logout
function logout() {
    sessionStorage.removeItem('authenticated');
    sessionStorage.removeItem('pageType');
    window.location.href = '/';
}

// Notification helper
function showNotification(type, message) {
    console.log(`[${type.toUpperCase()}] ${message}`);
    // Use existing notification system if available
    if (window.showNotification) {
        window.showNotification(type, message);
    }
}
