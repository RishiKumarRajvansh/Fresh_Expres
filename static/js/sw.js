// Service Worker for PWA Offline Functionality
// Implements caching strategies for hyperlocal grocery platform

const CACHE_NAME = 'fresh-meat-v1.0.0';
const OFFLINE_URL = '/offline/';

// Assets to cache immediately
const PRECACHE_ASSETS = [
  '/',
  '/offline/',
  '/static/css/main.css',
  '/static/js/main.js',
  '/static/js/offline.js',
  '/static/img/logo.png',
  '/static/img/offline-placeholder.png',
  '/catalog/categories/',
  '/accounts/login/',
  '/accounts/register/'
];

// Cache strategies for different types of requests
const CACHE_STRATEGIES = {
  // HTML pages - Network First (fresh content preferred)
  pages: 'network-first',
  
  // API calls - Network First with timeout
  api: 'network-first',
  
  // Static assets - Cache First (performance optimized)
  static: 'cache-first',
  
  // Images - Cache First with fallback
  images: 'cache-first',
  
  // Product data - Stale While Revalidate (balance of speed and freshness)
  products: 'stale-while-revalidate'
};

// Install event - precache essential assets
self.addEventListener('install', event => {
  console.log('Service Worker installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Precaching assets...');
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => {
        // Skip waiting to activate immediately
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('Precache failed:', error);
      })
  );
});

// Activate event - cleanup old caches
self.addEventListener('activate', event => {
  console.log('Service Worker activating...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== CACHE_NAME) {
              console.log('Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        // Take control of all pages
        return self.clients.claim();
      })
  );
});

// Fetch event - handle all network requests with appropriate caching strategy
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Skip cross-origin requests not related to our app
  if (url.origin !== location.origin) {
    return;
  }
  
  // Determine caching strategy based on request type
  let strategy = determineStrategy(url, request);
  
  event.respondWith(
    handleRequest(request, strategy)
  );
});

// Determine caching strategy based on URL and request type
function determineStrategy(url, request) {
  const { pathname } = url;
  
  // API endpoints
  if (pathname.startsWith('/api/')) {
    return CACHE_STRATEGIES.api;
  }
  
  // Static assets
  if (pathname.startsWith('/static/')) {
    if (pathname.includes('.css') || pathname.includes('.js')) {
      return CACHE_STRATEGIES.static;
    }
    if (pathname.includes('.png') || pathname.includes('.jpg') || pathname.includes('.jpeg') || pathname.includes('.webp')) {
      return CACHE_STRATEGIES.images;
    }
    return CACHE_STRATEGIES.static;
  }
  
  // Product-related pages
  if (pathname.startsWith('/catalog/') || pathname.startsWith('/stores/')) {
    return CACHE_STRATEGIES.products;
  }
  
  // Regular HTML pages
  return CACHE_STRATEGIES.pages;
}

// Handle request with specified strategy
async function handleRequest(request, strategy) {
  switch (strategy) {
    case 'network-first':
      return networkFirst(request);
    case 'cache-first':
      return cacheFirst(request);
    case 'stale-while-revalidate':
      return staleWhileRevalidate(request);
    default:
      return networkFirst(request);
  }
}

// Network First strategy - try network, fallback to cache
async function networkFirst(request, timeout = 3000) {
  try {
    // Add timeout to network request
    const networkPromise = fetch(request);
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Network timeout')), timeout)
    );
    
    const response = await Promise.race([networkPromise, timeoutPromise]);
    
    if (response.ok) {
      // Update cache with fresh response
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
      return response;
    }
    throw new Error('Network response not ok');
    
  } catch (error) {
    console.log('Network failed, trying cache:', error.message);
    
    // Fallback to cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline page for navigation requests
    if (request.mode === 'navigate') {
      const offlineResponse = await caches.match(OFFLINE_URL);
      if (offlineResponse) {
        return offlineResponse;
      }
    }
    
    // Return generic offline response
    return new Response('Offline - Content not available', {
      status: 503,
      statusText: 'Service Unavailable',
      headers: new Headers({
        'Content-Type': 'text/plain'
      })
    });
  }
}

// Cache First strategy - try cache, fallback to network
async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
      return networkResponse;
    }
    
    return networkResponse;
    
  } catch (error) {
    console.error('Cache first failed:', error);
    
    // Return placeholder for images
    if (request.destination === 'image') {
      const placeholder = await caches.match('/static/img/offline-placeholder.png');
      if (placeholder) {
        return placeholder;
      }
    }
    
    return new Response('Content not available offline', {
      status: 503,
      statusText: 'Service Unavailable'
    });
  }
}

// Stale While Revalidate - return cache immediately, update in background
async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cachedResponse = await cache.match(request);
  
  // Update cache in background
  const networkPromise = fetch(request)
    .then(networkResponse => {
      if (networkResponse.ok) {
        cache.put(request, networkResponse.clone());
      }
      return networkResponse;
    })
    .catch(error => {
      console.log('Background update failed:', error);
    });
  
  // Return cached version immediately if available
  if (cachedResponse) {
    return cachedResponse;
  }
  
  // If no cache, wait for network
  try {
    return await networkPromise;
  } catch (error) {
    return new Response('Content not available', {
      status: 503,
      statusText: 'Service Unavailable'
    });
  }
}

// Background sync for offline actions
self.addEventListener('sync', event => {
  if (event.tag === 'background-order-sync') {
    event.waitUntil(syncOfflineOrders());
  }
  
  if (event.tag === 'background-cart-sync') {
    event.waitUntil(syncOfflineCart());
  }
});

// Sync offline orders when connection is restored
async function syncOfflineOrders() {
  try {
    const db = await openIndexedDB();
    const offlineOrders = await getOfflineOrders(db);
    
    for (const order of offlineOrders) {
      try {
        const response = await fetch('/api/orders/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': await getCSRFToken()
          },
          body: JSON.stringify(order.data)
        });
        
        if (response.ok) {
          await removeOfflineOrder(db, order.id);
          console.log('Offline order synced:', order.id);
        }
      } catch (error) {
        console.error('Failed to sync order:', error);
      }
    }
  } catch (error) {
    console.error('Background sync failed:', error);
  }
}

// Sync offline cart when connection is restored
async function syncOfflineCart() {
  try {
    const db = await openIndexedDB();
    const offlineCart = await getOfflineCart(db);
    
    if (offlineCart.length > 0) {
      const response = await fetch('/api/cart/sync/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': await getCSRFToken()
        },
        body: JSON.stringify({ items: offlineCart })
      });
      
      if (response.ok) {
        await clearOfflineCart(db);
        console.log('Offline cart synced');
      }
    }
  } catch (error) {
    console.error('Cart sync failed:', error);
  }
}

// Push notification handling
self.addEventListener('push', event => {
  if (!event.data) return;
  
  const data = event.data.json();
  const options = {
    body: data.body || 'You have a new notification',
    icon: '/static/img/icon-192x192.png',
    badge: '/static/img/badge-72x72.png',
    tag: data.tag || 'general',
    data: data.data || {},
    actions: data.actions || [],
    requireInteraction: data.requireInteraction || false,
    silent: data.silent || false
  };
  
  event.waitUntil(
    self.registration.
});

// Notification click handling
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  const data = event.notification.data;
  let url = '/';
  
  // Handle different notification types
  switch (data.type) {
    case 'order_status':
      url = `/orders/${data.order_id}/`;
      break;
    case 'delivery_update':
      url = `/delivery/track/${data.tracking_id}/`;
      break;
    case 'promotion':
      url = data.promotion_url || '/catalog/';
      break;
    case 'stock_alert':
      url = `/catalog/product/${data.product_id}/`;
      break;
    default:
      url = data.url || '/';
  }
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(clientList => {
        // Try to focus existing window
        for (const client of clientList) {
          if (client.url.includes(url) && 'focus' in client) {
            return client.focus();
          }
        }
        
        // Open new window
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
  );
});

// Utility functions for IndexedDB operations
async function openIndexedDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('FreshMeatOffline', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = event => {
      const db = event.target.result;
      
      if (!db.objectStoreNames.contains('orders')) {
        db.createObjectStore('orders', { keyPath: 'id', autoIncrement: true });
      }
      
      if (!db.objectStoreNames.contains('cart')) {
        db.createObjectStore('cart', { keyPath: 'id', autoIncrement: true });
      }
    };
  });
}

async function getOfflineOrders(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['orders'], 'readonly');
    const store = transaction.objectStore('orders');
    const request = store.getAll();
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

async function getOfflineCart(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['cart'], 'readonly');
    const store = transaction.objectStore('cart');
    const request = store.getAll();
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

async function removeOfflineOrder(db, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['orders'], 'readwrite');
    const store = transaction.objectStore('orders');
    const request = store.delete(id);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

async function clearOfflineCart(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['cart'], 'readwrite');
    const store = transaction.objectStore('cart');
    const request = store.clear();
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

async function getCSRFToken() {
  try {
    const response = await fetch('/api/csrf-token/');
    const data = await response.json();
    return data.token;
  } catch (error) {
    console.error('Failed to get CSRF token:', error);
    return '';
  }
}
