// Global state
let selectedItems = [];
let categories = [];
let products = [];
let filteredProducts = [];
let selectedCategoryId = null;
let currentTableInfo = null; // Store current table info
let searchQuery = ''; // Search query for tablet

// Get server IP from current location (works on same WiFi network)
// For tablets on the same network, they should access via the server's IP address
// Example: If server is at 192.168.1.100, tablets access http://192.168.1.100:3000/tablet
function getServerIP() {
    // Use current hostname (works automatically on same network)
    // If accessing from tablet via IP (e.g., 192.168.1.100), hostname will be that IP
    // If accessing via localhost, use localhost (for development)
    return window.location.hostname;
}

// Use current hostname for API (works on same network)
// This automatically works when tablets access via server IP on same WiFi
const SERVER_IP = getServerIP();
const API_BASE = `http://${window.location.hostname}:3000`;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadCategories();
    loadProducts();
    setupEventListeners();
    setupWebSocket();
    setupSearch();

    // Check table status when table number changes
    const tableNumberInput = document.getElementById('tableNumber');
    if (tableNumberInput) {
        const debouncedCheckTable = window.PerformanceUtils ? window.PerformanceUtils.debounce(checkTableStatus, 300) : checkTableStatus;
        tableNumberInput.addEventListener('input', debouncedCheckTable);
    }
});

// Setup search functionality (with debouncing)
function setupSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        const debouncedApplyFilters = window.PerformanceUtils ? window.PerformanceUtils.debounce(() => {
            searchQuery = searchInput.value.trim().toLowerCase();
            applyFilters();
        }, 200) : () => {
            searchQuery = searchInput.value.trim().toLowerCase();
            applyFilters();
        };
        searchInput.addEventListener('input', debouncedApplyFilters);
    }
}

// Check if table exists and is open
async function checkTableStatus() {
    const tableNumberInput = document.getElementById('tableNumber');
    const tableNumber = parseInt(tableNumberInput.value) || 0;
    const tableStatusDiv = document.getElementById('tableStatus');

    if (tableNumber <= 0) {
        tableStatusDiv.classList.add('hidden');
        currentTableInfo = null;
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/tables/${tableNumber}`);
        if (response.ok) {
            const table = await response.json();
            currentTableInfo = table;
            tableStatusDiv.classList.remove('hidden');
            tableStatusDiv.className = 'mt-1 sm:mt-2 text-xs font-semibold text-green-600';
            tableStatusDiv.textContent = `✓ طاولة مفتوحة - ${table.customer_name || 'بدون اسم'}`;
        } else {
            currentTableInfo = null;
            tableStatusDiv.classList.remove('hidden');
            tableStatusDiv.className = 'mt-1 sm:mt-2 text-xs font-semibold text-blue-600';
            tableStatusDiv.textContent = 'ℹ طاولة جديدة - سيتم فتحها تلقائياً';
        }
    } catch (error) {
        currentTableInfo = null;
        tableStatusDiv.classList.remove('hidden');
        tableStatusDiv.className = 'mt-1 sm:mt-2 text-xs font-semibold text-blue-600';
        tableStatusDiv.textContent = 'ℹ طاولة جديدة - سيتم فتحها تلقائياً';
    }
}

// Setup WebSocket for real-time updates (works on same network)
function setupWebSocket() {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Use current hostname for WebSocket (works automatically on same network)
        const wsUrl = `${protocol}//${window.location.hostname}:3000/ws`;
        window.ws = new WebSocket(wsUrl);

        window.ws.onopen = () => {
            console.log('WebSocket connected for real-time updates');
        };

        window.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('Tablet received WebSocket message:', data);

                // Real-time updates from admin or cashier
                if (data.type === 'categories_updated' || data.type === 'products_updated') {
                    loadCategories();
                    loadProducts();
                    if (window.notificationManager) {
                        window.notificationManager.info('تم تحديث المنتجات');
                    }
                } else if (data.type === 'order_ready' && data.table_number) {
                    // Order is ready - show notification with sound
                    console.log('Order ready received for table:', data.table_number);
                    showOrderReadyModal(data.table_number, data.message || 'طلبك جاهز للاستلام');
                }
            } catch (e) {
                console.error('Error parsing WebSocket message:', e);
            }
        };

        window.ws.onerror = (error) => {
            console.warn('WebSocket error:', error);
            // Silently fail, will retry
        };

        window.ws.onclose = () => {
            console.log('WebSocket closed, reconnecting...');
            // Reconnect after 5 seconds
            setTimeout(setupWebSocket, 5000);
        };
    } catch (e) {
        console.warn('WebSocket not available, using polling instead');
        // WebSocket not available, use polling instead
        setInterval(() => {
            loadCategories();
            loadProducts();
        }, 5000);
    }
}

// Global variable to store selected product for size selection
let selectedProductForSize = null;

// Setup event listeners
function setupEventListeners() {
    document.getElementById('submitOrderBtn').addEventListener('click', submitOrder);
    document.getElementById('clearBtn').addEventListener('click', clearSelection);
    document.getElementById('additionsBtn').addEventListener('click', showAdditionsModal);
    document.getElementById('closeAdditionsModalBtn').addEventListener('click', closeAdditionsModal);
    document.getElementById('cancelAdditionsBtn').addEventListener('click', closeAdditionsModal);
    document.getElementById('saveAdditionsBtn').addEventListener('click', saveAdditions);
    document.getElementById('additionsProductSelect').addEventListener('change', loadProductAdditions);

    // Size modal event listeners
    document.getElementById('closeSizeModalBtn').addEventListener('click', closeSizeModal);
    document.getElementById('cancelSizeBtn').addEventListener('click', closeSizeModal);
    document.getElementById('confirmSizeBtn').addEventListener('click', confirmSizeSelection);
}

// Load categories
async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE}/api/categories`);
        categories = await response.json();
        renderCategories();
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// Render categories - exact style as in the image
function renderCategories() {
    const container = document.getElementById('categoryTabs');
    container.innerHTML = '';

    const allTab = document.createElement('button');
    allTab.className = `px-4 sm:px-6 py-2 rounded-full font-bold text-xs sm:text-sm whitespace-nowrap transition ${selectedCategoryId === null ? 'bg-gray-200 text-gray-700' : 'bg-white border-2 border-gray-400 text-gray-700 hover:bg-gray-50'}`;
    allTab.textContent = 'الكل';
    allTab.onclick = () => filterByCategory(null);
    container.appendChild(allTab);

    categories.forEach(cat => {
        const tab = document.createElement('button');
        tab.className = `px-4 sm:px-6 py-2 rounded-full font-bold text-xs sm:text-sm whitespace-nowrap transition ${selectedCategoryId === cat.id ? 'bg-gray-200 text-gray-700' : 'bg-white border-2 border-gray-400 text-gray-700 hover:bg-gray-50'}`;
        tab.textContent = cat.name;
        tab.onclick = () => filterByCategory(cat.id);
        container.appendChild(tab);
    });
}

// Load products
async function loadProducts() {
    try {
        const response = await fetch(`${API_BASE}/api/products?enabled=true&exclude_hidden_tablet=true`);
        products = await response.json();
        filterProducts();
    } catch (error) {
        console.error('Error loading products:', error);
    }
}

// Filter products by category
function filterProducts() {
    applyFilters();
}

// Filter by category
function filterByCategory(categoryId) {
    selectedCategoryId = categoryId;
    renderCategories();
    applyFilters();
}

function applyFilters() {
    let filtered = products;

    // Filter by category
    if (selectedCategoryId !== null) {
        filtered = filtered.filter(p => p.category_id === selectedCategoryId);
    }

    // Filter by search query
    if (searchQuery) {
        filtered = filtered.filter(p =>
            p.name.toLowerCase().includes(searchQuery) ||
            (p.description && p.description.toLowerCase().includes(searchQuery))
        );
    }

    filteredProducts = filtered;
    renderProducts();
}

// Render products (optimized with DocumentFragment)
function renderProducts() {
    const container = document.getElementById('productsGrid');
    if (!container) return;

    if (filteredProducts.length === 0) {
        container.innerHTML = '<div class="col-span-4 text-center text-gray-400 py-12 text-sm sm:text-base">لا توجد منتجات</div>';
        return;
    }

    // Use DocumentFragment for better performance
    const fragment = document.createDocumentFragment();

    filteredProducts.forEach(product => {
        const card = document.createElement('div');
        card.className = 'product-card bg-white border border-gray-200 rounded-lg overflow-hidden cursor-pointer shadow-sm hover:shadow-md transition-all duration-200';
        card.onclick = () => handleProductClick(product.id);

        // Handle image path
        let imageHtml = '';
        if (product.image_path && product.image_path.trim() !== '') {
            let imagePath = product.image_path;
            // If path is relative (starts with /), prepend API_BASE
            // This ensures we fetch images from port 3000 (Main Server) not 3001 (Tablet Server)
            if (imagePath.startsWith('/')) {
                imagePath = `${API_BASE}${imagePath}`;
            } else if (!imagePath.startsWith('http')) {
                imagePath = `${API_BASE}/${imagePath}`;
            }

            imageHtml = `<img loading="lazy" src="${imagePath}" alt="${product.name}" class="w-full h-full object-cover" onerror="this.parentElement.innerHTML='<div class=\\'text-xs text-gray-400 text-center p-4\\'>لا توجد صورة</div>'">`;
        } else {
            imageHtml = '<div class="text-xs text-gray-400 text-center p-4">لا توجد صورة</div>';
        }

        // Format prices as text
        let priceText = '';
        const hasSizes = product.has_sizes === true ||
            product.has_sizes === 1 ||
            product.has_sizes === "1" ||
            (product.price_s && parseFloat(product.price_s) > 0) ||
            (product.price_m && parseFloat(product.price_m) > 0) ||
            (product.price_l && parseFloat(product.price_l) > 0);

        if (hasSizes) {
            const prices = [];
            if (product.price_s && parseFloat(product.price_s) > 0) prices.push({ label: 'S', value: parseFloat(product.price_s).toFixed(0) });
            if (product.price_m && parseFloat(product.price_m) > 0) prices.push({ label: 'M', value: parseFloat(product.price_m).toFixed(0) });
            if (product.price_l && parseFloat(product.price_l) > 0) prices.push({ label: 'L', value: parseFloat(product.price_l).toFixed(0) });

            if (prices.length > 0) {
                priceText = prices.map(p => `${p.label}: ${p.value}`).join(' | ');
            } else {
                priceText = parseFloat(product.price).toFixed(0);
            }
        } else {
            priceText = parseFloat(product.price).toFixed(0);
        }

        card.innerHTML = `
            <div class="relative">
                <div class="w-full h-32 sm:h-40 bg-gray-100 flex items-center justify-center overflow-hidden">
                    ${imageHtml}
                </div>
            </div>
            <div class="p-3 bg-white">
                <div class="font-bold text-gray-800 text-sm sm:text-base mb-1">${product.name}</div>
                ${product.description ? `<div class="text-xs text-gray-500 mb-2 min-h-[32px] line-clamp-2">${product.description}</div>` : ''}
                <div class="text-xs font-semibold text-gray-700">${priceText}</div>
            </div>
        `;
        fragment.appendChild(card);
    });

    // Single DOM update
    container.innerHTML = '';
    container.appendChild(fragment);
}

// Handle product click - show size modal if needed
async function handleProductClick(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    const hasSizes = product.has_sizes === true ||
        product.has_sizes === 1 ||
        product.has_sizes === "1" ||
        (product.price_s && parseFloat(product.price_s) > 0) ||
        (product.price_m && parseFloat(product.price_m) > 0) ||
        (product.price_l && parseFloat(product.price_l) > 0);

    if (hasSizes) {
        // Show size selection modal
        showSizeModal(product);
    } else {
        // No sizes - add directly
        addItem(productId);
    }
}

// Show size selection modal
function showSizeModal(product) {
    selectedProductForSize = product;
    const modal = document.getElementById('sizeModal');
    const productName = document.getElementById('sizeModalProductName');
    const sizeOptions = document.getElementById('sizeOptions');

    productName.textContent = product.name;

    // Clear previous options
    sizeOptions.innerHTML = '';

    // Add available sizes
    const sizes = [];
    if (product.price_s && parseFloat(product.price_s) > 0) {
        sizes.push({ label: 'S', value: 'S', price: parseFloat(product.price_s) });
    }
    if (product.price_m && parseFloat(product.price_m) > 0) {
        sizes.push({ label: 'M', value: 'M', price: parseFloat(product.price_m) });
    }
    if (product.price_l && parseFloat(product.price_l) > 0) {
        sizes.push({ label: 'L', value: 'L', price: parseFloat(product.price_l) });
    }

    // If no sizes found, use default price
    if (sizes.length === 0) {
        sizes.push({ label: 'عادي', value: null, price: parseFloat(product.price) });
    }

    // Render size buttons
    sizes.forEach(size => {
        const sizeBtn = document.createElement('button');
        sizeBtn.className = 'w-full p-4 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-lg shadow-sm transition size-option-btn';
        sizeBtn.setAttribute('data-size', size.value || '');
        sizeBtn.setAttribute('data-price', size.price);
        sizeBtn.innerHTML = `
            <div class="flex justify-between items-center">
                <span>${size.label}</span>
                <span class="text-teal-600">${size.price.toFixed(0)} ج.م</span>
            </div>
        `;

        sizeBtn.addEventListener('click', function () {
            // Remove selection from all buttons
            document.querySelectorAll('.size-option-btn').forEach(btn => {
                btn.classList.remove('bg-teal-600', 'text-white', 'border-teal-600');
                btn.classList.add('bg-white', 'border-gray-300', 'text-gray-800');
            });
            // Select this button
            this.classList.remove('bg-white', 'border-gray-300', 'text-gray-800');
            this.classList.add('bg-teal-600', 'text-white', 'border-teal-600');
        });

        sizeOptions.appendChild(sizeBtn);
    });

    // Show modal
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    modal.style.zIndex = '99999';
}

// Close size modal
function closeSizeModal() {
    const modal = document.getElementById('sizeModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
    selectedProductForSize = null;
}

// Confirm size selection
function confirmSizeSelection() {
    if (!selectedProductForSize) {
        closeSizeModal();
        return;
    }

    // Get selected size
    const selectedBtn = document.querySelector('.size-option-btn.bg-teal-600');
    if (!selectedBtn) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء اختيار حجم');
        }
        return;
    }

    const size = selectedBtn.getAttribute('data-size') || null;
    const price = parseFloat(selectedBtn.getAttribute('data-price'));

    // Add item with selected size
    addItemWithSize(selectedProductForSize.id, size, price);

    // Close modal
    closeSizeModal();
}

// Add item with size
async function addItemWithSize(productId, size, priceOverride = null) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    // Calculate price based on size or use override
    let price = priceOverride !== null ? priceOverride : parseFloat(product.price);
    if (priceOverride === null) {
        if (size === 'S' && product.price_s && parseFloat(product.price_s) > 0) {
            price = parseFloat(product.price_s);
        } else if (size === 'M' && product.price_m && parseFloat(product.price_m) > 0) {
            price = parseFloat(product.price_m);
        } else if (size === 'L' && product.price_l && parseFloat(product.price_l) > 0) {
            price = parseFloat(product.price_l);
        }
    }

    const itemKey = `${productId}_${size || 'default'}`;
    const existingItem = selectedItems.find(item =>
        item.product_id === productId &&
        (item.size || 'default') === (size || 'default')
    );

    if (existingItem) {
        existingItem.quantity += 1;
        existingItem.total = existingItem.price * existingItem.quantity;
    } else {
        selectedItems.push({
            product_id: productId,
            product_name: product.name,
            quantity: 1,
            price: price,
            total: price,
            size: size || null,
            additions: null
        });
    }

    renderSelectedItems();
    updateTotal();

    // Show notification
    if (window.notificationManager) {
        window.notificationManager.success(`تم إضافة ${product.name}${size ? ` (${size})` : ''}`, 2000);
    }
}

// Add item
function addItem(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    const existingItem = selectedItems.find(item =>
        item.product_id === productId &&
        !item.size
    );

    if (existingItem) {
        existingItem.quantity += 1;
        existingItem.total = existingItem.price * existingItem.quantity;
    } else {
        selectedItems.push({
            product_id: productId,
            product_name: product.name,
            quantity: 1,
            price: parseFloat(product.price),
            total: parseFloat(product.price),
            size: null,
            additions: null
        });
    }

    renderSelectedItems();
    updateTotal();

    // Show notification
    if (window.notificationManager) {
        window.notificationManager.success(`تم إضافة ${product.name}`, 2000);
    }
}

// Remove item
function removeItem(productId, size = null) {
    const item = selectedItems.find(item =>
        item.product_id === productId &&
        (item.size || null) === (size || null)
    );
    if (item && window.notificationManager) {
        window.notificationManager.info(`تم حذف ${item.product_name}${item.size ? ` (${item.size})` : ''}`, 2000);
    }
    selectedItems = selectedItems.filter(item =>
        !(item.product_id === productId && (item.size || null) === (size || null))
    );
    renderSelectedItems();
    updateTotal();
}

// Update quantity
function updateQuantity(productId, change, size = null) {
    const item = selectedItems.find(item =>
        item.product_id === productId &&
        (item.size || null) === (size || null)
    );
    if (!item) return;

    item.quantity = Math.max(1, item.quantity + change);
    item.total = item.price * item.quantity;

    if (item.quantity === 0) {
        removeItem(productId, size);
    } else {
        renderSelectedItems();
        updateTotal();
    }
}

// Update total
function updateTotal() {
    const total = selectedItems.reduce((sum, item) => sum + item.total, 0);
    document.getElementById('totalAmount').textContent = total.toFixed(2);
}

// Render selected items
function renderSelectedItems() {
    const container = document.getElementById('selectedItems');

    if (selectedItems.length === 0) {
        container.innerHTML = '<div class="text-center text-gray-400 py-4 text-xs sm:text-sm">لا توجد عناصر في الطلب</div>';
        return;
    }

    container.innerHTML = selectedItems.map((item, index) => `
        <div class="flex items-center justify-between p-2 sm:p-3 bg-gradient-to-r from-gray-50 to-white rounded-lg border-2 border-gray-200 shadow-sm">
            <div class="flex-1">
                <div class="font-semibold text-gray-800 text-xs sm:text-sm">
                    ${item.product_name}${item.size ? ` <span class="text-xs text-gray-700 font-bold">(${item.size})</span>` : ''}
                    ${item.additions ? ` <span class="text-xs text-teal-600 font-semibold">+ ${item.additions}</span>` : ''}
                </div>
                <div class="text-xs text-gray-500">${item.price.toFixed(2)} × ${item.quantity} = ${item.total.toFixed(2)}</div>
            </div>
            <div class="flex items-center gap-1 sm:gap-2">
                <button onclick="updateQuantity(${item.product_id}, -1, ${item.size ? `'${item.size}'` : 'null'})" class="w-7 h-7 sm:w-8 sm:h-8 bg-gray-200 rounded-lg flex items-center justify-center hover:bg-gray-300 font-bold text-gray-700 shadow-sm text-xs sm:text-sm">-</button>
                <span class="text-sm sm:text-base font-bold w-8 sm:w-12 text-center text-gray-800">${item.quantity}</span>
                <button onclick="updateQuantity(${item.product_id}, 1, ${item.size ? `'${item.size}'` : 'null'})" class="w-7 h-7 sm:w-8 sm:h-8 bg-gray-200 rounded-lg flex items-center justify-center hover:bg-gray-300 font-bold text-gray-700 shadow-sm text-xs sm:text-sm">+</button>
                <button onclick="removeItem(${item.product_id}, ${item.size ? `'${item.size}'` : 'null'})" class="ml-1 sm:ml-2 p-1 sm:p-2 text-red-600 hover:bg-red-50 rounded-lg transition">
                    <svg class="w-4 h-4 sm:w-5 sm:h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

// Show additions modal
async function showAdditionsModal() {
    if (selectedItems.length === 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء إضافة منتجات للطلب أولاً');
        }
        return;
    }

    // Populate product select
    const productSelect = document.getElementById('additionsProductSelect');
    if (productSelect) {
        productSelect.innerHTML = '<option value="">-- اختر منتج --</option>';
        selectedItems.forEach((item, index) => {
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
}

// Load additions options
async function loadAdditionsOptions() {
    try {
        const response = await fetch(`${API_BASE}/api/additions`);
        if (response.ok) {
            const additions = await response.json();
            const optionsContainer = document.getElementById('additionsOptions');
            if (optionsContainer) {
                if (additions.length === 0) {
                    optionsContainer.innerHTML = '<div class="col-span-3 text-center text-gray-500 py-8 text-sm sm:text-base">لا توجد إضافات متاحة</div>';
                    return;
                }

                optionsContainer.innerHTML = additions.map(addition => `
                    <button class="addition-option-btn w-full px-3 sm:px-4 py-3 sm:py-4 bg-white border-2 border-gray-300 text-gray-800 rounded-lg font-bold text-sm sm:text-base shadow-sm transition text-center" 
                            data-addition-id="${addition.id}" data-addition-name="${addition.name}">
                        <span class="addition-name">${addition.name}</span>
                    </button>
                `).join('');

                // Add click listeners
                document.querySelectorAll('.addition-option-btn').forEach(btn => {
                    btn.addEventListener('click', function () {
                        if (!this.disabled) {
                            toggleAddition(this);
                        }
                    });
                });
            }
        } else {
            console.error('Failed to load additions:', response.status);
            const optionsContainer = document.getElementById('additionsOptions');
            if (optionsContainer) {
                optionsContainer.innerHTML = '<div class="col-span-3 text-center text-red-500 py-8 text-sm sm:text-base">خطأ في تحميل الإضافات</div>';
            }
        }
    } catch (error) {
        console.error('Error loading additions:', error);
        const optionsContainer = document.getElementById('additionsOptions');
        if (optionsContainer) {
            optionsContainer.innerHTML = `<div class="col-span-3 text-center text-red-500 py-8 text-sm sm:text-base">خطأ في تحميل الإضافات: ${error.message}</div>`;
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
    const item = selectedItems[itemIndex];
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
    const item = selectedItems[itemIndex];
    if (!item) return;

    // Get selected additions
    const selectedAdditions = [];
    document.querySelectorAll('.addition-option-btn.bg-green-500').forEach(btn => {
        const additionName = btn.getAttribute('data-addition-name');
        selectedAdditions.push(additionName);
    });

    // Update item
    item.additions = selectedAdditions.length > 0 ? selectedAdditions.join(', ') : null;

    // Update display
    renderSelectedItems();

    // Close modal
    closeAdditionsModal();

    if (window.notificationManager) {
        window.notificationManager.success('تم حفظ الإضافات بنجاح');
    }
}

// Submit order - NO CONFIRMATION, send immediately
async function submitOrder() {
    if (selectedItems.length === 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء إضافة منتجات للطلب');
        }
        return;
    }

    const tableNumberInput = document.getElementById('tableNumber');
    const tableNumber = parseInt(tableNumberInput.value) || 0;
    if (tableNumber <= 0) {
        if (window.notificationManager) {
            window.notificationManager.warning('الرجاء إدخال رقم طاولة صحيح');
        }
        return;
    }

    const customerName = document.getElementById('customerName').value;
    const notes = document.getElementById('notes').value;

    // Disable submit button
    const submitBtn = document.getElementById('submitOrderBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'جاري الإرسال...';

    try {
        // Check if table exists and has an active order
        let existingOrderId = null;
        if (currentTableInfo && currentTableInfo.order_id) {
            // Table exists and has an order - add items to existing order
            existingOrderId = currentTableInfo.order_id;

            // Update existing order with new items
            const updateResponse = await fetch(`${API_BASE}/api/orders/${existingOrderId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    table_number: tableNumber,
                    customer_name: customerName || null,
                    notes: notes || null,
                    items: selectedItems.map(item => ({
                        product_id: item.product_id,
                        quantity: item.quantity,
                        size: item.size || null,
                        additions: item.additions || null
                    }))
                })
            });

            if (!updateResponse.ok) {
                const errorData = await updateResponse.json().catch(() => ({ detail: 'Failed to update order' }));
                throw new Error(errorData.detail || 'Failed to update order');
            }

            const updatedOrder = await updateResponse.json();

            // Print kitchen ticket automatically (without prices)
            try {
                await fetch(`${API_BASE}/api/print/kitchen/${existingOrderId}`, { method: 'POST' });
                console.log('Kitchen ticket printed automatically for table', tableNumber);
            } catch (error) {
                console.warn('Failed to print kitchen ticket automatically:', error);
            }

            // Clear selection immediately
            clearSelection();

            // Clear entire form
            clearForm();

            // Show success notification with clear message
            setTimeout(() => {
                if (window.notificationManager) {
                    window.notificationManager.success(`✅ تم إضافة المنتجات للطاولة ${tableNumber} بنجاح`, 3000);
                } else {
                    alert(`تم إضافة المنتجات للطاولة ${tableNumber} بنجاح`);
                }
            }, 100);

        } else {
            // Table doesn't exist or has no order - create new order
            const response = await fetch(`${API_BASE}/api/orders`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    table_number: tableNumber,
                    customer_name: customerName || null,
                    notes: notes || null,
                    items: selectedItems.map(item => ({
                        product_id: item.product_id,
                        quantity: item.quantity,
                        size: item.size || null,
                        additions: item.additions || null
                    }))
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Failed to submit order' }));
                throw new Error(errorData.detail || 'Failed to submit order');
            }

            const order = await response.json();

            // Note: Printing is now handled automatically in the backend
            // No need to call print endpoint from frontend - it's automatic
            console.log('Order created successfully, printing handled automatically by backend');

            // Clear selection immediately
            clearSelection();

            // Clear entire form
            clearForm();

            // Show success notification with clear message
            setTimeout(() => {
                if (window.notificationManager) {
                    window.notificationManager.success(`✅ تم إرسال الطلب للطاولة ${tableNumber} بنجاح`, 3000);
                } else {
                    alert(`تم إرسال الطلب للطاولة ${tableNumber} بنجاح`);
                }
            }, 100);
        }
    } catch (error) {
        console.error('Error submitting order:', error);
        if (window.notificationManager) {
            window.notificationManager.error('خطأ في إرسال الطلب: ' + (error.message || 'خطأ غير معروف'), 4000);
        }
    } finally {
        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.textContent = 'إرسال الطلب';
    }
}

// Clear entire form
function clearForm() {
    // Clear table number
    const tableNumberInput = document.getElementById('tableNumber');
    if (tableNumberInput) {
        tableNumberInput.value = '';
    }

    // Hide table status
    const tableStatusDiv = document.getElementById('tableStatus');
    if (tableStatusDiv) {
        tableStatusDiv.classList.add('hidden');
    }

    // Clear table info
    currentTableInfo = null;
}

// Clear selection
function clearSelection() {
    selectedItems = [];
    const customerNameInput = document.getElementById('customerName');
    if (customerNameInput) {
        customerNameInput.value = '';
    }
    const notesInput = document.getElementById('notes');
    if (notesInput) {
        notesInput.value = '';
    }
    renderSelectedItems();
    updateTotal();
}

// Play ringtone sound (like phone call)
let ringtoneInterval = null;
let ringtoneAudioContext = null;

function playRingtone() {
    try {
        console.log('Starting ringtone...');

        // Create audio context for ringtone
        ringtoneAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        if (ringtoneAudioContext.state === 'suspended') {
            ringtoneAudioContext.resume();
        }

        // Phone ringtone pattern: two tones (high-low) repeating
        function playPhoneRing() {
            if (!ringtoneAudioContext) return;

            const now = ringtoneAudioContext.currentTime;

            // First tone (high frequency)
            const osc1 = ringtoneAudioContext.createOscillator();
            const gain1 = ringtoneAudioContext.createGain();
            osc1.connect(gain1);
            gain1.connect(ringtoneAudioContext.destination);

            osc1.frequency.value = 800;
            osc1.type = 'sine';
            gain1.gain.setValueAtTime(0, now);
            gain1.gain.linearRampToValueAtTime(0.4, now + 0.1);
            gain1.gain.linearRampToValueAtTime(0, now + 0.4);

            osc1.start(now);
            osc1.stop(now + 0.4);

            // Second tone (lower frequency) - starts after first tone
            const osc2 = ringtoneAudioContext.createOscillator();
            const gain2 = ringtoneAudioContext.createGain();
            osc2.connect(gain2);
            gain2.connect(ringtoneAudioContext.destination);

            osc2.frequency.value = 600;
            osc2.type = 'sine';
            gain2.gain.setValueAtTime(0, now + 0.4);
            gain2.gain.linearRampToValueAtTime(0.4, now + 0.5);
            gain2.gain.linearRampToValueAtTime(0, now + 0.8);

            osc2.start(now + 0.4);
            osc2.stop(now + 0.8);
        }

        // Play ringtone pattern every 2 seconds (like real phone)
        playPhoneRing(); // Play immediately
        ringtoneInterval = setInterval(playPhoneRing, 2000);

        console.log('Ringtone started');
    } catch (e) {
        console.error('Could not play ringtone:', e);
        // Fallback: try simple beep
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            if (audioContext.state === 'suspended') {
                audioContext.resume();
            }

            function playSimpleRing() {
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();

                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);

                oscillator.frequency.value = 800;
                oscillator.type = 'sine';
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

                oscillator.start();
                oscillator.stop(audioContext.currentTime + 0.5);
            }

            ringtoneInterval = setInterval(playSimpleRing, 1000);
            playSimpleRing();
        } catch (e2) {
            console.error('Fallback ringtone also failed:', e2);
        }
    }
}

function stopRingtone() {
    console.log('Stopping ringtone...');
    if (ringtoneInterval) {
        clearInterval(ringtoneInterval);
        ringtoneInterval = null;
    }
    if (ringtoneAudioContext) {
        try {
            ringtoneAudioContext.close();
        } catch (e) {
            // Ignore errors when closing
        }
        ringtoneAudioContext = null;
    }
    console.log('Ringtone stopped');
}

// Show order ready modal
function showOrderReadyModal(tableNumber, message) {
    console.log('showOrderReadyModal called with:', { tableNumber, message });
    const modal = document.getElementById('orderReadyModal');
    const tableNumberSpan = document.getElementById('orderReadyTableNumber');
    const messageEl = document.getElementById('orderReadyMessage');
    const titleEl = document.getElementById('orderReadyTitle');
    const confirmBtn = document.getElementById('orderReadyConfirmBtn');

    if (!modal) {
        console.error('Order ready modal not found!');
        return;
    }

    console.log('Modal elements found:', { modal: !!modal, tableNumberSpan: !!tableNumberSpan, messageEl: !!messageEl, confirmBtn: !!confirmBtn });

    // Update modal content
    if (tableNumberSpan) {
        tableNumberSpan.textContent = tableNumber;
        console.log('Table number updated to:', tableNumber);
    }
    if (titleEl) {
        titleEl.textContent = message || 'طلبك جاهز للاستلام';
    }
    if (messageEl) {
        messageEl.innerHTML = `الطاولة رقم <span id="orderReadyTableNumber">${tableNumber}</span>`;
    }

    // Show modal
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
    modal.style.zIndex = '99999';
    console.log('Modal shown');

    // Play ringtone
    console.log('Playing ringtone...');
    playRingtone();

    // Show notification
    if (window.notificationManager) {
        window.notificationManager.success(`🔔 ${message || 'طلبك جاهز للاستلام'} - الطاولة ${tableNumber}`, 10000);
        console.log('Notification shown');
    } else {
        console.warn('NotificationManager not available');
    }

    // Handle confirm button
    if (confirmBtn) {
        // Remove old listeners by cloning
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

        newConfirmBtn.onclick = () => {
            console.log('Confirm button clicked');
            stopRingtone();
            modal.classList.add('hidden');
            modal.style.display = 'none';

            if (window.notificationManager) {
                window.notificationManager.success('تم تأكيد الاستلام', 2000);
            }
        };
        console.log('Confirm button listener attached');
    } else {
        console.error('Confirm button not found!');
    }
}

// Make functions global
window.addItem = addItem;
window.removeItem = removeItem;
window.updateQuantity = updateQuantity;
window.handleProductClick = handleProductClick;
