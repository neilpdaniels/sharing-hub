# Integration Guide for Friends Module and Transaction Changes

## Summary of Changes

This document outlines all changes made to the Sharing Hub project to:
1. Add a friends module for managing user relationships
2. Add location-based filtering to transactions
3. Rename transaction types (BUY→WANTED, SELL→TO LET)
4. Implement friend/non-friend pricing
5. Remove reference pricing functionality

## 1. Friends Module Integration

### Add to Main URLs
In `sharing_hub/urls.py`, add the friends URL configuration:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing urls ...
    path('friends/', include('friends.urls')),
]
```

### Test the Friends Module
```bash
python manage.py test friends
```

## 2. Running Migrations

The models have been updated. Create and run migrations:

```bash
# Create migrations for all changed apps
python manage.py makemigrations friends
python manage.py makemigrations common
python manage.py makemigrations transaction

# Apply all migrations
python manage.py migrate
```

### Migration Details

#### `common` (Order model changes):
- Changes `BUY`/`SELL` to `WANTED`/`TO_LET`
- Adds `latitude`, `longitude`, `radius_km` fields
- Removes `price_style`, `relative_price_pct`, `relative_offset` fields

#### `transaction` (Transaction model changes):
- Adds `friend_price` field for friend-specific pricing

#### `friends` (New app):
- Creates `Friendship` model
- Creates `django_admin` entries

## 3. Template Updates Required

The following templates reference removed Order model fields and need updating:

### `transaction/templates/transaction/add_order.html`
**Remove** these lines (around line 38-41):
```django
{% bootstrap_field order_form.price_style addon_after='...' %}
{% bootstrap_field order_form.relative_price_pct %}
{% bootstrap_field order_form.relative_offset %}
```

Also remove JavaScript handling for these fields (around line 115-185).

**Add** these lines to include location fields:
```django
{% bootstrap_field order_form.latitude %}
{% bootstrap_field order_form.longitude %}
{% bootstrap_field order_form.radius_km %}
```

### `transaction/templates/transaction/hit_order.html`
**Remove** references to transaction fee `price_style` if they're specific to pricing type display.

Update any display logic that assumes relative pricing.

### `navigation/templates/navigation/index.html`
**Remove** references to `gold_ref`, `silver_ref`, `platinum_ref`, `palladium_ref` context variables.

## 4. Transaction Views Update

If you have custom views for creating/editing transactions that handle pricing, update them to:
- Not reference `price_style`
- Not calculate relative pricing
- Use `friend_price` when displaying to friends

Example pricing helper:
```python
from friends.models import FriendsHelper

def get_transaction_price(transaction, viewing_user):
    """Get the appropriate price for a transaction based on friendship."""
    if FriendsHelper.are_friends(transaction.user_aggressive, viewing_user):
        return transaction.friend_price or transaction.price
    return transaction.price
```

## 5. Query Updates for Location-Based Filtering

When filtering orders, you can now use location fields:

```python
from django.db.models import DecimalField
from django.db.models.functions import ACos, Cos, Radians, Sin
from django.db.models import F, FloatField, Value
from math import pi

# Calculate haversine distance (simplified)
# Earth's radius in km
EARTH_RADIUS_KM = 6371

def get_orders_within_radius(latitude, longitude, radius_km):
    """Get all orders within a certain radius."""
    return Order.objects.filter(
        radius_km__gte=distance_calculation  # Your distance calculation
    )
```

Or use a simpler approach if you have PostGIS:
```python
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

orders = Order.objects.annotate(
    distance=Distance('point_field', Point(longitude, latitude))
).filter(distance__lte=F('radius_km'))
```

## 6. Admin Interface Updates

The Friends app admin is automatically registered. To customize Order admin to show location fields:

```python
# common/admin.py
from django.contrib import admin
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'direction', 'price', 'latitude', 'longitude', 'radius_km', 'expiry_date')
    list_filter = ('direction', 'status', 'created_date')
    search_fields = ('product__name', 'user__username', 'order_reference')
    fieldsets = (
        ('Basic Info', {
            'fields': ('product', 'user', 'direction', 'quantity', 'status')
        }),
        ('Pricing', {
            'fields': ('price', 'description', 'currency')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'radius_km')
        }),
        ('Dates', {
            'fields': ('expiry_date', 'amended', 'create_date')
        }),
    )
```

## 7. Update Tests

Check for tests that verify transaction types or pricing:

- Update test fixtures to use `WANTED`/`TO_LET` instead of `BUY`/`SELL`
- Update tests that check `price_style` or relative pricing
- Add tests for location-based filtering
- Add tests for friend pricing

Example test update:
```python
# Before
order = Order.objects.create(
    direction=Order.BUY,
    price_style=Order.RELATIVE,
    relative_price_pct=5
)

# After
order = Order.objects.create(
    direction=Order.WANTED,
    price=100.00
)
```

## 8. Remove Reference Price Module

Once everything is migrated and working, you can remove the reference_price app:

```bash
# Backup first (optional)
cp -r reference_price reference_price.backup

# Delete the directory
rm -rf reference_price
```

Also remove from `sharing_hub/settings/base.py` if not already done:
- Already removed from INSTALLED_APPS ✓

## 9. Environment Variables & Settings

No new environment variables are required.

The friends module uses Django's built-in User model and requires:
- `AUTH_USER_MODEL` setting (standard Django)
- `simple_history` app (already in INSTALLED_APPS)

## 10. Data Migration Notes

When running `python manage.py migrate`:

1. **Order model changes**: 
   - Existing `direction` values will need updating
   - New location fields will be NULL by default
   - Create a data migration to backfill if needed

2. **Transaction model**:
   - `friend_price` will be NULL for existing transactions
   - No data loss

3. **Friends model**:
   - New table created
   - No conflicts with existing data

### Creating Data Migration for Direction Change

If needed, create a data migration:
```bash
python manage.py makemigrations common --empty --name migrate_buy_sell_to_wanted_to_let
```

Then edit the migration file:
```python
from django.db import migrations

def migrate_directions(apps, schema_editor):
    Order = apps.get_model('common', 'Order')
    Order.objects.filter(direction='B').update(direction='W')  # BUY → WANTED
    Order.objects.filter(direction='S').update(direction='L')  # SELL → TO LET

def reverse_migrate_directions(apps, schema_editor):
    Order = apps.get_model('common', 'Order')
    Order.objects.filter(direction='W').update(direction='B')
    Order.objects.filter(direction='L').update(direction='S')

class Migration(migrations.Migration):
    dependencies = [
        ('common', 'previous_migration'),
    ]

    operations = [
        migrations.RunPython(migrate_directions, reverse_migrate_directions),
    ]
```

## 11. Frontend Navigation

To add the friends section to your navigation menu, update your base template:

```django
{% if user.is_authenticated %}
    <li class="nav-item">
        <a class="nav-link" href="{% url 'friends:friends_list' %}">Friends</a>
    </li>
{% endif %}
```

## 12. API Considerations (if applicable)

If you have a REST API:
- Update serializers to include new fields
- Update API endpoints for transaction listing to filter by location
- Add friends-related endpoints
- Update documentation

## Verification Checklist

After migration:

- [ ] Migrations applied successfully
- [ ] Friends app admin page accessible
- [ ] User can add friends via web interface
- [ ] Friendship statuses work correctly (PENDING/ACCEPTED/BLOCKED)
- [ ] Order model shows new location fields in admin
- [ ] Transaction model shows friend_price field in admin
- [ ] Old reference_price references removed
- [ ] Tests pass: `python manage.py test`
- [ ] No import errors for reference_price
- [ ] Templates render without errors
- [ ] Location-based queries work
- [ ] Friend pricing logic works in transaction views

## Rollback Plan

If needed to rollback:

```bash
# Unapply migrations
python manage.py migrate common HEAD~1
python manage.py migrate transaction HEAD~1
python manage.py migrate friends zero

# Note: Data migration for BUY→WANTED must be manually reversed
```

Then restore the reference_price app from backup.

## Support & Troubleshooting

### Common Issues

**Q: Migration fails with "no such table"**
A: This usually means app isn't in INSTALLED_APPS. Check `sharing_hub/settings/base.py` includes `'friends.apps.FriendsConfig'`.

**Q: "ReferencePrice" import errors**
A: Remove import statements from navigation/views.py and any custom views.

**Q: Orders show NULL for location fields**
A: This is expected. Populate location data via a data migration or management command.

**Q: Friend pricing not showing**
A: Implement the pricing logic in your views/serializers using `FriendsHelper.are_friends()`.

For more help, see `friends/README.md`.
