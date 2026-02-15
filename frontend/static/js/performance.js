// Performance optimization utilities

// Debounce function for input events
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle function for scroll and resize events
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Request cache for API calls
const apiCache = new Map();
const CACHE_DURATION = 30000; // 30 seconds

function cachedFetch(url, options = {}, cacheKey = null) {
    const key = cacheKey || url;
    const cached = apiCache.get(key);
    const now = Date.now();
    
    if (cached && (now - cached.timestamp) < CACHE_DURATION) {
        // Return a Response-like object that works with .json()
        return Promise.resolve({
            ok: true,
            status: 200,
            statusText: 'OK',
            headers: new Headers({ 'Content-Type': 'application/json' }),
            json: () => Promise.resolve(cached.data),
            text: () => Promise.resolve(JSON.stringify(cached.data)),
            clone: function() { return this; }
        });
    }
    
    return fetch(url, options).then(response => {
        if (response.ok) {
            return response.clone().json().then(data => {
                apiCache.set(key, { data, timestamp: now });
                return response;
            }).catch(() => response);
        }
        return response;
    });
}

// Clear cache
function clearCache(pattern = null) {
    if (pattern) {
        for (const key of apiCache.keys()) {
            if (key.includes(pattern)) {
                apiCache.delete(key);
            }
        }
    } else {
        apiCache.clear();
    }
}

// Optimized DOM manipulation using DocumentFragment
function createFragment(html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    return template.content;
}

// Batch DOM updates
function batchDOMUpdates(updates) {
    requestAnimationFrame(() => {
        updates.forEach(update => update());
    });
}

// Lazy load images
function lazyLoadImage(img) {
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                    observer.unobserve(img);
                }
            });
        });
        observer.observe(img);
    } else {
        // Fallback for older browsers
        if (img.dataset.src) {
            img.src = img.dataset.src;
        }
    }
}

// Optimized event delegation
function delegateEvent(container, selector, event, handler) {
    container.addEventListener(event, (e) => {
        const target = e.target.closest(selector);
        if (target) {
            handler.call(target, e);
        }
    });
}

// Use requestIdleCallback for non-critical operations
function scheduleIdleTask(callback) {
    if ('requestIdleCallback' in window) {
        requestIdleCallback(callback, { timeout: 2000 });
    } else {
        setTimeout(callback, 0);
    }
}

// Optimize CSS transitions
function enableGPUAcceleration(element) {
    element.style.willChange = 'transform';
    element.style.transform = 'translateZ(0)';
}

// Export utilities
window.PerformanceUtils = {
    debounce,
    throttle,
    cachedFetch,
    clearCache,
    createFragment,
    batchDOMUpdates,
    lazyLoadImage,
    delegateEvent,
    scheduleIdleTask,
    enableGPUAcceleration
};

