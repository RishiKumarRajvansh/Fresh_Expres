"""
Real-time Inventory Synchronization Services
Handles automatic stock updates, cross-store visibility, and intelligent transfers
"""
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Sum, F, Q, Avg
from decimal import Decimal
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class InventorySyncService:
    """Core service for real-time inventory synchronization"""
    
    @staticmethod
    def update_stock(store, product, new_quantity, reason="Manual update", user=None):
        """Update stock with real-time sync across all systems"""
        from catalog.models import StoreProduct
        from catalog.models_inventory import InventorySyncEvent, StockAlert
        
        with transaction.atomic():
            try:
                store_product = StoreProduct.objects.select_for_update().get(
                    store=store, product=product
                )
                previous_quantity = store_product.stock_quantity
                
                # Update stock
                store_product.stock_quantity = new_quantity
                store_product.last_stock_update = timezone.now()
                store_product.save()
                
                # Create sync event
                InventorySyncEvent.objects.create(
                    product=product,
                    store=store,
                    event_type='stock_update',
                    previous_quantity=previous_quantity,
                    new_quantity=new_quantity,
                    reason=reason,
                    triggered_by=user
                )
                
                # Check for alerts
                InventorySyncService._check_stock_alerts(store_product)
                
                # Update cache
                cache_key = f"stock_{store.id}_{product.id}"
                cache.set(cache_key, new_quantity, timeout=300)
                
                # Broadcast update (for real-time UI updates)
                InventorySyncService._broadcast_stock_update(store, product, new_quantity)
                
                logger.info(f"Stock updated: {product.name} at {store.name}: {previous_quantity} → {new_quantity}")
                return True
                
            except Exception as e:
                logger.error(f"Stock update failed: {str(e)}")
                return False
    
    @staticmethod
    def get_cross_store_inventory(product, zip_area=None):
        """Get inventory levels across all stores for a product"""
        from catalog.models import StoreProduct
        from stores.models import Store
        
        query = StoreProduct.objects.filter(
            product=product,
            store__is_active=True
        ).select_related('store')
        
        if zip_area:
            query = query.filter(store__zip_coverages__zip_area=zip_area)
        
        inventory_data = []
        for sp in query:
            inventory_data.append({
                'store': sp.store,
                'stock_quantity': sp.stock_quantity,
                'selling_price': sp.selling_price,
                'is_available': sp.is_available,
                'last_updated': sp.last_stock_update,
                'distance': 0  # TODO: Calculate based on customer location
            })
        
        # Sort by availability and stock level
        inventory_data.sort(key=lambda x: (not x['is_available'], -x['stock_quantity']))
        return inventory_data
    
    @staticmethod
    def request_inter_store_transfer(from_store, to_store, product, quantity, reason, user):
        """Request inventory transfer between stores"""
        from catalog.models_inventory import InterStoreTransfer
        from catalog.models import StoreProduct
        
        # Check if from_store has enough stock
        try:
            source_product = StoreProduct.objects.get(store=from_store, product=product)
            if source_product.stock_quantity < quantity:
                return False, "Insufficient stock in source store"
        except StoreProduct.DoesNotExist:
            return False, "Product not available in source store"
        
        # Create transfer request
        transfer = InterStoreTransfer.objects.create(
            from_store=from_store,
            to_store=to_store,
            product=product,
            requested_quantity=quantity,
            request_reason=reason,
            requested_by=user,
            priority='medium'
        )
        
        # Auto-approve for same owner stores
        if from_store.owner == to_store.owner:
            transfer.approve(user, notes="Auto-approved for same owner")
        
        logger.info(f"Transfer requested: {quantity}x {product.name} from {from_store.name} to {to_store.name}")
        return True, transfer
    
    @staticmethod
    def process_transfer_completion(transfer, user):
        """Process completed inventory transfer"""
        from catalog.models import StoreProduct
        from catalog.models_inventory import InventorySyncEvent
        
        with transaction.atomic():
            # Update source store inventory
            InventorySyncService.update_stock(
                store=transfer.from_store,
                product=transfer.product,
                new_quantity=F('stock_quantity') - transfer.transferred_quantity,
                reason=f"Transfer out to {transfer.to_store.name}",
                user=user
            )
            
            # Update destination store inventory
            dest_product, created = StoreProduct.objects.get_or_create(
                store=transfer.to_store,
                product=transfer.product,
                defaults={
                    'selling_price': transfer.product.base_price,
                    'stock_quantity': 0
                }
            )
            
            InventorySyncService.update_stock(
                store=transfer.to_store,
                product=transfer.product,
                new_quantity=F('stock_quantity') + transfer.transferred_quantity,
                reason=f"Transfer in from {transfer.from_store.name}",
                user=user
            )
            
            # Create completion events
            InventorySyncEvent.objects.create(
                product=transfer.product,
                store=transfer.to_store,
                event_type='transfer_complete',
                new_quantity=transfer.transferred_quantity,
                reason=f"Transfer completed from {transfer.from_store.name}",
                triggered_by=user,
                transfer=transfer
            )
    
    @staticmethod
    def _check_stock_alerts(store_product):
        """Check and create stock alerts"""
        from catalog.models_inventory import StockAlert, PredictiveRestockRule
        
        # Get restock rules
        try:
            restock_rule = PredictiveRestockRule.objects.get(
                store=store_product.store,
                product=store_product.product,
                is_active=True
            )
            
            current_stock = store_product.stock_quantity
            
            # Check for low stock
            if current_stock <= restock_rule.minimum_stock_level:
                alert_type = 'out_of_stock' if current_stock == 0 else 'low_stock'
                priority = 'critical' if current_stock == 0 else 'high'
                
                StockAlert.objects.get_or_create(
                    product=store_product.product,
                    store=store_product.store,
                    alert_type=alert_type,
                    defaults={
                        'priority': priority,
                        'current_stock': current_stock,
                        'threshold_level': restock_rule.minimum_stock_level,
                        'recommended_restock': restock_rule.calculate_reorder_quantity()
                    }
                )
            
            # Check for restock needed
            elif current_stock <= restock_rule.reorder_level:
                StockAlert.objects.get_or_create(
                    product=store_product.product,
                    store=store_product.store,
                    alert_type='restock_needed',
                    defaults={
                        'priority': 'medium',
                        'current_stock': current_stock,
                        'threshold_level': restock_rule.reorder_level,
                        'recommended_restock': restock_rule.calculate_reorder_quantity()
                    }
                )
        
        except PredictiveRestockRule.DoesNotExist:
            # Create basic low stock alert
            if store_product.stock_quantity <= 5:
                StockAlert.objects.get_or_create(
                    product=store_product.product,
                    store=store_product.store,
                    alert_type='low_stock',
                    defaults={
                        'priority': 'medium',
                        'current_stock': store_product.stock_quantity,
                        'threshold_level': 5,
                        'recommended_restock': 50
                    }
                )
    
    @staticmethod
    def _broadcast_stock_update(store, product, new_quantity):
        """Broadcast stock update for real-time UI updates"""
        # TODO: Implement WebSocket/Server-Sent Events for real-time updates
        # For now, we'll use cache-based updates
        cache_key = f"stock_update_{store.id}_{product.id}"
        cache.set(cache_key, {
            'store_id': store.id,
            'product_id': product.id,
            'quantity': new_quantity,
            'timestamp': timezone.now().isoformat()
        }, timeout=60)
    
    @staticmethod
    def auto_suggest_transfers():
        """Automatically suggest inventory transfers based on demand and availability"""
        from catalog.models import StoreProduct
        from catalog.models_inventory import InterStoreTransfer
        from django.db.models import Avg
        
        suggestions = []
        
        # Find products with imbalanced inventory
        products_needing_transfer = StoreProduct.objects.filter(
            stock_quantity__lte=5,
            is_available=True
        ).select_related('product', 'store')
        
        for low_stock_product in products_needing_transfer:
            # Find stores with excess inventory of same product
            excess_stores = StoreProduct.objects.filter(
                product=low_stock_product.product,
                stock_quantity__gte=20,
                store__is_active=True
            ).exclude(
                store=low_stock_product.store
            ).select_related('store')
            
            for excess_store_product in excess_stores[:3]:  # Top 3 candidates
                # Check if they serve overlapping areas
                common_areas = InventorySyncService._get_common_service_areas(
                    excess_store_product.store,
                    low_stock_product.store
                )
                
                if common_areas:
                    suggestions.append({
                        'from_store': excess_store_product.store,
                        'to_store': low_stock_product.store,
                        'product': low_stock_product.product,
                        'suggested_quantity': min(10, excess_store_product.stock_quantity - 15),
                        'priority': 'high' if low_stock_product.stock_quantity == 0 else 'medium',
                        'reason': f"Auto-suggested: Low stock ({low_stock_product.stock_quantity}) in {low_stock_product.store.name}"
                    })
        
        return suggestions
    
    @staticmethod
    def _get_common_service_areas(store1, store2):
        """Get common service areas between two stores"""
        from stores.models import StoreZipCoverage
        
        store1_zips = set(
            StoreZipCoverage.objects.filter(store=store1, is_active=True)
            .values_list('zip_area__zip_code', flat=True)
        )
        
        store2_zips = set(
            StoreZipCoverage.objects.filter(store=store2, is_active=True)
            .values_list('zip_area__zip_code', flat=True)
        )
        
        return store1_zips.intersection(store2_zips)


class PredictiveRestockService:
    """Service for predictive restocking algorithms"""
    
    @staticmethod
    def calculate_demand_patterns(product, store, days=30):
        """Calculate demand patterns for predictive restocking"""
        from orders.models import OrderItem
        from catalog.models_inventory import InventorySnapshot
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get order data
        order_data = OrderItem.objects.filter(
            order__store=store,
            product=product,
            order__status='delivered',
            order__created_at__date__range=[start_date, end_date]
        ).values('order__created_at__date').annotate(
            daily_demand=Sum('quantity')
        )
        
        daily_demands = [item['daily_demand'] for item in order_data]
        
        if not daily_demands:
            return {
                'avg_daily_demand': 0,
                'max_daily_demand': 0,
                'demand_variance': 0,
                'trend': 'stable'
            }
        
        avg_demand = sum(daily_demands) / len(daily_demands)
        max_demand = max(daily_demands)
        variance = sum((x - avg_demand) ** 2 for x in daily_demands) / len(daily_demands)
        
        # Simple trend calculation
        if len(daily_demands) >= 7:
            recent_avg = sum(daily_demands[-7:]) / 7
            older_avg = sum(daily_demands[:-7]) / (len(daily_demands) - 7)
            
            if recent_avg > older_avg * 1.1:
                trend = 'increasing'
            elif recent_avg < older_avg * 0.9:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        return {
            'avg_daily_demand': avg_demand,
            'max_daily_demand': max_demand,
            'demand_variance': variance,
            'trend': trend,
            'total_days': len(daily_demands)
        }
    
    @staticmethod
    def update_restock_rules(store, product=None):
        """Update predictive restock rules based on historical data"""
        from catalog.models_inventory import PredictiveRestockRule
        from catalog.models import StoreProduct
        
        if product:
            products = [product]
        else:
            products = StoreProduct.objects.filter(
                store=store, is_available=True
            ).values_list('product', flat=True)
        
        for prod in products:
            demand_data = PredictiveRestockService.calculate_demand_patterns(prod, store)
            
            if demand_data['avg_daily_demand'] > 0:
                # Calculate optimal levels
                avg_demand = demand_data['avg_daily_demand']
                safety_multiplier = 1.5 if demand_data['trend'] == 'increasing' else 1.2
                
                minimum_level = int(avg_demand * 2)  # 2 days buffer
                reorder_level = int(avg_demand * 3 * safety_multiplier)  # 3 days + safety
                maximum_level = int(avg_demand * 7 * safety_multiplier)  # 1 week + safety
                
                PredictiveRestockRule.objects.update_or_create(
                    product=prod,
                    store=store,
                    defaults={
                        'minimum_stock_level': minimum_level,
                        'reorder_level': reorder_level,
                        'maximum_stock_level': maximum_level,
                        'avg_daily_demand': Decimal(str(avg_demand)),
                        'demand_variance': Decimal(str(demand_data['demand_variance'])),
                        'is_active': True
                    }
                )
                
                logger.info(f"Updated restock rules for {prod.name} at {store.name}")


class InventoryAnalyticsService:
    """Service for inventory analytics and insights"""
    
    @staticmethod
    def create_daily_snapshot():
        """Create daily inventory snapshots for all stores"""
        from catalog.models import StoreProduct
        from catalog.models_inventory import InventorySnapshot
        from orders.models import OrderItem
        from django.utils import timezone
        
        today = timezone.now().date()
        
        for store_product in StoreProduct.objects.all():
            # Get today's sales
            daily_sales = OrderItem.objects.filter(
                order__store=store_product.store,
                product=store_product.product,
                order__status='delivered',
                order__created_at__date=today
            ).aggregate(
                total_sold=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('unit_price'))
            )
            
            # Calculate turnover rate
            turnover_rate = Decimal('0.00')
            if store_product.stock_quantity > 0:
                sold_qty = daily_sales['total_sold'] or 0
                turnover_rate = Decimal(sold_qty) / Decimal(store_product.stock_quantity) * 100
            
            InventorySnapshot.objects.update_or_create(
                store=store_product.store,
                product=store_product.product,
                snapshot_date=today,
                defaults={
                    'closing_stock': store_product.stock_quantity,
                    'stock_out': daily_sales['total_sold'] or 0,
                    'total_revenue': daily_sales['total_revenue'] or Decimal('0.00'),
                    'average_selling_price': store_product.selling_price,
                    'turnover_rate': turnover_rate
                }
            )
    
    @staticmethod
    def get_inventory_insights(store, days=30):
        """Get comprehensive inventory insights for a store"""
        from catalog.models_inventory import InventorySnapshot, StockAlert
        from django.utils import timezone
        from datetime import timedelta
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get snapshots
        snapshots = InventorySnapshot.objects.filter(
            store=store,
            snapshot_date__range=[start_date, end_date]
        )
        
        # Calculate insights
        total_revenue = snapshots.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')
        avg_turnover = snapshots.aggregate(Avg('turnover_rate'))['turnover_rate__avg'] or Decimal('0.00')
        
        # Active alerts
        active_alerts = StockAlert.objects.filter(
            store=store,
            is_active=True
        ).count()
        
        # Top performing products
        top_products = snapshots.values(
            'product__name'
        ).annotate(
            total_revenue=Sum('total_revenue'),
            avg_turnover=Avg('turnover_rate')
        ).order_by('-total_revenue')[:10]
        
        return {
            'period_days': days,
            'total_revenue': total_revenue,
            'avg_turnover_rate': avg_turnover,
            'active_alerts': active_alerts,
            'top_products': list(top_products),
            'snapshot_count': snapshots.count()
        }
