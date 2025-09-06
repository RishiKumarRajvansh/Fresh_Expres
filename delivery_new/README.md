# Delivery System Documentation

## Overview

The Fresh Express delivery system manages all delivery operations, including agent management, delivery tracking, and order fulfillment. This system replaces the legacy delivery app with an improved architecture and feature set.

## Migration Status

The migration from the old `delivery` app to `delivery_new` was completed on September 6, 2025. The old delivery app has been completely removed from the codebase. URLs that previously pointed to `/delivery/` now redirect to this app.

## Models

1. **DeliveryAgent**
   - Represents delivery personnel
   - Tracks availability, service area, and performance metrics

2. **Delivery**
   - Main model for order deliveries
   - Tracks the status of a delivery from assignment to completion

3. **DeliveryTracking**
   - Logs location updates during delivery
   - Used for customer tracking and analytics

4. **DeliveryIssue**
   - Records problems during delivery
   - Supports issue resolution workflow

5. **DeliveryRating**
   - Stores customer ratings for deliveries
   - Used for agent performance evaluation

## Usage Examples

### Creating a New Delivery

```python
from delivery_new.models import Delivery, DeliveryAgent

# Get an available agent
agent = DeliveryAgent.objects.filter(is_available=True).first()

# Create a delivery
delivery = Delivery.objects.create(
    order=order,
    agent=agent,
    status='assigned'
)
```

### Updating Delivery Status

```python
# Get a delivery
delivery = Delivery.objects.get(order=order)

# Update status
delivery.status = 'in_transit'
delivery.save()
```

### Tracking a Delivery

```python
# Get tracking points
tracking_points = delivery.tracking_points.order_by('-timestamp')

# Get the latest location
latest_location = tracking_points.first()
```

## URL Structure

The app is accessible at `/delivery/` and `/delivery-new/` (both URLs point to the same views).

Main routes:
- `/delivery/dashboard/` - Agent dashboard
- `/delivery/deliveries/` - List of deliveries
- `/delivery/agents/` - Agent management

## Best Practices

1. **Use the new models directly**:
   - Import from `delivery_new.models`
   - Use the new model names (`Delivery` instead of `DeliveryAssignment`)

2. **Update template references**:
   - Use `{% url 'delivery_new:route_name' %}` in templates
   - Check for hardcoded URLs and update them

For any questions or issues, please consult the development team.
