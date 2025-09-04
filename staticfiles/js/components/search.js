// Search Functionality JavaScript
document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
});

function initializeSearch() {
    const searchInput = document.getElementById('search-input');
    const searchForm = document.querySelector('.search-form');
    
    if (searchInput) {
        // Handle Enter key
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });
        
        // Handle search suggestions (optional)
        searchInput.addEventListener('input', debounce(function() {
            const query = this.value.trim();
            if (query.length > 2) {
                fetchSearchSuggestions(query);
            } else {
                hideSearchSuggestions();
            }
        }, 300));
    }
    
    // Handle search form submission
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            performSearch();
        });
    }
    
    // Search button click
    const searchBtn = document.querySelector('.search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', function(e) {
            e.preventDefault();
            performSearch();
        });
    }
}

function performSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;
    
    const query = searchInput.value.trim();
    if (query) {
        // Redirect to search results page
        window.location.href = `/catalog/?q=${encodeURIComponent(query)}`;
    }
}

function fetchSearchSuggestions(query) {
    fetch(`/catalog/api/search-suggestions/?q=${encodeURIComponent(query)}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.suggestions) {
            showSearchSuggestions(data.suggestions);
        }
    })
    .catch(error => {
        console.error('Error fetching suggestions:', error);
    });
}

function showSearchSuggestions(suggestions) {
    hideSearchSuggestions(); // Remove any existing suggestions
    
    if (suggestions.length === 0) return;
    
    const searchForm = document.querySelector('.search-form');
    if (!searchForm) return;
    
    const suggestionsHtml = `
        <div class="search-suggestions position-absolute w-100" style="top: 100%; z-index: 1000;">
            <div class="search-results">
                ${suggestions.map(suggestion => `
                    <div class="search-result-item" data-query="${suggestion.name}">
                        <div class="d-flex align-items-center">
                            <i class="fas fa-search text-muted me-2"></i>
                            <span>${suggestion.name}</span>
                            <small class="text-muted ms-auto">${suggestion.category || ''}</small>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    searchForm.insertAdjacentHTML('beforeend', suggestionsHtml);
    
    // Add click handlers to suggestion items
    document.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', function() {
            const query = this.dataset.query;
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.value = query;
                performSearch();
            }
        });
    });
    
    // Hide suggestions when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchForm.contains(e.target)) {
            hideSearchSuggestions();
        }
    });
}

function hideSearchSuggestions() {
    const suggestions = document.querySelector('.search-suggestions');
    if (suggestions) {
        suggestions.remove();
    }
}

// Advanced search filters
function initializeSearchFilters() {
    const filterCheckboxes = document.querySelectorAll('.search-filter');
    
    filterCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSearchFilters();
        });
    });
}

function updateSearchFilters() {
    const activeFilters = [];
    document.querySelectorAll('.search-filter:checked').forEach(checkbox => {
        activeFilters.push(checkbox.value);
    });
    
    const searchParams = new URLSearchParams(window.location.search);
    const query = searchParams.get('q') || '';
    
    // Update URL with filters
    const url = new URL(window.location.href);
    url.searchParams.delete('category');
    url.searchParams.delete('price_min');
    url.searchParams.delete('price_max');
    
    activeFilters.forEach(filter => {
        const [key, value] = filter.split(':');
        url.searchParams.append(key, value);
    });
    
    window.location.href = url.toString();
}
