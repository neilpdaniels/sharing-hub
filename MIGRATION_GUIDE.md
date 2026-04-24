# Data Migration Guide: Transaction Type Changes (BUY→WANTED, SELL→TO LET)

## Overview

The transaction types have been renamed:
- `BUY` (character code 'B') → `WANTED` (character code 'W')
- `SELL` (character code 'S') → `TO LET` (character code 'L')

This guide explains how to migrate existing data.

## Migration Steps

### Step 1: Create the Data Migration

```bash
cd /home/neil/Projects/sharing-hub
python manage.py makemigrations common --empty --name migrate_order_direction_codes
```

### Step 2: Edit the Migration File

Edit the newly created migration file in `common/migrations/`. It will be something like `xxxx_migrate_order_direction_codes.py`.

Replace its contents with:

```python
from django.db import migrations

def migrate_order_directions_forward(apps, schema_editor):
    """Update order direction codes from BUY/SELL to WANTED/TO LET"""
    Order = apps.get_model('common', 'Order')
    
    # Update BUY → WANTED
    updated_buy = Order.objects.filter(direction='B').update(direction='W')
    print(f"Migrated {updated_buy} orders from BUY to WANTED")
    
    # Update SELL → TO LET
    updated_sell = Order.objects.filter(direction='S').update(direction='L')
    print(f"Migrated {updated_sell} orders from SELL to TO LET")

def migrate_order_directions_reverse(apps, schema_editor):
    """Reverse: Update order direction codes from WANTED/TO LET back to BUY/SELL"""
    Order = apps.get_model('common', 'Order')
    
    # Update WANTED → BUY
    updated_wanted = Order.objects.filter(direction='W').update(direction='B')
    print(f"Reversed {updated_wanted} orders from WANTED to BUY")
    
    # Update TO LET → SELL
    updated_to_let = Order.objects.filter(direction='L').update(direction='S')
    print(f"Reversed {updated_to_let} orders from TO LET to SELL")

class Migration(migrations.Migration):

    dependencies = [
        ('common', 'latest_migration_before_this'),  # UPDATE THIS LINE
    ]

    operations = [
        migrations.RunPython(
            migrate_order_directions_forward,
            migrate_order_directions_reverse
        ),
    ]
```

**IMPORTANT**: Update the `dependencies` line to reference the latest migration before this one. You can find this by looking at other migrations in `common/migrations/`.

### Step 3: Apply the Migration

```bash
python manage.py migrate common
```

You should see output like:
```
Running migrations:
  Applying common.xxxx_migrate_order_direction_codes... OK
```

### Step 4: Verify the Migration

Check that data was migrated correctly:

```bash
python manage.py shell
```

Then in the shell:

```python
from common.models import Order

# Check counts
wanted_count = Order.objects.filter(direction='W').count()
to_let_count = Order.objects.filter(direction='L').count()
old_buy = Order.objects.filter(direction='B').count()
old_sell = Order.objects.filter(direction='S').count()

print(f"WANTED: {wanted_count}, TO_LET: {to_let_count}")
print(f"Old BUY: {old_buy}, Old SELL: {old_sell}")

# There should be no BUY or SELL left
assert old_buy == 0, "Some BUY orders still exist!"
assert old_sell == 0, "Some SELL orders still exist!"
print("✓ Migration successful!")
```

## Rollback Procedure

If you need to rollback this migration:

```bash
# Go back one migration
python manage.py migrate common 0xxx  # where 0xxx is the migration before this one

# Or unapply all to common app migrations
python manage.py migrate common zero
```

## Display Names in Templates & Admin

The display names have been automatically updated in the model:

```python
DIRECTION_CHOICES = (
    (WANTED, 'Wanted'),  # Was 'Buy'
    (TO_LET, 'To Let')   # Was 'Sell'
)
```

No template changes needed unless you hardcoded BUY/SELL strings.

## Database Reference

If you need to know what direction codes mean after migration:

| Code | Meaning    | Previous |
|------|-----------|----------|
| W    | Wanted    | B (Buy)  |
| L    | To Let    | S (Sell) |

## Checking Transaction Direction in Code

After migration, update code references:

```python
# Before
if order.direction == Order.BUY:
    # action for buyer

# After
if order.direction == Order.WANTED:
    # action for someone wanting something

# Before
if order.direction == Order.SELL:
    # action for seller

# After
if order.direction == Order.TO_LET:
    # action for someone offering something
```

## Search & Replace for Code Updates

In your IDE, use Find & Replace (with regex):

1. Find: `Order\.BUY` → Replace: `Order.WANTED`
2. Find: `Order\.SELL` → Replace: `Order.TO_LET`
3. Find: `'B'` (in direction context) → Replace: `'W'`
4. Find: `'S'` (in direction context) → Replace: `'L'`

## Template Updates

If templates reference these hardcoded strings:

```django
<!-- Before -->
{% if order.direction == 'B' %}
    <span>Buying</span>
{% endif %}

<!-- After -->
{% if order.direction == 'W' %}
    <span>Wanted</span>
{% endif %}
```

Or better yet, use the `get_direction_display()` method:

```django
<span>{{ order.get_direction_display }}</span>
<!-- Displays: "Wanted" or "To Let" -->
```

## Test Updates

Update any tests that reference the old codes:

```python
# Before
order = Order.objects.create(direction=Order.BUY, ...)

# After
order = Order.objects.create(direction=Order.WANTED, ...)
```

## Admin Filter Updates

If you have custom admin filters referencing old codes, update them:

```python
# Before
list_filter = ('direction',)  # Shows old B/S values

# After (automatic in Django admin)
list_filter = ('direction',)  # Shows new W/L values with display names
```

## Logs & Monitoring

After migration, monitor for any errors:

```bash
# Check Django logs
tail -f logs/django.log | grep -i "order\|direction"

# Test a transaction workflow
python manage.py shell
from common.models import Order
order = Order.objects.first()
print(f"Direction: {order.direction} -> {order.get_direction_display()}")
```

## Performance Notes

The migration uses `update()` which is efficient:
- No model instances are loaded into memory
- Direct SQL UPDATE statements are executed
- Typical execution time: <1 second for most databases

For millions of records, it may take longer but still completes quickly.

## FAQ

**Q: Will this migration break existing transactions?**
A: No. The migration only updates the `direction` field in Order records. Transactions that reference these orders will still work correctly.

**Q: Is there a backup option?**
A: Yes, always backup your database before migrations:
```bash
python manage.py dumpdata > backup_before_migration.json
```

**Q: How do I test the migration safely?**
A: Do it on a development database first, or in a staging environment separate from production.

**Q: Will users see any changes?**
A: They'll see the new display names ("Wanted" instead of "Buy", "To Let" instead of "Sell"). The database codes are invisible to users.

**Q: What if something goes wrong?**
A: Rollback using `python manage.py migrate common <previous_migration>` then restore from backup if needed.
