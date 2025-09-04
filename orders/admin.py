from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, OrderStatusHistory, Coupon, CouponUsage, Complaint

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'store', 'total_items', 'is_active', 'created_at')
    list_filter = ('is_active', 'store', 'created_at')
    search_fields = ('user__username', 'store__name', 'session_key')
    inlines = [CartItemInline]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'store', 'status', 'delivery_confirmation_code', 'handover_code', 'total_amount', 'workflow_status', 'created_at')
    list_filter = ('status', 'payment_status', 'store', 'created_at')
    search_fields = ('order_number', 'user__username', 'store__name', 'delivery_confirmation_code', 'handover_code')
    readonly_fields = ('order_number', 'order_id', 'delivery_confirmation_code', 'handover_code', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'order_id', 'user', 'store', 'status', 'payment_status', 'payment_method')
        }),
        ('Workflow Codes', {
            'fields': ('delivery_confirmation_code', 'handover_code'),
            'classes': ('wide',),
            'description': 'Automatically generated codes for order workflow - these codes are used for store handover and customer delivery verification'
        }),
        ('Delivery Information', {
            'fields': ('delivery_address', 'delivery_slot', 'estimated_delivery_time', 'actual_delivery_time', 'delivery_instructions')
        }),
        ('Handover Tracking', {
            'fields': ('handover_to_delivery_time', 'delivery_agent_confirmed', 'store_handover_confirmed', 'handover_verification_code')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'delivery_fee', 'tax_amount', 'discount_amount', 'total_amount')
        }),
        ('Payment Details', {
            'fields': ('payment_id', 'payment_details')
        }),
        ('Notes', {
            'fields': ('customer_notes', 'store_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    
    actions = ['generate_workflow_codes', 'export_workflow_report']
    
    def workflow_status(self, obj):
        """Display workflow completion status"""
        status_items = []
        if obj.delivery_confirmation_code:
            status_items.append('✅ Delivery Code')
        else:
            status_items.append('❌ Delivery Code')
            
        if obj.handover_code:
            status_items.append('✅ Handover Code')
        else:
            status_items.append('❌ Handover Code')
            
        return ' | '.join(status_items)
    workflow_status.short_description = 'Workflow Codes Status'
    
    def generate_workflow_codes(self, request, queryset):
        """Admin action to generate missing workflow codes"""
        updated_count = 0
        for order in queryset:
            old_status = order.status
            # Force code generation by saving
            order.save()
            if order.delivery_confirmation_code or order.handover_code:
                updated_count += 1
        
        self.message_user(request, f'Successfully generated workflow codes for {updated_count} orders.')
    generate_workflow_codes.short_description = 'Generate missing workflow codes'
    
    def export_workflow_report(self, request, queryset):
        """Export workflow codes for selected orders"""
        import csv
        from django.http import HttpResponse
        from datetime import datetime
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="workflow_codes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Customer', 'Store', 'Status', 
            'Delivery Confirmation Code', 'Handover Code', 
            'Total Amount', 'Created Date'
        ])
        
        for order in queryset:
            writer.writerow([
                order.order_number,
                order.user.username if order.user else 'Guest',
                order.store.name,
                order.get_status_display(),
                order.delivery_confirmation_code or 'Not Generated',
                order.handover_code or 'Not Generated',
                f'${order.total_amount}',
                order.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_workflow_report.short_description = 'Export workflow codes report'
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        # Make workflow codes readonly as they are auto-generated
        if obj and obj.delivery_confirmation_code:
            readonly.append('delivery_confirmation_code')
        if obj and obj.handover_code:
            readonly.append('handover_code')
        return readonly

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'coupon_type', 'value', 'is_active', 'start_date', 'end_date')
    list_filter = ('coupon_type', 'is_active', 'start_date', 'end_date')
    search_fields = ('code', 'description')

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('order', 'complaint_type', 'status', 'created_at')
    list_filter = ('complaint_type', 'status', 'created_at')
    search_fields = ('order__order_number', 'subject', 'description')
