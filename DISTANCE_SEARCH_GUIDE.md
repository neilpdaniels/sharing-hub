# Distance-Based Transaction Search & Deposit Features - Implementation Guide

## Overview

This document describes the new distance-based transaction search and deposit features added to Sharing Hub.

## New Features

### 1. Deposit Fields on Transactions

Transactions now support a two-tier deposit structure, similar to pricing:

**Fields Added to Transaction Model**:
- `deposit` - Regular deposit amount (non-friends)
- `friend_deposit` - Optional friend-only deposit amount
- `delivery_distance_km` - Maximum distance lender can deliver/travel (1-1000 km, default 10)

**Usage**:
```python
transaction = Transaction.objects.create(
    price=100.00,
    friend_price=80.00,
    deposit=50.00,              # Deposit for non-friends
    friend_deposit=30.00,       # Deposit for friends (optional)
    delivery_distance_km=25,    # Can deliver up to 25km
    ...
)

# Get appropriate deposit for user
from transaction.helpers import get_transaction_deposit_for_user
deposit = get_transaction_deposit_for_user(transaction, viewing_user)
```

### 2. Postcode-Based Location System

Replaced GPS coordinate entry with UK postcodes for simpler UX.

**Fields Added**:
- **Order Model**: `postcode` (UK postcode field, indexed for search)
- **Profile Model**: `latitude`, `longitude` (cached GPS coordinates from postcode)

**How It Works**:
1. User enters UK postcode when creating order
2. System automatically geocodes postcode to GPS coordinates using postcodes.io API
3. Coordinates cached in Profile for future use
4. Coordinates used for distance filtering and sorting

### 3. Distance-Based Search for Borrowers

Borrowers (those wanting to borrow/rent) can search transactions by:
- Postcode (for logged-in users: uses their postcode; for guests: they enter it)
- Distance radius (default 25 km, configurable)
- Direction filter (WANTED or TO LET)
- Sort by: newest, distance, price

**Access Point**: `/navigation/search_by_postcode/`

**Query Parameters**:
- `postcode` - UK postcode to search from (optional for logged-in users)
- `distance` - Maximum search distance in km (default 25)
- `sort_by` - Sort method: `newest`, `distance`, `price` (default: newest)
- `direction` - Filter by: `W` (WANTED), `L` (TO LET), or empty for both

**Example URLs**:
```
/navigation/search_by_postcode/                           # Logged-in user search
/navigation/search_by_postcode/?postcode=SM4+4NX&distance=50  # Guest search
/navigation/search_by_postcode/?sort_by=distance          # Sort by distance
```

### 4. Lender Delivery Range

Lenders can specify how far they're willing to deliver/travel via the `delivery_distance_km` field in transactions.

**How It's Used**:
- Borrower searches from their postcode with max distance (e.g., 25 km)
- Results only show transactions where: `borrower_distance <= search_distance AND borrower_distance <= lender_delivery_distance`
- Both constraints must be satisfied

## Implementation Details

### Postcode Geocoding (`common/geocoding.py`)

**PostcodeGeocoder Class**:
- Uses free postcodes.io API (no authentication required)
- Automatic caching of results (30 days)
- Fallback handling for invalid postcodes

**Methods**:
- `get_coordinates(postcode)` - Get GPS for postcode
- `calculate_distance(lat1, lon1, lat2, lon2)` - Distance using Haversine formula
- `populate_coordinates(obj)` - Auto-populate from postcode

**Example**:
```python
from common.geocoding import PostcodeGeocoder

# Get coordinates
coords = PostcodeGeocoder.get_coordinates('SW1A2AA')
# Returns: {'latitude': Decimal('51.501009'), 'longitude': Decimal('-0.141588')}

# Calculate distance between two points
distance = PostcodeGeocoder.calculate_distance(
    Decimal('51.501'), Decimal('-0.141'),
    Decimal('51.507'), Decimal('-0.128')
)
# Returns: 0.89 (km)
```

### Distance Filtering Helpers (`transaction/helpers.py`)

**New Functions**:
- `get_transaction_price_for_user()` - Returns friend or regular price
- `get_transaction_deposit_for_user()` - Returns friend or regular deposit
- `filter_transactions_by_distance()` - Filter by distance + delivery range
- `geocode_postcode_for_order()` - Geocode order's postcode

**Example**:
```python
from transaction.helpers import filter_transactions_by_distance

# Get transactions within 25km of user
nearby = filter_transactions_by_distance(
    Transaction.objects.all(),
    user_latitude=Decimal('51.5'),
    user_longitude=Decimal('-0.1'),
    max_distance_km=25
)

# Each transaction now has .distance attribute
for txn in nearby:
    print(f"{txn.order_passive.product.name} - {txn.distance}km away")
```

### Search View (`navigation/views.py`)

**`search_by_postcode` View**:
- Handles both logged-in users and guests
- Auto-geocodes user's postcode from profile
- Filters transactions by distance
- Supports sorting and filtering
- Adds pricing info (friend vs regular) to results
- Returns paginated results (20 per page)

**Features**:
- Distance caching in User Profile for faster future searches
- Proper error handling for invalid postcodes
- Support for both WANTED and TO LET transactions
- Friend pricing displayed correctly

**Context Variables in Template**:
```python
{
    'postcode': 'SM44NX',
    'max_distance': 25,
    'sort_by': 'distance',
    'direction_filter': 'W',
    'is_logged_in': True,
    'transactions': Page object,
    'total_results': 42,
    'latitude': Decimal('51.35'),
    'longitude': Decimal('-0.20'),
    'search_performed': True,
    'postcode_not_found': False,
}
```

## Database Migrations Required

```bash
# Create migrations
python manage.py makemigrations account     # Profile: latitude, longitude
python manage.py makemigrations common      # Order: postcode
python manage.py makemigrations transaction # Transaction: deposit fields

# Apply migrations
python manage.py migrate
```

### Migration Details

**account/migrations**: Add to Profile
```python
latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
```

**common/migrations**: Add to Order
```python
postcode = models.CharField(max_length=10, null=True, blank=True, db_index=True)
```

**transaction/migrations**: Add to Transaction
```python
deposit = models.FloatField(default=0)
friend_deposit = models.FloatField(null=True, blank=True)
delivery_distance_km = models.PositiveIntegerField(default=10)
```

## API Reference

### Forms

#### OrderAddForm / OrderEditForm
```python
# Now includes fields
fields = ('direction', 'quantity', 'expiry_date', 'price', 
          'description', 'postcode', 'latitude', 'longitude', 'radius_km')

# Template usage
{% bootstrap_field order_form.postcode %}
{% bootstrap_field order_form.latitude %}  
{% bootstrap_field order_form.longitude %}
{% bootstrap_field order_form.radius_km %}
```

#### TransactionCreateForm
```python
# For creating transactions with prices and deposits
fields = ('quantity', 'price', 'friend_price', 
          'deposit', 'friend_deposit', 'delivery_distance_km')
```

### Models

#### Transaction
```python
# New fields
transaction.price              # Regular price (non-friends)
transaction.friend_price       # Friend price (optional)
transaction.deposit            # Regular deposit (non-friends)
transaction.friend_deposit     # Friend deposit (optional)
transaction.delivery_distance_km  # Max delivery distance
```

#### Order
```python
# New fields
order.postcode         # UK postcode
order.latitude         # Cached latitude (auto-populated)
order.longitude        # Cached longitude (auto-populated)
```

#### Profile
```python
# New fields
profile.latitude      # Cached latitude from postcode
profile.longitude     # Cached longitude from postcode
```

## URL Routing

### New Endpoint
```
/navigation/search_by_postcode/
```

**Methods**: GET, POST

**Parameters** (GET):
- `postcode` - UK postcode (required for guests, optional for logged-in users)
- `distance` - Search distance in km (default: 25)
- `sort_by` - Sort order: `newest`, `distance`, `price` (default: newest)
- `direction` - Filter: `W` (WANTED), `L` (TO LET), or both (default: both)
- `page` - Page number for pagination (default: 1)

## Template Considerations

### New Fields in Forms
Add these bootstrap fields to transaction/templates forms:

```django
{% bootstrap_field order_form.postcode %}
{% bootstrap_field order_form.delivery_distance_km %}

{% bootstrap_field transaction_form.deposit %}
{% bootstrap_field transaction_form.friend_deposit %}
{% bootstrap_field transaction_form.delivery_distance_km %}
```

### Search Results Display
In template for search_by_postcode results:

```django
{% if search_performed %}
    {% if postcode_not_found %}
        <div class="alert alert-warning">Postcode not found</div>
    {% elif transactions %}
        <p>Found {{ total_results }} transactions within {{ max_distance }}km</p>
        
        {% for transaction in transactions %}
            <div class="transaction-result">
                <h5>{{ transaction.order_passive.product.name }}</h5>
                <p>Distance: {{ transaction.distance }}km</p>
                <p>Price: £{{ transaction.display_price }}</p>
                <p>Deposit: £{{ transaction.display_deposit }}</p>
                <p>Lender can deliver: {{ transaction.delivery_distance_km }}km</p>
            </div>
        {% endfor %}
    {% endif %}
{% endif %}
```

## Performance Notes

### Optimization Recommendations

1. **Postcode Caching**: Use Django's cache framework
   - API results cached for 30 days
   - User profile coordinates cached in database

2. **Distance Filtering**: Currently loads all transactions in Python
   - For large datasets, consider PostGIS integration
   - Index on `postcode` field in Order table

3. **User Profile Cache**: Cache user coordinates for 24 hours
   ```python
   from django.core.cache import cache
   coords = cache.get(f'user_postcode_{user.id}')
   ```

4. **Query Optimization**:
   ```python
   # Use select_related to minimize queries
   transactions = Transaction.objects.select_related(
       'order_passive', 'order_passive__product',
       'user_aggressive', 'user_passive'
   ).filter(...)
   ```

## Testing

### Unit Tests to Create

```python
# tests/test_geocoding.py
from common.geocoding import PostcodeGeocoder

def test_postcode_geocoding():
    coords = PostcodeGeocoder.get_coordinates('SW1A2AA')
    assert coords is not None
    assert 'latitude' in coords
    assert 'longitude' in coords

def test_distance_calculation():
    distance = PostcodeGeocoder.calculate_distance(
        Decimal('51.5'), Decimal('-0.1'),
        Decimal('51.5'), Decimal('-0.1')
    )
    assert distance == 0.0
```

### Integration Tests

```python
def test_distance_search():
    user = User.objects.create_user('testuser')
    user.profile.postcode = 'SW1A2AA'
    user.profile.save()
    
    response = client.get('/navigation/search_by_postcode/')
    assert response.status_code == 200
```

## Dependencies

### New External Dependency
- `requests` - For postcodes.io API calls (may already be installed)

**Installation**:
```bash
pip install requests
```

### Existing Dependencies Used
- `django` - ORM and caching
- `decimal` - For precise coordinate storage
- `math` - For Haversine distance calculation
- `django-simple-history` - Already installed

## Future Enhancements

1. **PostGIS Integration**
   - Replace Python distance filtering with database queries
   - Support for complex geographic queries
   - Significant performance improvement for large datasets

2. **Google Maps Integration**
   - Advanced mapping UI for search
   - Street view and directions
   - Requires API key

3. **Radius Search History**
   - Save favorite search areas
   - Quick access to previous searches

4. **Instant Search**
   - Live autocomplete for postcodes
   - Real-time result updates

5. **Delivery Options**
   - Schedule delivery times
   - Multiple location options per transaction

6. **Geographic Zones**
   - Pre-defined delivery zones
   - Zone-based pricing

## Troubleshooting

### Postcode Not Found
- Check postcode format (e.g., `SM4 4NX`)
- Verify it's a valid UK postcode at postcodes.io/lookup
- Check Django cache not returning stale data

### Distance Calculations Incorrect
- Verify latitude/longitude are in decimal format
- Check coordinates are cached correctly in profile
- Ensure order's postcode is valid

### Search Returns No Results
- Verify lender's `delivery_distance_km` >= borrower's distance
- Check transaction status is NEW
- Check order status is ACTIVE

## Example Usage Flow

### For Lender (Creating Transaction)
1. Create account with postcode (e.g., SW1A2AA)
2. Create order for item to lend
3. System auto-geocodes user's postcode to GPS
4. Create transaction with:
   - Price and Friend Price
   - Deposit and Friend Deposit
   - Delivery Distance (e.g., 30km)

### For Borrower (Searching)
1. **If logged in**: Go to /navigation/search_by_postcode/
   - System uses their postcode automatically
   - Set search distance (e.g., 25km)
   - Choose direction and sort order
2. **If not logged in**: 
   - Go to /navigation/search_by_postcode/
   - Enter postcode (e.g., SM4 4NX)
   - Set search distance
   - View results with distances and appropriate pricing

## Support & Questions

See main INTEGRATION_GUIDE.md for general setup instructions.

For geocoding-specific issues, check:
- postcodes.io documentation
- Django cache configuration
- Database migration status
