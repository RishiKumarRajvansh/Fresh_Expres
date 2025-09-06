from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from delivery.models import DeliveryAgent, DeliveryAssignment


class Command(BaseCommand):
    help = 'Cleans up old delivery system data after migration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm the deletion of old data',
        )

    def handle(self, *args, **kwargs):
        confirm = kwargs.get('confirm')
        
        if not confirm:
            self.stdout.write(self.style.WARNING(
                'This command will delete ALL data from the old delivery system. '
                'Run with --confirm to proceed.'
            ))
            return
        
        self.stdout.write(self.style.SUCCESS('Starting cleanup of old delivery system data...'))
        
        # Step 1: Count and report on data to be deleted
        assignment_count = DeliveryAssignment.objects.count()
        agent_count = DeliveryAgent.objects.count()
        
        self.stdout.write(f'Found {assignment_count} delivery assignments and {agent_count} delivery agents to clean up.')
        
        # Step 2: Delete all data with transaction
        with transaction.atomic():
            # Delete assignments first (foreign key relationships)
            deleted_assignments = DeliveryAssignment.objects.all().delete()
            self.stdout.write(f'Deleted {deleted_assignments[0]} delivery assignments.')
            
            # Delete agents
            deleted_agents = DeliveryAgent.objects.all().delete()
            self.stdout.write(f'Deleted {deleted_agents[0]} delivery agents.')
        
        self.stdout.write(self.style.SUCCESS('Old delivery system data has been cleaned up successfully!'))
