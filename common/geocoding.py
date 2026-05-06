"""
Geocoding utilities for converting UK postcodes and town/place names to GPS coordinates.

Uses the free postcodes.io API for UK postcode lookups.
Uses the free Nominatim (OpenStreetMap) API for town/place lookups.
Results are cached to minimize API calls.
"""

import re
import requests
import logging
from decimal import Decimal
from typing import Optional, Dict, Tuple
from django.core.cache import cache
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)

# Using the free postcodes.io API - no authentication required
POSTCODE_API_URL = 'https://api.postcodes.io/postcodes'
POSTCODE_CACHE_TIMEOUT = 86400 * 30  # Cache for 30 days

# Using OpenStreetMap Nominatim - free, no auth, be respectful (1 req/sec)
NOMINATIM_API_URL = 'https://nominatim.openstreetmap.org/search'
NOMINATIM_CACHE_TIMEOUT = 86400 * 7  # Cache for 7 days

# UK postcode pattern (e.g. SW1A 2AA, sw1a2aa, N1, etc.)
UK_POSTCODE_RE = re.compile(
    r'^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$'
    r'|^[A-Z]{1,2}[0-9][0-9A-Z]?$',  # partial/outward-only postcodes
    re.IGNORECASE
)

# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371


def is_postcode(location: str) -> bool:
    """Return True if the string looks like a UK postcode."""
    return bool(UK_POSTCODE_RE.match(location.strip()))


class PostcodeGeocoder:
    """Handles UK postcode to GPS coordinate conversion."""

    @staticmethod
    def geocode_location(location: str) -> Optional[Dict]:
        """
        Geocode an arbitrary location string — postcode or town name.

        Tries postcodes.io first if the string looks like a postcode,
        otherwise falls back to Nominatim.

        Returns:
            Dict with 'latitude', 'longitude' (Decimal) and 'display_name' (str),
            or None if not found.
        """
        if not location:
            return None
        location = location.strip()
        if is_postcode(location):
            coords = PostcodeGeocoder.get_coordinates(location)
            if coords:
                coords['display_name'] = location.upper()
            return coords
        return PostcodeGeocoder.geocode_town(location)

    @staticmethod
    def geocode_town(town: str) -> Optional[Dict]:
        """
        Geocode a town or place name using Nominatim (OpenStreetMap).

        Args:
            town: Town or place name, optionally including country

        Returns:
            Dict with 'latitude', 'longitude' (Decimal) and 'display_name' (str),
            or None if not found.
        """
        if not town:
            return None

        cache_key = f'town_coords_{town.lower().replace(" ", "_")}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached or None  # cached False-y value means not found

        try:
            response = requests.get(
                NOMINATIM_API_URL,
                params={
                    'q': town,
                    'countrycodes': 'gb',  # Restrict to UK
                    'format': 'json',
                    'limit': 1,
                },
                headers={'User-Agent': 'SharingHub/1.0'},
                timeout=5,
            )
            if response.status_code == 200:
                results = response.json()
                if results:
                    r = results[0]
                    result = {
                        'latitude': Decimal(str(r['lat'])),
                        'longitude': Decimal(str(r['lon'])),
                        'display_name': r.get('display_name', town).split(',')[0],
                    }
                    cache.set(cache_key, result, NOMINATIM_CACHE_TIMEOUT)
                    return result
            # Not found — cache negative to avoid repeated calls
            cache.set(cache_key, False, NOMINATIM_CACHE_TIMEOUT)
        except requests.RequestException as e:
            logger.error(f"Nominatim request error for '{town}': {e}")
        except Exception as e:
            logger.error(f"Error geocoding town '{town}': {e}")

        return None

    @staticmethod
    def get_coordinates(postcode: str) -> Optional[Dict[str, Decimal]]:
        """
        Get GPS coordinates for a UK postcode.
        
        Checks cache first, then PostGIS database, then API.
        
        Args:
            postcode: UK postcode (will be normalized)
            
        Returns:
            Dict with 'latitude' and 'longitude' as Decimal, or None if not found
        """
        if not postcode:
            return None
            
        # Normalize postcode (remove spaces, uppercase)
        normalized_postcode = postcode.strip().upper().replace(' ', '')
        
        # Try cache first
        cache_key = f'postcode_coords_v2_{normalized_postcode}'
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"Postcode {postcode} found in cache")
            return cached
        
        # Try API
        try:
            result = PostcodeGeocoder._query_api(normalized_postcode)
            if result:
                # Cache the result
                cache.set(cache_key, result, POSTCODE_CACHE_TIMEOUT)
                logger.info(f"Postcode {postcode} geocoded successfully")
                return result
            else:
                # Cache negative result too
                cache.set(cache_key, None, POSTCODE_CACHE_TIMEOUT)
                logger.warning(f"Postcode {postcode} not found in API")
                return None
        except Exception as e:
            logger.error(f"Error geocoding postcode {postcode}: {str(e)}")
            return None
    
    @staticmethod
    def _query_api(postcode: str) -> Optional[Dict[str, Decimal]]:
        """
        Query the postcodes.io API for postcode coordinates.
        
        Args:
            postcode: Normalized UK postcode
            
        Returns:
            Dict with latitude/longitude or None
        """
        try:
            response = requests.get(
                f'{POSTCODE_API_URL}/{postcode}',
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 200 and data.get('result'):
                    result = data['result']
                    return {
                        'latitude': Decimal(str(result['latitude'])),
                        'longitude': Decimal(str(result['longitude'])),
                        'display_name': (
                            result.get('parish')
                            or result.get('admin_ward')
                            or result.get('bua')
                            or result.get('admin_district')
                            or result.get('region')
                            or postcode
                        ),
                    }
            elif response.status_code == 404:
                logger.warning(f"Postcode {postcode} not found in postcodes.io")
            else:
                logger.warning(f"Unexpected status {response.status_code} from postcodes.io")
                
        except requests.RequestException as e:
            logger.error(f"Request error querying postcodes.io: {str(e)}")
        except ValueError as e:
            logger.error(f"JSON parsing error from postcodes.io: {str(e)}")
        
        return None
    
    @staticmethod
    def calculate_distance(lat1: Decimal, lon1: Decimal, 
                          lat2: Decimal, lon2: Decimal) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.
        
        Args:
            lat1, lon1: First coordinate (Decimal)
            lat2, lon2: Second coordinate (Decimal)
            
        Returns:
            Distance in kilometers
        """
        # Convert to float for calculation
        lat1, lon1 = float(lat1), float(lon1)
        lat2, lon2 = float(lat2), float(lon2)
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        km = EARTH_RADIUS_KM * c
        
        return round(km, 2)
    
    @staticmethod
    def populate_coordinates(obj, postcode_field='postcode', 
                            latitude_field='latitude', 
                            longitude_field='longitude'):
        """
        Populate latitude/longitude fields from postcode.
        
        Useful for saving model instances - call before save().
        
        Args:
            obj: Model instance with postcode field
            postcode_field: Name of postcode field
            latitude_field: Name of latitude field to populate
            longitude_field: Name of longitude field to populate
        """
        postcode = getattr(obj, postcode_field, None)
        
        if postcode:
            coords = PostcodeGeocoder.get_coordinates(postcode)
            if coords:
                setattr(obj, latitude_field, coords['latitude'])
                setattr(obj, longitude_field, coords['longitude'])
                logger.debug(f"Populated coordinates for {postcode}")
            else:
                logger.warning(f"Could not geocode postcode {postcode}")


    @staticmethod
    def get_nearby_user_ids(user_lat, user_lon, max_distance_km, user_postcode=None):
        """
        Return the set of User IDs whose stored profile location is within
        *max_distance_km* km of (user_lat, user_lon).

        When max_distance_km == 0 the comparison is postcode-area only:
        users whose outward code (first 3 chars of stripped postcode) matches
        user_postcode are included.

        Args:
            user_lat: Latitude of the reference point (float).
            user_lon: Longitude of the reference point (float).
            max_distance_km: Radius in km.  0 means postcode-area match only.
            user_postcode: Normalised postcode of reference user (str or None).
                           Required when max_distance_km == 0.

        Returns:
            set of int — user IDs within the radius.
        """
        from django.contrib.auth import get_user_model
        _User = get_user_model()
        nearby = set()
        for u in _User.objects.filter(
            profile__latitude__isnull=False,
            profile__longitude__isnull=False,
        ).select_related('profile'):
            try:
                dist = PostcodeGeocoder.calculate_distance(
                    user_lat, user_lon,
                    float(u.profile.latitude),
                    float(u.profile.longitude),
                )
                if max_distance_km == 0:
                    ref = (user_postcode or '').upper().replace(' ', '')[:3]
                    if (u.profile.postcode or '').upper().replace(' ', '')[:3] == ref:
                        nearby.add(u.id)
                elif dist <= max_distance_km:
                    nearby.add(u.id)
            except Exception:
                pass
        return nearby


class DistanceFilter:
    """Utilities for filtering objects by distance."""
    
    @staticmethod
    def get_nearby_queryset(queryset, user_latitude: Decimal, user_longitude: Decimal,
                           max_distance_km: int, 
                           latitude_field='latitude',
                           longitude_field='longitude'):
        """
        Filter queryset to only include items within a certain distance.
        
        WARNING: This loads all items and filters in Python (not database).
        For large datasets, use PostGIS instead.
        
        Args:
            queryset: QuerySet to filter
            user_latitude: User's latitude
            user_longitude: User's longitude  
            max_distance_km: Maximum distance in km
            latitude_field: Name of latitude field on model
            longitude_field: Name of longitude field on model
            
        Returns:
            Filtered list of objects with 'distance' attribute
        """
        nearby = []
        
        for obj in queryset:
            lat = getattr(obj, latitude_field, None)
            lon = getattr(obj, longitude_field, None)
            
            if lat and lon:
                distance = PostcodeGeocoder.calculate_distance(
                    user_latitude, user_longitude,
                    lat, lon
                )
                
                if distance <= max_distance_km:
                    obj.distance = distance
                    nearby.append(obj)
        
        return nearby
    
    @staticmethod
    def sort_by_distance(objects_with_distance):
        """
        Sort list of objects (with distance attribute) by distance.
        
        Args:
            objects_with_distance: List of objects with 'distance' attribute
            
        Returns:
            Sorted list (closest first)
        """
        return sorted(objects_with_distance, key=lambda x: getattr(x, 'distance', float('inf')))
