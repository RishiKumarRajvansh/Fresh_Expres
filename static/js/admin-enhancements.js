// Admin Dashboard Enhancements
document.addEventListener('DOMContentLoaded', function() {
    // Enhanced sidebar functionality
    function enhanceSidebar() {
        const sidebar = document.querySelector('#nav-sidebar');
        const modules = document.querySelectorAll('#nav-sidebar .module');
        
        if (sidebar && modules.length > 0) {
            // Add smooth scroll behavior
            sidebar.style.scrollBehavior = 'smooth';
            
            // Add hover effects to modules
            modules.forEach(module => {
                const header = module.querySelector('h2');
                const links = module.querySelectorAll('a');
                
                // Add icons to module headers
                if (header && !header.querySelector('i')) {
                    const icon = document.createElement('i');
                    icon.className = 'fas fa-chevron-right';
                    icon.style.marginLeft = 'auto';
                    icon.style.transition = 'transform 0.3s ease';
                    header.appendChild(icon);
                    
                    // Toggle module visibility
                    header.style.cursor = 'pointer';
                    header.addEventListener('click', function() {
                        const isOpen = module.classList.contains('open');
                        
                        if (isOpen) {
                            module.classList.remove('open');
                            icon.style.transform = 'rotate(0deg)';
                            links.forEach(link => {
                                link.style.maxHeight = '0';
                                link.style.opacity = '0';
                                link.style.padding = '0 20px';
                            });
                        } else {
                            module.classList.add('open');
                            icon.style.transform = 'rotate(90deg)';
                            links.forEach((link, index) => {
                                setTimeout(() => {
                                    link.style.maxHeight = '50px';
                                    link.style.opacity = '1';
                                    link.style.padding = '15px 20px';
                                }, index * 50);
                            });
                        }
                    });
                }
                
                // Add badge numbers to links (simulate item counts)
                links.forEach(link => {
                    if (!link.querySelector('.nav-badge')) {
                        const href = link.getAttribute('href');
                        let count = Math.floor(Math.random() * 50) + 1; // Simulate counts
                        
                        // Assign realistic counts based on model type
                        if (href.includes('user') || href.includes('accounts')) count = Math.floor(Math.random() * 100) + 50;
                        if (href.includes('order')) count = Math.floor(Math.random() * 200) + 100;
                        if (href.includes('product') || href.includes('store')) count = Math.floor(Math.random() * 150) + 75;
                        if (href.includes('category')) count = Math.floor(Math.random() * 20) + 5;
                        
                        const badge = document.createElement('span');
                        badge.className = 'nav-badge';
                        badge.textContent = count;
                        badge.style.cssText = `
                            background: var(--secondary-yellow);
                            color: var(--primary-dark);
                            font-size: 10px;
                            font-weight: 700;
                            padding: 2px 6px;
                            border-radius: 10px;
                            margin-left: auto;
                            min-width: 16px;
                            text-align: center;
                            transition: all 0.3s ease;
                        `;
                        
                        link.appendChild(badge);
                        
                        // Update badge on hover
                        link.addEventListener('mouseenter', function() {
                            badge.style.background = 'var(--white)';
                            badge.style.color = 'var(--primary-blue)';
                            badge.style.transform = 'scale(1.1)';
                        });
                        
                        link.addEventListener('mouseleave', function() {
                            if (!this.classList.contains('current-app')) {
                                badge.style.background = 'var(--secondary-yellow)';
                                badge.style.color = 'var(--primary-dark)';
                                badge.style.transform = 'scale(1)';
                            }
                        });
                    }
                });
            });
            
            // Add quick actions to sidebar
            const quickActions = document.createElement('div');
            quickActions.className = 'sidebar-quick-actions';
            quickActions.style.cssText = `
                position: fixed;
                bottom: 20px;
                left: 20px;
                right: 20px;
                max-width: 220px;
                background: var(--primary-gradient);
                border-radius: var(--border-radius);
                padding: 15px;
                box-shadow: var(--box-shadow);
                z-index: 1000;
            `;
            
            quickActions.innerHTML = `
                <h4 style="color: white; margin: 0 0 10px 0; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">
                    <i class="fas fa-bolt" style="margin-right: 5px;"></i>
                    Quick Actions
                </h4>
                <div style="display: flex; justify-content: space-between; gap: 5px;">
                    <a href="/admin/stores/storeproduct/add/" style="flex: 1; background: rgba(255,255,255,0.2); color: white; text-decoration: none; padding: 8px; border-radius: 4px; text-align: center; font-size: 11px; transition: all 0.3s ease;">
                        <i class="fas fa-plus" style="display: block; margin-bottom: 2px;"></i>
                        Add Product
                    </a>
                    <a href="/admin/orders/order/" style="flex: 1; background: rgba(255,255,255,0.2); color: white; text-decoration: none; padding: 8px; border-radius: 4px; text-align: center; font-size: 11px; transition: all 0.3s ease;">
                        <i class="fas fa-shopping-cart" style="display: block; margin-bottom: 2px;"></i>
                        Orders
                    </a>
                    <a href="/admin/accounts/customuser/" style="flex: 1; background: rgba(255,255,255,0.2); color: white; text-decoration: none; padding: 8px; border-radius: 4px; text-align: center; font-size: 11px; transition: all 0.3s ease;">
                        <i class="fas fa-users" style="display: block; margin-bottom: 2px;"></i>
                        Users
                    </a>
                </div>
            `;
            
            // Add hover effects to quick action buttons
            const quickActionBtns = quickActions.querySelectorAll('a');
            quickActionBtns.forEach(btn => {
                btn.addEventListener('mouseenter', function() {
                    this.style.background = 'rgba(255,255,255,0.3)';
                    this.style.transform = 'translateY(-2px)';
                });
                
                btn.addEventListener('mouseleave', function() {
                    this.style.background = 'rgba(255,255,255,0.2)';
                    this.style.transform = 'translateY(0)';
                });
            });
            
            sidebar.appendChild(quickActions);
        }
    }
    
    // Initialize enhancements
    enhanceSidebar();
    
    // Add search functionality to sidebar
    function addSidebarSearch() {
        const sidebar = document.querySelector('#nav-sidebar');
        if (sidebar) {
            const searchBox = document.createElement('div');
            searchBox.className = 'sidebar-search';
            searchBox.style.cssText = `
                padding: 15px 20px;
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border-bottom: 1px solid var(--medium-gray);
                position: sticky;
                top: 0;
                z-index: 100;
            `;
            
            searchBox.innerHTML = `
                <div style="position: relative;">
                    <input type="text" placeholder="Search admin..." style="
                        width: 100%;
                        padding: 8px 35px 8px 12px;
                        border: 1px solid var(--medium-gray);
                        border-radius: 20px;
                        font-size: 12px;
                        background: white;
                        transition: all 0.3s ease;
                    " id="sidebar-search-input">
                    <i class="fas fa-search" style="
                        position: absolute;
                        right: 12px;
                        top: 50%;
                        transform: translateY(-50%);
                        color: var(--dark-gray);
                        font-size: 12px;
                    "></i>
                </div>
            `;
            
            sidebar.insertBefore(searchBox, sidebar.firstChild);
            
            // Search functionality
            const searchInput = searchBox.querySelector('#sidebar-search-input');
            const allLinks = sidebar.querySelectorAll('.module a');
            
            searchInput.addEventListener('input', function() {
                const query = this.value.toLowerCase();
                
                allLinks.forEach(link => {
                    const text = link.textContent.toLowerCase();
                    const module = link.closest('.module');
                    
                    if (text.includes(query) || query === '') {
                        link.style.display = '';
                        module.style.display = '';
                        
                        if (query !== '') {
                            // Highlight matching text
                            const originalText = link.textContent;
                            const highlightedText = originalText.replace(
                                new RegExp(query, 'gi'),
                                match => `<mark style="background: var(--secondary-yellow); padding: 1px 2px; border-radius: 2px;">${match}</mark>`
                            );
                            link.innerHTML = highlightedText;
                        } else {
                            // Remove highlights
                            link.innerHTML = link.textContent;
                        }
                    } else {
                        link.style.display = 'none';
                    }
                });
                
                // Hide empty modules
                const modules = sidebar.querySelectorAll('.module');
                modules.forEach(module => {
                    const visibleLinks = Array.from(module.querySelectorAll('a')).filter(
                        link => link.style.display !== 'none'
                    );
                    module.style.display = visibleLinks.length > 0 ? '' : 'none';
                });
            });
            
            // Focus enhancement
            searchInput.addEventListener('focus', function() {
                this.style.borderColor = 'var(--primary-blue)';
                this.style.boxShadow = '0 0 0 2px rgba(21, 101, 192, 0.1)';
            });
            
            searchInput.addEventListener('blur', function() {
                this.style.borderColor = 'var(--medium-gray)';
                this.style.boxShadow = 'none';
            });
        }
    }
    
    // Add sidebar search
    addSidebarSearch();
    
    // Add loading animation for page transitions
    const adminLinks = document.querySelectorAll('#nav-sidebar a, .object-tools a');
    adminLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Add loading overlay
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(21, 101, 192, 0.9);
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 18px;
            `;
            overlay.innerHTML = `
                <div style="text-align: center;">
                    <div style="border: 3px solid rgba(255,255,255,0.3); border-top: 3px solid white; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 15px;"></div>
                    <div>Loading...</div>
                </div>
                <style>
                    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                </style>
            `;
            
            document.body.appendChild(overlay);
            
            // Remove overlay after page loads (fallback)
            setTimeout(() => {
                if (document.body.contains(overlay)) {
                    document.body.removeChild(overlay);
                }
            }, 3000);
        });
    });
});

// Add dynamic dashboard widgets
function addDashboardEnhancements() {
    const dashboard = document.querySelector('#content');
    if (dashboard && window.location.pathname === '/admin/') {
        // Add floating action button
        const fab = document.createElement('div');
        fab.style.cssText = `
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            background: var(--primary-gradient);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(21, 101, 192, 0.3);
            transition: all 0.3s ease;
            z-index: 1000;
        `;
        
        fab.innerHTML = '<i class="fas fa-plus"></i>';
        
        // FAB interactions
        fab.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.1)';
            this.style.boxShadow = '0 6px 25px rgba(21, 101, 192, 0.4)';
        });
        
        fab.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = '0 4px 20px rgba(21, 101, 192, 0.3)';
        });
        
        fab.addEventListener('click', function() {
            // Show quick add menu
            const menu = document.createElement('div');
            menu.style.cssText = `
                position: fixed;
                bottom: 100px;
                right: 30px;
                background: white;
                border-radius: 10px;
                padding: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                z-index: 1001;
                min-width: 200px;
            `;
            
            menu.innerHTML = `
                <h4 style="margin: 0 0 10px 0; color: var(--primary-blue);">Quick Add</h4>
                <a href="/admin/stores/storeproduct/add/" style="display: block; padding: 8px 0; color: var(--text-dark); text-decoration: none; border-bottom: 1px solid #eee;">
                    <i class="fas fa-plus" style="margin-right: 8px; color: var(--success-green);"></i>
                    Add Product
                </a>
                <a href="/admin/stores/store/add/" style="display: block; padding: 8px 0; color: var(--text-dark); text-decoration: none; border-bottom: 1px solid #eee;">
                    <i class="fas fa-store" style="margin-right: 8px; color: var(--primary-blue);"></i>
                    Add Store
                </a>
                <a href="/admin/catalog/category/add/" style="display: block; padding: 8px 0; color: var(--text-dark); text-decoration: none;">
                    <i class="fas fa-tags" style="margin-right: 8px; color: var(--warning-orange);"></i>
                    Add Category
                </a>
            `;
            
            document.body.appendChild(menu);
            
            // Close menu when clicking outside
            setTimeout(() => {
                document.addEventListener('click', function closeMenu(e) {
                    if (!menu.contains(e.target) && e.target !== fab) {
                        document.body.removeChild(menu);
                        document.removeEventListener('click', closeMenu);
                    }
                });
            }, 100);
        });
        
        document.body.appendChild(fab);
    }
}

// Initialize dashboard enhancements
setTimeout(addDashboardEnhancements, 500);
