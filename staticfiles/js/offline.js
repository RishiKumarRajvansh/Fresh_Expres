// PWA Offline Functionality and Real-time Features
// Handles service worker registration, push notifications, and offline data management

class PWAManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.swRegistration = null;
        this.db = null;
        this.notificationPermission = 'default';
        
        this.init();
    }
    
    async init() {
        // Register service worker
        if ('serviceWorker' in navigator) {
            try {
                this.swRegistration = await navigator.serviceWorker.register('/static/js/sw.js');
                console.log('Service Worker registered successfully');
                
                // Check for updates
                this.swRegistration.addEventListener('updatefound', () => {
                    this.handleServiceWorkerUpdate();
                });
            } catch (error) {
                console.error('Service Worker registration failed:', error);
            }
        }
        
        // Initialize offline storage
        await this.initOfflineDB();
        
        // Setup connectivity listeners
        this.setupConnectivityListeners();
        
        // Request notification permission
        await this.requestNotificationPermission();
        
        // Setup push notifications
        if (this.swRegistration) {
            await this.setupPushNotifications();
        }
        
        // Update UI based on connection status
        this.updateUIForConnectivity();
        
        // Setup periodic background sync
        this.setupBackgroundSync();
        
        // Initialize real-time features
        this.initRealTimeFeatures();
    }
    
    async initOfflineDB() {
        try {
            this.db = await this.openIndexedDB();
            console.log('Offline database initialized');
        } catch (error) {
            console.error('Failed to initialize offline database:', error);
        }
    }
    
    openIndexedDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('FreshMeatOffline', 1);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
            
            request.onupgradeneeded = event => {
                const db = event.target.result;
                
                // Orders store
                if (!db.objectStoreNames.contains('orders')) {
                    const ordersStore = db.createObjectStore('orders', { 
                        keyPath: 'id', 
                        autoIncrement: true 
                    });
                    ordersStore.createIndex('timestamp', 'timestamp');
                    ordersStore.createIndex('synced', 'synced');
                }
                
                // Cart store
                if (!db.objectStoreNames.contains('cart')) {
                    const cartStore = db.createObjectStore('cart', { 
                        keyPath: 'productId' 
                    });
                    cartStore.createIndex('timestamp', 'timestamp');
                }
                
                // Products cache
                if (!db.objectStoreNames.contains('products')) {
                    const productsStore = db.createObjectStore('products', { 
                        keyPath: 'id' 
                    });
                    productsStore.createIndex('category', 'category');
                    productsStore.createIndex('store', 'store');
                }
                
                // User preferences
                if (!db.objectStoreNames.contains('preferences')) {
                    db.createObjectStore('preferences', { 
                        keyPath: 'key' 
                    });
                }
            };
        });
    }
    
    setupConnectivityListeners() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.updateUIForConnectivity();
            this.syncOfflineData();
            this.showConnectionStatus('Connected to internet', 'success');
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.updateUIForConnectivity();
            this.showConnectionStatus('You are offline. Some features may be limited.', 'warning');
        });
    }
    
    updateUIForConnectivity() {
        // Show a compact inline SVG network-status indicator when offline; remove when online
        this._updateNetworkStatusIndicator(this.isOnline);

        // Update form behaviors
        this.updateFormBehaviors();
    }

    _updateNetworkStatusIndicator(isOnline) {
        const id = 'network-status-indicator';
        let el = document.getElementById(id);

        if (isOnline) {
            if (el && el.parentNode) el.parentNode.removeChild(el);
            return;
        }

        if (!el) {
            el = document.createElement('div');
            el.id = id;
            el.setAttribute('aria-live', 'polite');
            el.style.position = 'fixed';
            el.style.top = '8px';
            el.style.right = '8px';
            el.style.zIndex = '2000';
            el.style.background = 'rgba(0,0,0,0.7)';
            el.style.color = '#fff';
            el.style.padding = '6px 10px';
            el.style.borderRadius = '18px';
            el.style.fontSize = '13px';
            el.style.display = 'flex';
            el.style.alignItems = 'center';
            el.style.gap = '8px';
            el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
            el.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <path d="M12 3C7.03 3 2.53 5.11 0 8.5L2.5 11C4.43 8.72 8.02 7 12 7s7.57 1.72 9.5 4.0L24 8.5C21.47 5.11 16.97 3 12 3z" fill="#FFB74D" />
                    <path d="M12 10c-2.76 0-5 2.24-5 5h2a3 3 0 116 0h2c0-2.76-2.24-5-5-5z" fill="#FFB74D" />
                    <circle cx="12" cy="18" r="2" fill="#FF7043" />
                </svg>
                <span>You're offline</span>
            `;
            document.body.appendChild(el);
        }
    }
    
    updateFormBehaviors() {
        const forms = document.querySelectorAll('form[data-offline-capable]');
        
        forms.forEach(form => {
            if (this.isOnline) {
                form.classList.remove('offline-mode');
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = submitBtn.dataset.originalText || submitBtn.textContent;
                }
            } else {
                form.classList.add('offline-mode');
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    if (!submitBtn.dataset.originalText) {
                        submitBtn.dataset.originalText = submitBtn.textContent;
                    }
                    submitBtn.textContent = 'Save for Later (Offline)';
                }
            }
        });
    }
    
    async requestNotificationPermission() {
        if ('Notification' in window) {
            this.notificationPermission = await Notification.requestPermission();
            
            if (this.notificationPermission === 'granted') {
                console.log('Notification permission granted');
            } else {
                console.log('Notification permission denied');
            }
        }
    }
    
    async setupPushNotifications() {
        if (!this.swRegistration || this.notificationPermission !== 'granted') {
            return;
        }
        
        try {
            // Check if already subscribed
            let subscription = await this.swRegistration.pushManager.getSubscription();
            
            if (!subscription) {
                // Create new subscription
                const vapidPublicKey = await this.getVAPIDPublicKey();
                
                subscription = await this.swRegistration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: this.urlBase64ToUint8Array(vapidPublicKey)
                });
                
                console.log('Push subscription created');
            }
            
            // Send subscription to server
            await this.sendSubscriptionToServer(subscription);
            
        } catch (error) {
            console.error('Push notification setup failed:', error);
        }
    }
    
    async getVAPIDPublicKey() {
        try {
            const response = await fetch('/api/push/vapid-key/');
            const data = await response.json();
            return data.public_key;
        } catch (error) {
            console.error('Failed to get VAPID key:', error);
            // Fallback key (should be replaced with actual key)
            return 'BM5Y5QhPiqD-d6q8VZ_j8v5kY6zH-8M6G9oN0dQ9ZrHjN9u0jF8XkE6MZtC0G-qF2tJ7cP5mL9xN8pQ1_wH0sO4';
        }
    }
    
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        return new Uint8Array([...rawData].map(char => char.charCodeAt(0)));
    }
    
    async sendSubscriptionToServer(subscription) {
        try {
            const response = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': await this.getCSRFToken()
                },
                body: JSON.stringify({
                    subscription: subscription.toJSON()
                })
            });
            
            if (response.ok) {
                console.log('Push subscription sent to server');
            }
        } catch (error) {
            console.error('Failed to send subscription to server:', error);
        }
    }
    
    setupBackgroundSync() {
        if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
            // Register background sync for offline orders
            navigator.serviceWorker.ready.then(registration => {
                return registration.sync.register('background-order-sync');
            }).catch(error => {
                console.error('Background sync registration failed:', error);
            });
        }
    }
    
    // Offline data management
    async saveOrderOffline(orderData) {
        if (!this.db) return false;
        
        const transaction = this.db.transaction(['orders'], 'readwrite');
        const store = transaction.objectStore('orders');
        
        const offlineOrder = {
            data: orderData,
            timestamp: new Date().toISOString(),
            synced: false
        };
        
        try {
            await store.add(offlineOrder);
            console.log('Order saved offline');
            
            this.showConnectionStatus('Order saved. Will be processed when online.', 'info');
            
            // Try to sync immediately if online
            if (this.isOnline) {
                setTimeout(() => this.syncOfflineData(), 1000);
            }
            
            return true;
        } catch (error) {
            console.error('Failed to save order offline:', error);
            return false;
        }
    }
    
    async saveCartOffline(cartItems) {
        if (!this.db) return false;
        
        const transaction = this.db.transaction(['cart'], 'readwrite');
        const store = transaction.objectStore('cart');
        
        try {
            // Clear existing cart
            await store.clear();
            
            // Add new items
            for (const item of cartItems) {
                await store.add({
                    ...item,
                    timestamp: new Date().toISOString()
                });
            }
            
            console.log('Cart saved offline');
            return true;
        } catch (error) {
            console.error('Failed to save cart offline:', error);
            return false;
        }
    }
    
    async getOfflineCart() {
        if (!this.db) return [];
        
        const transaction = this.db.transaction(['cart'], 'readonly');
        const store = transaction.objectStore('cart');
        
        try {
            const result = await store.getAll();
            return result;
        } catch (error) {
            console.error('Failed to get offline cart:', error);
            return [];
        }
    }
    
    async syncOfflineData() {
        if (!this.isOnline || !this.db) return;
        
        try {
            await this.syncOfflineOrders();
            await this.syncOfflineCart();
        } catch (error) {
            console.error('Offline data sync failed:', error);
        }
    }
    
    async syncOfflineOrders() {
        const transaction = this.db.transaction(['orders'], 'readwrite');
        const store = transaction.objectStore('orders');
        const index = store.index('synced');
        
        const unsyncedOrders = await index.getAll(false);
        
        for (const order of unsyncedOrders) {
            try {
                const response = await fetch('/api/orders/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': await this.getCSRFToken()
                    },
                    body: JSON.stringify(order.data)
                });
                
                if (response.ok) {
                    // Mark as synced
                    order.synced = true;
                    await store.put(order);
                    
                    this.showConnectionStatus('Offline order synced successfully', 'success');
                }
            } catch (error) {
                console.error('Failed to sync order:', error);
            }
        }
    }
    
    async syncOfflineCart() {
        const cartItems = await this.getOfflineCart();
        
        if (cartItems.length > 0) {
            try {
                const response = await fetch('/api/cart/sync/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': await this.getCSRFToken()
                    },
                    body: JSON.stringify({ items: cartItems })
                });
                
                if (response.ok) {
                    // Clear offline cart
                    const transaction = this.db.transaction(['cart'], 'readwrite');
                    await transaction.objectStore('cart').clear();
                    
                    console.log('Offline cart synced');
                }
            } catch (error) {
                console.error('Failed to sync cart:', error);
            }
        }
    }
    
    // Real-time features
    initRealTimeFeatures() {
        this.setupStockUpdates();
        this.setupOrderTracking();
        this.setupDeliveryTracking();
    }
    
    setupStockUpdates() {
        // WebSocket connection for real-time stock updates
        if (window.location.pathname.includes('/catalog/')) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/stock/`;
            
            const stockSocket = new WebSocket(wsUrl);
            
            stockSocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleStockUpdate(data);
            };
            
            stockSocket.onclose = () => {
                console.log('Stock WebSocket closed. Attempting to reconnect...');
                setTimeout(() => this.setupStockUpdates(), 5000);
            };
        }
    }
    
    handleStockUpdate(data) {
        const { product_id, store_id, stock_quantity, is_available } = data;
        
        // Update product cards
        const productCards = document.querySelectorAll(`[data-product-id="${product_id}"][data-store-id="${store_id}"]`);
        
        productCards.forEach(card => {
            const stockElement = card.querySelector('.stock-quantity');
            const availabilityElement = card.querySelector('.availability-status');
            const addToCartButton = card.querySelector('.add-to-cart-btn');
            
            if (stockElement) {
                stockElement.textContent = `Stock: ${stock_quantity}`;
            }
            
            if (availabilityElement) {
                availabilityElement.textContent = is_available ? 'Available' : 'Out of Stock';
                availabilityElement.className = `availability-status ${is_available ? 'available' : 'out-of-stock'}`;
            }
            
            if (addToCartButton) {
                addToCartButton.disabled = !is_available;
                addToCartButton.textContent = is_available ? 'Add to Cart' : 'Out of Stock';
            }
        });
        
        // Show notification for low stock
        if (stock_quantity <= 5 && stock_quantity > 0) {
            this.showConnectionStatus(`Low stock (${stock_quantity}) for product ${product_id}`, 'warning');
        }
    }
    
    setupOrderTracking() {
        if (window.location.pathname.includes('/orders/track/')) {
            const orderId = this.extractOrderIdFromUrl();
            if (orderId) {
                this.trackOrder(orderId);
            }
        }
    }
    
    async trackOrder(orderId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/orders/${orderId}/`;
        
        const orderSocket = new WebSocket(wsUrl);
        
        orderSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleOrderUpdate(data);
        };
        
        orderSocket.onclose = () => {
            console.log('Order tracking WebSocket closed. Attempting to reconnect...');
            setTimeout(() => this.trackOrder(orderId), 5000);
        };
    }
    
    handleOrderUpdate(data) {
        const { order_id, status, estimated_delivery, message } = data;
        
        // Update order status display
        const statusElement = document.querySelector('.order-status');
        if (statusElement) {
            statusElement.textContent = status;
            statusElement.className = `order-status ${status.toLowerCase().replace(' ', '-')}`;
        }
        
        // Update estimated delivery
        const deliveryElement = document.querySelector('.estimated-delivery');
        if (deliveryElement && estimated_delivery) {
            deliveryElement.textContent = new Date(estimated_delivery).toLocaleString();
        }
        
        // Show notification for important updates
        if (status === 'Out for Delivery' || status === 'Delivered') {
            this.showConnectionStatus(`Order ${order_id} is now ${status}`, 'info');
        }
        
        // Add to order timeline
        this.addToOrderTimeline(status, message, new Date());
    }
    
    addToOrderTimeline(status, message, timestamp) {
        const timeline = document.querySelector('.order-timeline');
        if (!timeline) return;
        
        const timelineItem = document.createElement('div');
        timelineItem.className = 'timeline-item active';
        timelineItem.innerHTML = `
            <div class="timeline-marker"></div>
            <div class="timeline-content">
                <h6>${status}</h6>
                <p>${message || 'Status updated'}</p>
                <small>${timestamp.toLocaleString()}</small>
            </div>
        `;
        
        timeline.insertBefore(timelineItem, timeline.firstChild);
    }
    
    setupDeliveryTracking() {
        if (window.location.pathname.includes('/delivery/track/')) {
            const deliveryId = this.extractDeliveryIdFromUrl();
            if (deliveryId) {
                this.trackDelivery(deliveryId);
            }
        }
    }
    
    // Utility functions
    async getCSRFToken() {
        try {
            const response = await fetch('/api/csrf-token/');
            const data = await response.json();
            return data.token;
        } catch (error) {
            console.error('Failed to get CSRF token:', error);
            return '';
        }
    }
    
    extractOrderIdFromUrl() {
        const match = window.location.pathname.match(/\/orders\/track\/(\d+)\//);
        return match ? match[1] : null;
    }
    
    extractDeliveryIdFromUrl() {
        const match = window.location.pathname.match(/\/delivery\/track\/(\d+)\//);
        return match ? match[1] : null;
    }
    
    showConnectionStatus(message, type = 'info') {
        // Create or update status toast
        let toast = document.querySelector('.connection-toast');
        
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'connection-toast';
            document.body.appendChild(toast);
        }
        
        toast.className = `connection-toast ${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${this.getIconForType(type)}"></i>
                <span>${message}</span>
            </div>
        `;
        
        toast.style.display = 'block';
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
            toast.style.display = 'none';
        }, 3000);
    }
    
    getIconForType(type) {
        const icons = {
            success: 'check-circle',
            warning: 'exclamation-triangle',
            error: 'times-circle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
    
    handleServiceWorkerUpdate() {
        const newWorker = this.swRegistration.installing;
        
        newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                // Show update available notification
                this.showUpdateNotification();
            }
        });
    }
    
    showUpdateNotification() {
        const notification = document.createElement('div');
        notification.className = 'update-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <h6>App Update Available</h6>
                <p>A new version of the app is available. Refresh to get the latest features.</p>
                <div class="notification-actions">
                    <button class="btn btn-primary btn-sm" onclick="window.location.reload()">
                        Update Now
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="this.parentElement.parentElement.parentElement.remove()">
                        Later
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(notification);
    }
}

// Initialize PWA Manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.pwaManager = new PWAManager();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PWAManager;
}
