// Main JavaScript for FreshMeat Platform

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips and popovers
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Fix navbar dropdown positioning - CRITICAL FIX
    initializeNavbarDropdowns();

    // Cart functionality
    initializeCart();
    
    // Chat widget
    initializeChatWidget();
    
    // Product filters
    initializeFilters();
    
    // Quantity controls
    initializeQuantityControls();
    
    // Wishlist functionality
    initializeWishlist();
    
    // Auto-dismiss alerts
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});

// Fix navbar dropdown functionality
function initializeNavbarDropdowns() {
    // Remove any custom dropdown handling that interferes with Bootstrap
    // Let Bootstrap handle dropdown functionality by default
    
    // Just ensure dropdowns are properly positioned
    const dropdowns = document.querySelectorAll('.navbar .dropdown');
    
    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu');
        
        if (toggle && menu) {
            // Ensure proper Bootstrap attributes are set
            if (!toggle.hasAttribute('data-bs-toggle')) {
                toggle.setAttribute('data-bs-toggle', 'dropdown');
            }
            if (!toggle.hasAttribute('aria-expanded')) {
                toggle.setAttribute('aria-expanded', 'false');
            }
            
            // Let Bootstrap handle the dropdown - don't override default behavior
            // Just ensure proper styling
            menu.style.position = 'absolute';
            menu.style.zIndex = '1050';
        }
    });
}

// Cart Management
function initializeCart() {
    // Add to cart buttons
    document.querySelectorAll('.add-to-cart-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const storeProductId = this.dataset.storeProductId;
            
            // Get quantity from the quantity input next to this button
            let quantity = 1;
            const qtyInput = this.parentElement.querySelector('.qty-input');
            if (qtyInput) {
                quantity = parseInt(qtyInput.value) || 1;
            } else {
                quantity = parseInt(this.dataset.quantity) || 1;
            }
            
            if (!storeProductId) {
                return;
            }
            
            addToCart(storeProductId, quantity, this);
        });
    });
    
    // Quantity controls
    document.querySelectorAll('.qty-decrease').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const input = this.parentElement.querySelector('.qty-input');
            const currentValue = parseInt(input.value) || 1;
            if (currentValue > 1) {
                input.value = currentValue - 1;
            }
        });
    });
    
    document.querySelectorAll('.qty-increase').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const input = this.parentElement.querySelector('.qty-input');
            const currentValue = parseInt(input.value) || 1;
            if (currentValue < 5) {
                input.value = currentValue + 1;
            }
        });
    });
    
    // Update cart quantities
    document.querySelectorAll('.update-cart-btn').forEach(button => {
        button.addEventListener('click', function() {
            const itemId = this.dataset.itemId;
            const quantity = this.parentElement.querySelector('.quantity-input').value;
            
            updateCartItem(itemId, quantity);
        });
    });
    
    // Remove from cart
    document.querySelectorAll('.remove-cart-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const itemId = this.dataset.itemId;
            
            if (confirm('Are you sure you want to remove this item?')) {
                removeFromCart(itemId);
            }
        });
    });
}

function addToCart(storeProductId, quantity = 1, button = null) {
    // Prevent double-clicking
    if (button && button.disabled) {
        return;
    }
    
    const originalText = button ? button.innerHTML : '';
    
    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    }
    
    fetch('/orders/cart/add/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            store_product_id: storeProductId,
            quantity: quantity
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateCartCounter(data.cart_count);
            
            if (button) {
                // Change button state briefly
                button.innerHTML = '<i class="fas fa-check"></i> Added';
                button.classList.remove('btn-primary');
                button.classList.add('btn-success');
                
                setTimeout(() => {
                    button.innerHTML = originalText;
                    button.classList.remove('btn-success');
                    button.classList.add('btn-primary');
                    button.disabled = false;
                }, 1500);
            }
        } else {
            if (button) {
                button.innerHTML = originalText;
                button.disabled = false;
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        if (button) {
            button.innerHTML = originalText;
            button.disabled = false;
        }
    });
}

function updateCartItem(itemId, quantity) {
    fetch('/orders/cart/update/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            cart_item_id: itemId,
            quantity: quantity
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload(); // Refresh cart page
        } else {
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function removeFromCart(itemId) {
    fetch('/orders/cart/remove/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            cart_item_id: itemId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload(); // Refresh cart page
        } else {
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function updateCartCounter(count) {
    const counter = document.querySelector('.navbar .badge');
    if (counter) {
        counter.textContent = count;
        counter.style.display = count > 0 ? 'inline' : 'none';
    }
}

// Chat Widget
function initializeChatWidget() {
    const chatToggle = document.getElementById('chat-toggle');
    const chatWindow = document.getElementById('chat-window');
    
    if (chatToggle) {
        chatToggle.addEventListener('click', function() {
            if (chatWindow) {
                chatWindow.style.display = chatWindow.style.display === 'none' ? 'block' : 'none';
            } else {
                // Create and show chat window
                createChatWindow();
            }
        });
    }
}

// Function to open customer support from navbar
function openCustomerSupport() {
    const existingChat = document.getElementById('chat-window');
    if (existingChat) {
        existingChat.style.display = 'block';
    } else {
        createChatWindow();
    }
}

function createChatWindow() {
    const chatHtml = `
        <div id="chat-window" class="chat-window">
            <div class="chat-header d-flex justify-content-between align-items-center">
                <span>Support Chat</span>
                <button class="btn btn-sm text-white" onclick="closeChatWindow()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="chat-messages" id="chat-messages">
                <div class="text-center text-muted p-3">
                    <p>Start a conversation with our support team!</p>
                </div>
            </div>
            <div class="chat-input">
                <div class="input-group">
                    <input type="text" class="form-control" placeholder="Type your message..." id="chat-input">
                    <button class="btn btn-primary" onclick="sendChatMessage()">
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', chatHtml);
    
    // Initialize chat functionality
    initializeChatMessaging();
}

function closeChatWindow() {
    const chatWindow = document.getElementById('chat-window');
    if (chatWindow) {
        chatWindow.remove();
    }
}

function initializeChatMessaging() {
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendChatMessage();
            }
        });
    }
}

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (message) {
        // Add message to chat
        addChatMessage(message, 'user');
        input.value = '';
        
        // Send to server (implement WebSocket connection here)
        // For now, just simulate a response
        setTimeout(() => {
            addChatMessage('Thank you for your message. A support representative will respond shortly.', 'support');
        }, 1000);
    }
}

function addChatMessage(message, sender) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageHtml = `
        <div class="chat-message ${sender} mb-2">
            <div class="d-flex ${sender === 'user' ? 'justify-content-end' : ''}">
                <div class="message-bubble p-2 rounded ${sender === 'user' ? 'bg-primary text-white' : 'bg-light'}">
                    ${message}
                </div>
            </div>
        </div>
    `;
    
    messagesContainer.insertAdjacentHTML('beforeend', messageHtml);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Filters
function initializeFilters() {
    const filterCheckboxes = document.querySelectorAll('.filter-checkbox');
    const filterForm = document.getElementById('filter-form');
    
    if (filterCheckboxes.length > 0) {
        filterCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                if (filterForm) {
                    filterForm.submit();
                } else {
                    // Apply filters via AJAX
                    applyFilters();
                }
            });
        });
    }
    
    // Price range filter
    const priceRange = document.getElementById('price-range');
    if (priceRange) {
        priceRange.addEventListener('input', debounce(function() {
            applyFilters();
        }, 500));
    }
}

function applyFilters() {
    const filters = {};
    
    // Collect filter values
    document.querySelectorAll('.filter-checkbox:checked').forEach(checkbox => {
        const filterType = checkbox.dataset.filterType;
        if (!filters[filterType]) {
            filters[filterType] = [];
        }
        filters[filterType].push(checkbox.value);
    });
    
    // Price range
    const priceRange = document.getElementById('price-range');
    if (priceRange) {
        filters.max_price = priceRange.value;
    }
    
    // Send AJAX request
    const url = new URL(window.location.href);
    Object.keys(filters).forEach(key => {
        url.searchParams.delete(key);
        if (Array.isArray(filters[key])) {
            filters[key].forEach(value => url.searchParams.append(key, value));
        } else {
            url.searchParams.set(key, filters[key]);
        }
    });
    
    // Update URL without reload
    history.pushState(null, '', url.toString());
    
    // Load filtered results
    loadFilteredProducts(filters);
}

function loadFilteredProducts(filters) {
    const productGrid = document.getElementById('product-grid');
    if (!productGrid) return;
    
    // Show loading state
    productGrid.innerHTML = '<div class="text-center p-4"><div class="loading"></div></div>';
    
    fetch('/catalog/api/filters/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(filters)
    })
    .then(response => response.json())
    .then(data => {
        productGrid.innerHTML = data.html;
        initializeCart(); // Reinitialize cart buttons
    })
    .catch(error => {
        console.error('Error:', error);
        productGrid.innerHTML = '<div class="text-center p-4 text-danger">Error loading products</div>';
    });
}

// Quantity Controls
function initializeQuantityControls() {
    document.querySelectorAll('.quantity-minus').forEach(button => {
        button.addEventListener('click', function() {
            const input = this.nextElementSibling;
            const currentValue = parseInt(input.value);
            if (currentValue > 1) {
                input.value = currentValue - 1;
                input.dispatchEvent(new Event('change'));
            }
        });
    });
    
    document.querySelectorAll('.quantity-plus').forEach(button => {
        button.addEventListener('click', function() {
            const input = this.previousElementSibling;
            const currentValue = parseInt(input.value);
            const maxValue = parseInt(input.max) || 99;
            if (currentValue < maxValue) {
                input.value = currentValue + 1;
                input.dispatchEvent(new Event('change'));
            }
        });
    });
}

// Utility Functions
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function {
    const alertClass = type === 'error' ? 'alert-danger' : 
                     type === 'success' ? 'alert-success' : 
                     type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const notification = document.createElement('div');
    notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 1060; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            const bsAlert = new bootstrap.Alert(notification);
            bsAlert.close();
        }
    }, 5000);
}

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

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(amount);
}

// Location services
function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject('Geolocation is not supported');
        }
        
        navigator.geolocation.getCurrentPosition(
            position => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                });
            },
            error => {
                reject('Error getting location: ' + error.message);
            }
        );
    });
}

// Form validation helpers
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function validatePhone(phone) {
    const re = /^[6-9]\d{9}$/;
    return re.test(phone);
}

function validateZipCode(zip) {
    const re = /^\d{6}$/;
    return re.test(zip);
}

// Image lazy loading
function initializeLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        images.forEach(img => imageObserver.observe(img));
    } else {
        // Fallback for older browsers
        images.forEach(img => {
            img.src = img.dataset.src;
            img.classList.remove('lazy');
        });
    }
}

// Wishlist functionality
// Wishlist functionality - DISABLED to prevent conflict with template-specific functions
function initializeWishlist() {
    console.log('Wishlist initialization skipped - using template-specific functions');
    // Wishlist is handled by individual templates to avoid conflicts
}

function toggleWishlist(storeProductId, button = null) {
    console.log('toggleWishlist called from main.js - redirecting to template function');
    // This function is disabled to prevent conflicts
    // Each template handles wishlist functionality independently
}
