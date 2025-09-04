// Wishlist Management JavaScript
document.addEventListener('DOMContentLoaded', function() {
    initializeWishlist();
});

function initializeWishlist() {
    // Wishlist toggle buttons
    document.querySelectorAll('.wishlist-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const storeProductId = this.dataset.storeProductId;
            if (!storeProductId) {
                return;
            }
            
            toggleWishlist(storeProductId, this);
        });
    });
}

function toggleWishlist(storeProductId, button = null) {
    fetch('/accounts/wishlist/toggle/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            store_product_id: storeProductId
        })
    })
    .then(response => {
        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                return;
            }
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data && data.success !== undefined) {
            if (data.added) {
                if (button) {
                    button.classList.add('active');
                    const icon = button.querySelector('i');
                    if (icon) {
                        icon.classList.remove('far');
                        icon.classList.add('fas');
                    }
                }
            } else {
                if (button) {
                    button.classList.remove('active');
                    const icon = button.querySelector('i');
                    if (icon) {
                        icon.classList.remove('fas');
                        icon.classList.add('far');
                    }
                }
            }
        } else {
        }
    })
    .catch(error => {
        console.error('Error:', error);
        if (error.message.includes('login')) {
        } else {
        }
    });
}

function removeFromWishlist(storeProductId, element = null) {
    fetch('/accounts/wishlist/toggle/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            store_product_id: storeProductId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && !data.added) {
            if (element) {
                element.remove();
            }
        } else {
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}
