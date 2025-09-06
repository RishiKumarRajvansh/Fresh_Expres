from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from delivery.models import DeliveryAgent as OldDeliveryAgent
from delivery.models import DeliveryAssignment as OldDeliveryAssignment
from delivery_new.models import DeliveryAgent, Delivery, DeliveryTracking, DeliveryIssue, DeliveryRating

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrates data from the old delivery system to the new one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making any changes to the database',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY RUN mode. No changes will be made.'))
        
        self.stdout.write(self.style.SUCCESS('Starting migration from old delivery system to new...'))
        
        # Start a transaction that we can rollback if needed
        sid = transaction.savepoint()
        
        try:
            # Step 1: Migrate delivery agents
            self.migrate_agents(dry_run)
            
            # Step 2: Migrate delivery assignments
            self.migrate_deliveries(dry_run)
            
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN completed. Rolling back changes.'))
                transaction.savepoint_rollback(sid)
            else:
                transaction.savepoint_commit(sid)
                self.stdout.write(self.style.SUCCESS('Migration completed successfully!'))
                
        except Exception as e:
            transaction.savepoint_rollback(sid)
            self.stdout.write(self.style.ERROR(f'Error during migration: {str(e)}'))
            logger.exception("Migration failed")
            raise
    
    @transaction.atomic
    def migrate_agents(self, dry_run):
        """Migrate delivery agents from old system to new"""
        self.stdout.write('Migrating delivery agents...')
        
        # Count old agents
        old_agents_count = OldDeliveryAgent.objects.count()
        self.stdout.write(f'Found {old_agents_count} agents to migrate')
        
        # Counter for agents migrated
        migrated_count = 0
        skipped_count = 0
        
        old_agents = OldDeliveryAgent.objects.select_related('user', 'store').all()
        
        for old_agent in old_agents:
            # Check if already migrated
            if DeliveryAgent.objects.filter(user=old_agent.user).exists():
                self.stdout.write(f'  Agent for user {old_agent.user.username} already exists, skipping')
                skipped_count += 1
                continue
                
            # Get agent store
            store = getattr(old_agent, 'store', None)
            
            # Map status
            if hasattr(old_agent, 'status'):
                status = old_agent.status
            else:
                status = 'active' if getattr(old_agent, 'is_active', True) else 'offline'
            
            # Create new agent
            new_agent = DeliveryAgent(
                user=old_agent.user,
                phone_number=getattr(old_agent, 'phone_number', ''),
                alternative_phone=getattr(old_agent, 'alternative_phone', None),
                status=status,
                is_available=getattr(old_agent, 'is_available', False),
                max_concurrent_orders=getattr(old_agent, 'max_concurrent_orders', 3),
                service_area_radius=getattr(old_agent, 'service_radius', 10),
                vehicle_type=getattr(old_agent, 'vehicle_type', 'scooter'),
                vehicle_number=getattr(old_agent, 'vehicle_number', None),
                current_latitude=getattr(old_agent, 'latitude', None),
                current_longitude=getattr(old_agent, 'longitude', None),
                last_location_update=timezone.now() if getattr(old_agent, 'latitude', None) else None,
                total_deliveries=getattr(old_agent, 'total_deliveries', 0),
                successful_deliveries=getattr(old_agent, 'successful_deliveries', 0),
                average_rating=getattr(old_agent, 'rating', 0.00),
            )
            
            if store:
                new_agent.store = store
            
            if not dry_run:
                new_agent.save()
                migrated_count += 1
                self.stdout.write(f'  Migrated agent: {new_agent.agent_id} - {new_agent.user.username}')
        
        self.stdout.write(self.style.SUCCESS(f'Migrated {migrated_count} agents, skipped {skipped_count} agents'))
    
    @transaction.atomic
    def migrate_deliveries(self, dry_run):
        """Migrate delivery assignments from old system to new"""
        self.stdout.write('Migrating delivery assignments...')
        
        # Count old deliveries
        old_deliveries_count = OldDeliveryAssignment.objects.count()
        self.stdout.write(f'Found {old_deliveries_count} deliveries to migrate')
        
        # Counter for deliveries migrated
        migrated_count = 0
        skipped_count = 0
        
        old_deliveries = OldDeliveryAssignment.objects.select_related('order', 'agent', 'agent__user').all()
        
        for old_delivery in old_deliveries:
            # Skip if already migrated (check by order as orders should only have one delivery)
            if Delivery.objects.filter(order=old_delivery.order).exists():
                self.stdout.write(f'  Delivery for order {old_delivery.order.order_number} already exists, skipping')
                skipped_count += 1
                continue
                
            # Find the corresponding new agent
            try:
                new_agent = DeliveryAgent.objects.get(user=old_delivery.agent.user)
            except DeliveryAgent.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'  Agent not found for delivery {old_delivery.id}, skipping'))
                skipped_count += 1
                continue
            
            # Map old status to new status
            status_map = {
                'pending': 'assigned',
                'assigned': 'assigned',
                'accepted': 'accepted',
                'at_store': 'at_store',
                'picked_up': 'picked_up',
                'in_transit': 'in_transit',
                'delivered': 'delivered',
                'cancelled': 'cancelled',
                'failed': 'failed',
                'completed': 'delivered',
            }
            
            new_status = status_map.get(old_delivery.status, 'assigned')
            
            # Create new delivery
            new_delivery = Delivery(
                order=old_delivery.order,
                agent=new_agent,
                status=new_status,
                delivery_fee=getattr(old_delivery, 'delivery_fee', 0) or Decimal('5.00'),
                agent_payout=getattr(old_delivery, 'agent_payout', 0) or Decimal('10.00'),
                
                # Timestamps - map as available
                assigned_at=getattr(old_delivery, 'assigned_at', old_delivery.created_at),
                accepted_at=getattr(old_delivery, 'accepted_at', None),
                arrived_at_store_at=getattr(old_delivery, 'arrived_at_store_at', None),
                picked_up_at=getattr(old_delivery, 'picked_up_at', None),
                delivered_at=getattr(old_delivery, 'delivered_at', None) if new_status == 'delivered' else None,
                
                # Generate new OTPs
                store_pickup_otp=None,  # Will be auto-generated in save()
                customer_delivery_otp=None,  # Will be auto-generated in save()
                
                # Verification status
                store_pickup_verified=new_status in ['picked_up', 'in_transit', 'delivered'],
                customer_delivery_verified=new_status in ['delivered'],
            )
            
            if not dry_run:
                new_delivery.save()
                migrated_count += 1
                self.stdout.write(f'  Migrated delivery: {new_delivery.delivery_id} - Order: {new_delivery.order.order_number}')
                
                # Create tracking point
                DeliveryTracking.objects.create(
                    delivery=new_delivery,
                    latitude=getattr(old_delivery.agent, 'latitude', 0) or Decimal('0'),
                    longitude=getattr(old_delivery.agent, 'longitude', 0) or Decimal('0'),
                )
        
        self.stdout.write(self.style.SUCCESS(f'Migrated {migrated_count} deliveries, skipped {skipped_count} deliveries'))
    
    def map_status(self, old_status):
        """Map old status values to new ones"""
        status_map = {
            'pending': 'assigned',
            'assigned': 'assigned',
            'accepted': 'accepted',
            'at_store': 'at_store',
            'picked_up': 'picked_up',
            'in_transit': 'in_transit',
            'delivered': 'delivered',
            'cancelled': 'cancelled',
            'failed': 'failed',
            'completed': 'delivered',
        }
        return status_map.get(old_status, 'assigned')
