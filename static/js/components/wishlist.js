// Clean Wishlist module
// Usage: include this script and it will automatically bind to elements with `.wishlist-btn[data-store-product-id]`
// Buttons can be server-rendered with `data-store-product-id` and optional `data-wishlist-bound="1"` to opt-out of binding.

(function () {
    const endpoint = '/accounts/wishlist/toggle/';
    const pending = new Map(); // store_product_id -> Promise

    function getCookie(name) {
        if (typeof window.getCookie === 'function') return window.getCookie(name);
        const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : null;
    }

    function updateButtonState(button, added) {
        if (!button) return;
        const icon = button.querySelector('i');
        if (added) {
            button.classList.add('active');
            if (icon) { icon.className = 'fas fa-heart'; }
        } else {
            button.classList.remove('active');
            if (icon) { icon.className = 'far fa-heart'; }
        }
    }

    function updateNavbarCountsSafely(data) {
        try {
            if (window.updateNavbarCounts) window.updateNavbarCounts(data);
        } catch (e) {
            console.debug('updateNavbarCounts failed', e);
        }
    }

    async function toggle(storeProductId) {
        // If a request for this product is pending, return that promise (dedupe)
        if (pending.has(storeProductId)) return pending.get(storeProductId);

        const payload = JSON.stringify({ store_product_id: storeProductId });
        const promise = fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'same-origin',
            body: payload
        })
        .then(async res => {
            const json = await res.json().catch(() => ({}));
            return { status: res.status, json };
        })
        .finally(() => pending.delete(storeProductId));

        pending.set(storeProductId, promise);
        return promise;
    }

    function bindButtons(root = document) {
        root.querySelectorAll('.wishlist-btn[data-store-product-id]').forEach(btn => {
            // Skip if already bound by server or this script
            if (btn.getAttribute('data-wishlist-bound') === '1') return;
            btn.setAttribute('data-wishlist-bound', '1');

            btn.addEventListener('click', function (e) {
                e.preventDefault(); e.stopPropagation();
                const id = btn.getAttribute('data-store-product-id');
                if (!id) return;

                // visual feedback
                const prevHTML = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                btn.disabled = true;

                toggle(id).then(({ status, json }) => {
                    if (json && json.success) {
                        updateButtonState(btn, json.added);
                        updateNavbarCountsSafely(json);
                    } else if (status === 403) {
                        // Not authenticated
                        window.location.href = '/accounts/login/';
                    } else {
                        console.error('Wishlist error', json || status);
                    }
                }).catch(err => {
                    console.error('Wishlist request failed', err);
                }).finally(() => {
                    if (document.body.contains(btn)) {
                        btn.innerHTML = prevHTML;
                        btn.disabled = false;
                    }
                });
            });
        });
    }

    // Initial bind on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => bindButtons(document));
    } else {
        bindButtons(document);
    }

    // Expose for dynamic content
    window.WishlistModule = {
        bind: bindButtons,
        toggle,
    };

})();
