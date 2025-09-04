// Enhanced Checkout Form Validation and Address Management
document.addEventListener('DOMContentLoaded', function() {
    const checkoutForm = document.getElementById('checkoutForm');
    const placeOrderBtn = document.getElementById('placeOrderBtn');
    const addressSelect = document.getElementById('delivery_address_select');
    
    if (checkoutForm) {
        checkoutForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validate address selection
            const deliveryAddressId = addressSelect ? addressSelect.value : 
                                     document.querySelector('input[name="delivery_address"]:checked')?.value;
            
            if (!deliveryAddressId) {
                showCheckoutToast('Please select a delivery address before placing your order.', 'error');
                return;
            }
            
            // Validate payment method
            const paymentMethod = document.querySelector('input[name="payment_method"]:checked')?.value;
            if (!paymentMethod) {
                showCheckoutToast('Please select a payment method.', 'error');
                return;
            }
            
            // Disable button to prevent double submission
            if (placeOrderBtn) {
                placeOrderBtn.disabled = true;
                placeOrderBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            }
            
            // Add delivery address to form if using dropdown
            if (addressSelect && !document.querySelector('input[name="delivery_address_id"]')) {
                const hiddenAddressInput = document.createElement('input');
                hiddenAddressInput.type = 'hidden';
                hiddenAddressInput.name = 'delivery_address_id';
                hiddenAddressInput.value = deliveryAddressId;
                this.appendChild(hiddenAddressInput);
            }
            
            if (paymentMethod === 'upi') {
                // Show UPI payment modal
                const paymentModal = new bootstrap.Modal(document.getElementById('paymentModal'));
                paymentModal.show();
                
                // Re-enable button
                if (placeOrderBtn) {
                    placeOrderBtn.disabled = false;
                    placeOrderBtn.innerHTML = '<i class="fas fa-check me-2"></i>Place Order - ₹{{ total_amount }}';
                }
            } else {
                // Submit form for COD or card
                this.submit();
            }
        });
    }
    
    // Handle UPI app selection
    document.querySelectorAll('.payment-app').forEach(button => {
        button.addEventListener('click', function() {
            const app = this.dataset.app;
            
            // Add hidden input for selected UPI app
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'upi_app';
            hiddenInput.value = app;
            checkoutForm.appendChild(hiddenInput);
            
            // Close modal and submit form
            bootstrap.Modal.getInstance(document.getElementById('paymentModal')).hide();
            checkoutForm.submit();
        });
    });
    
    // Address radio button change handler
    document.querySelectorAll('input[name="delivery_address"]').forEach(radio => {
        radio.addEventListener('change', function() {
            // Update visual selection
            document.querySelectorAll('.address-card').forEach(card => {
                card.classList.remove('selected', 'border-primary');
            });
            
            if (this.checked) {
                const addressCard = this.closest('.address-card');
                if (addressCard) {
                    addressCard.classList.add('selected', 'border-primary');
                }
                
                // Update place order button to show selected
                if (placeOrderBtn) {
                    placeOrderBtn.classList.remove('btn-outline-primary');
                    placeOrderBtn.classList.add('btn-primary');
                    placeOrderBtn.innerHTML = '<i class="fas fa-check me-2"></i>Place Order - ₹{{ total_amount }}';
                }
            }
        });
    });
    
    // Initialize address selection state
    const selectedAddressRadio = document.querySelector('input[name="delivery_address"]:checked');
    if (selectedAddressRadio) {
        selectedAddressRadio.dispatchEvent(new Event('change'));
    } else if (addressSelect && addressSelect.value) {
        // Dropdown is pre-selected
        if (placeOrderBtn) {
            placeOrderBtn.classList.remove('btn-outline-primary');
            placeOrderBtn.classList.add('btn-primary');
        }
    }
});

// Address dropdown change handler
function updateSelectedAddress() {
    const select = document.getElementById('delivery_address_select');
    const selectedOption = select.options[select.selectedIndex];
    
    if (selectedOption && selectedOption.value) {
        // Update the display elements
        const contactName = document.getElementById('contact-name');
        const addressLine1 = document.getElementById('address-line-1');
        const addressLine2 = document.getElementById('address-line-2');
        const addressLocation = document.getElementById('address-location');
        const contactPhone = document.getElementById('contact-phone');
        
        if (contactName) contactName.textContent = selectedOption.dataset.contact;
        if (addressLine1) addressLine1.textContent = selectedOption.dataset.line1;
        
        if (addressLine2) {
            if (selectedOption.dataset.line2) {
                addressLine2.textContent = selectedOption.dataset.line2;
                addressLine2.classList.remove('d-none');
            } else {
                addressLine2.classList.add('d-none');
            }
        }
        
        if (addressLocation) {
            addressLocation.textContent = 
                `${selectedOption.dataset.city}, ${selectedOption.dataset.state} ${selectedOption.dataset.zip}`;
        }
        
        if (contactPhone) {
            if (selectedOption.dataset.phone) {
                contactPhone.innerHTML = `<i class="fas fa-phone me-1"></i>${selectedOption.dataset.phone}`;
                contactPhone.classList.remove('d-none');
            } else {
                contactPhone.classList.add('d-none');
            }
        }
        
        // Update place order button state
        const placeOrderBtn = document.getElementById('placeOrderBtn');
        if (placeOrderBtn) {
            placeOrderBtn.classList.remove('btn-outline-primary');
            placeOrderBtn.classList.add('btn-primary');
            placeOrderBtn.innerHTML = '<i class="fas fa-check me-2"></i>Place Order - ₹{{ total_amount }}';
        }
        
        showCheckoutToast('Delivery address updated successfully!', 'success');
    }
}

// Checkout-specific toast notifications
function showCheckoutToast(message, type = 'info') {
    // Remove any existing checkout toasts
    document.querySelectorAll('.checkout-toast').forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast show position-fixed checkout-toast`;
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.style.minWidth = '350px';
    
    const bgColor = type === 'success' ? 'bg-success' : 
                   type === 'error' ? 'bg-danger' : 
                   type === 'warning' ? 'bg-warning' : 'bg-info';
    
    toast.innerHTML = `
        <div class="toast-header ${bgColor} text-white">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 
                              type === 'error' ? 'exclamation-circle' : 
                              type === 'warning' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
            <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
            <button type="button" class="btn-close btn-close-white" onclick="this.closest('.toast').remove()"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds for success messages, 8 seconds for errors
    const timeout = type === 'error' ? 8000 : 5000;
    setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, timeout);
}

// Address validation helper
function validateAddressSelection() {
    const addressSelect = document.getElementById('delivery_address_select');
    const addressRadio = document.querySelector('input[name="delivery_address"]:checked');
    
    if (addressSelect) {
        return addressSelect.value && addressSelect.value !== '';
    } else if (addressRadio) {
        return addressRadio.value && addressRadio.value !== '';
    }
    
    return false;
}

// Add visual feedback for form interactions
document.addEventListener('DOMContentLoaded', function() {
    // Highlight active payment method
    document.querySelectorAll('input[name="payment_method"]').forEach(radio => {
        radio.addEventListener('change', function() {
            document.querySelectorAll('.form-check').forEach(check => {
                check.classList.remove('border-primary', 'bg-light');
            });
            
            if (this.checked) {
                const formCheck = this.closest('.form-check');
                if (formCheck) {
                    formCheck.classList.add('border-primary', 'bg-light');
                }
            }
        });
    });
    
    // Initialize selected payment method
    const selectedPayment = document.querySelector('input[name="payment_method"]:checked');
    if (selectedPayment) {
        selectedPayment.dispatchEvent(new Event('change'));
    }
});

// Auto-save address selection to prevent loss
let addressSelectionTimeout;
function autoSaveAddressSelection() {
    clearTimeout(addressSelectionTimeout);
    addressSelectionTimeout = setTimeout(() => {
        const selectedAddress = validateAddressSelection();
        if (selectedAddress) {
            sessionStorage.setItem('selectedDeliveryAddress', 
                document.getElementById('delivery_address_select')?.value || 
                document.querySelector('input[name="delivery_address"]:checked')?.value
            );
        }
    }, 1000);
}

// Restore address selection on page load
document.addEventListener('DOMContentLoaded', function() {
    const savedAddress = sessionStorage.getItem('selectedDeliveryAddress');
    if (savedAddress) {
        const addressSelect = document.getElementById('delivery_address_select');
        const addressRadio = document.querySelector(`input[name="delivery_address"][value="${savedAddress}"]`);
        
        if (addressSelect && addressSelect.querySelector(`option[value="${savedAddress}"]`)) {
            addressSelect.value = savedAddress;
            updateSelectedAddress();
        } else if (addressRadio) {
            addressRadio.checked = true;
            addressRadio.dispatchEvent(new Event('change'));
        }
    }
    
    // Add listeners for auto-save
    document.getElementById('delivery_address_select')?.addEventListener('change', autoSaveAddressSelection);
    document.querySelectorAll('input[name="delivery_address"]').forEach(radio => {
        radio.addEventListener('change', autoSaveAddressSelection);
    });
});

// Clear saved selection after successful order
window.addEventListener('beforeunload', function() {
    if (window.location.href.includes('order-success') || 
        window.location.href.includes('order-confirmation')) {
        sessionStorage.removeItem('selectedDeliveryAddress');
    }
});
