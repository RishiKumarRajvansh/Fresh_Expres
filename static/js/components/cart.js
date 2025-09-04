// Cart Management JavaScript
document.addEventListener('DOMContentLoaded', function() {
    initializeCart();
});

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
            
            // Update navbar counters using global function
            if (window.updateNavbarCounts) {
                window.updateNavbarCounts(data);
            } else {
                // Fallback to old method
                updateCartCounter(data.cart_count);
            }
            
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
            // Update navbar counters
            if (window.updateNavbarCounts) {
                window.updateNavbarCounts(data);
            }
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
            // Update navbar counters
            if (window.updateNavbarCounts) {
                window.updateNavbarCounts(data);
            }
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
