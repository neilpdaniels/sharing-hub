from common.models import TransactionFee, TransactionFeeBand
from transaction.models import Transaction
from django.db.models import Avg, Count, Q
import logging


def empty_feedback_breakdown():
    return {
        'completed_free_transactions': 0,
        'completed_transactions': 0,
        'completed_transactions_total': 0,
        'free_transaction_feedback_score': None,
        'completed_transaction_feedback_score': None,
        'has_free_feedback_score': False,
        'has_completed_feedback_score': False,
    }


def get_user_feedback_breakdown(*, user_id):
    from transaction.models import TransactionFeedback

    if not user_id:
        return empty_feedback_breakdown()

    feedback_qs = TransactionFeedback.objects.filter(
        left_for_id=user_id,
        transaction__transaction_status=Transaction.RENTAL_PROCESS_COMPLETED,
    )

    aggregates = feedback_qs.aggregate(
        completed_transactions_total=Count('transaction', distinct=True),
        completed_free_transactions=Count(
            'transaction',
            filter=Q(transaction__price__lte=0),
            distinct=True,
        ),
        completed_transactions=Count(
            'transaction',
            filter=Q(transaction__price__gt=0),
            distinct=True,
        ),
        free_transaction_feedback_score=Avg('overall_rating', filter=Q(transaction__price__lte=0)),
        completed_transaction_feedback_score=Avg('overall_rating', filter=Q(transaction__price__gt=0)),
    )

    breakdown = {
        'completed_free_transactions': aggregates.get('completed_free_transactions') or 0,
        'completed_transactions': aggregates.get('completed_transactions') or 0,
        'completed_transactions_total': aggregates.get('completed_transactions_total') or 0,
        'free_transaction_feedback_score': aggregates.get('free_transaction_feedback_score'),
        'completed_transaction_feedback_score': aggregates.get('completed_transaction_feedback_score'),
        'has_free_feedback_score': aggregates.get('free_transaction_feedback_score') is not None,
        'has_completed_feedback_score': aggregates.get('completed_transaction_feedback_score') is not None,
    }
    return breakdown


def get_user_feedback_breakdown_map(user_ids):
    user_ids = [uid for uid in set(user_ids or []) if uid]
    if not user_ids:
        return {}
    return {uid: get_user_feedback_breakdown(user_id=uid) for uid in user_ids}

def getMinPriceByWeight(fee_bands, total_weight):
    toReturn = 0
    for band in fee_bands:
        if total_weight <= band.max_weight:
            toReturn = band.price
    return toReturn
    
def getMinPriceByValue(fee_bands, total_value):
    toReturn = 0
    for band in fee_bands:
        if total_value <= band.max_price:
            toReturn = band.price
    return toReturn
    
# def checkFee(fee, qty, unit_price, expected_value, order):
#     toReturn = False
#     fee_bands = fee.transactionfeeband_set.all().order_by('-price')
#     if len(fee_bands) == 1:
#         if fee.fee_type == TransactionFee.FLAT:
#             if fee_bands[0].price_style == TransactionFeeBand.ABSOLUTE:
#                 if float(expected_value) == float(fee_bands[0].price):
#                     toReturn = True
#             elif fee_bands[0].price_style == TransactionFeeBand.PERCENTAGE:
#                 calculated_fee = round((fee_bands[0].price / 100) * ( qty * unit_price),2)
#                 if float(expected_value) == calculated_fee:
#                     toReturn = True
#         # elif fee.fee_type = TransactionFee.
#     elif len(fee_bands) > 1:
#         if fee.fee_type == TransactionFee.WEIGHT_AND_VALUE:
#             fee_value = getMinPriceByValue(fee_bands, round(qty * unit_price, 2))
#             fee_weight = getMinPriceByValue(fee_bands, (qty * order.product.weight))
#             if fee_value < fee_weight:
#                 if float(expected_value) == fee_weight:
#                     toReturn = True
#             else:
#                 if float(expected_value) == fee_value:
#                     toReturn = True

#     if (qty * unit_price) > 2500 and fee.slug == 'royal_mail_special_delivery_pre_1pm':
#         if qty > 1:
#             # same unit price
#             max_number_in_package = int (2500 / unit_price)
#             totalPackagePrice = 0
#             totalPacked = 0
#             while qty > totalPacked:
#                 if qty - totalPacked < max_number_in_package:
#                     packed_this_time = qty - totalPacked
#                 else:
#                     packed_this_time = max_number_in_package

#                 additional_cost = returnFeeValue(fee, packed_this_time, unit_price, order)
#                 totalPacked = totalPacked + packed_this_time
#                 totalPackagePrice = totalPackagePrice + additional_cost
#         toReturn = totalPackagePrice

#     return toReturn
    
 
def returnFeeValue(fee, qty, unit_price, order):
    toReturn = False
    fee_bands = fee.transactionfeeband_set.all().order_by('-price')
    if len(fee_bands) == 1:
        if fee.fee_type == TransactionFee.FLAT:
            if fee_bands[0].price_style == TransactionFeeBand.ABSOLUTE:
                toReturn = fee_bands[0].price
            elif fee_bands[0].price_style == TransactionFeeBand.PERCENTAGE:
                calculated_fee = round((fee_bands[0].price / 100) * ( qty * unit_price),2)
                toReturn = calculated_fee
        # elif fee.fee_type = TransactionFee.
    elif len(fee_bands) > 1:
        if fee.fee_type == TransactionFee.WEIGHT_AND_VALUE:
            fee_value = getMinPriceByValue(fee_bands, round(qty * unit_price, 2))
            fee_weight = getMinPriceByValue(fee_bands, (qty * order.product.weight))
            if fee_value < fee_weight:
                toReturn = fee_weight
            else:
                toReturn = fee_value
        elif fee.fee_type == TransactionFee.VALUE:
            toReturn = getMinPriceByValue(fee_bands, round(qty * unit_price, 2))
            

    if (qty * unit_price) > 2500 and fee.slug == 'royal_mail_special_delivery_pre_1pm':
        if qty > 1:
            # same unit price
            max_number_in_package = int (2500 / unit_price)
            totalPackagePrice = 0
            totalPacked = 0
            while qty > totalPacked:
                if qty - totalPacked < max_number_in_package:
                    packed_this_time = qty - totalPacked
                else:
                    packed_this_time = max_number_in_package

                additional_cost = returnFeeValue(fee, packed_this_time, unit_price, order)
                totalPacked = totalPacked + packed_this_time
                totalPackagePrice = totalPackagePrice + additional_cost
            toReturn = totalPackagePrice

    return toReturn

def getTransactionStepAndAction(txn, request):
    step = 1
    next_action = False
    is_lender = (txn.user_passive == request.user)
    is_renter = (txn.user_aggressive == request.user)

    if txn.transaction_status == txn.RENTAL_ENQUIRY:
        step = 1
        next_action = is_lender
    elif txn.transaction_status == txn.RENTAL_AGREED:
        lender_done = bool(txn.lender_agreed_at)
        renter_done = bool(txn.renter_agreed_at)

        if not lender_done and not renter_done:
            # Both parties can confirm in parallel
            step = 2
            next_action = (is_lender or is_renter)
        elif lender_done ^ renter_done:
            # One side confirmed; waiting on the other
            step = 3
            next_action = (is_lender and not lender_done) or (is_renter and not renter_done)
        else:
            # Both confirmed, ready for initiation
            step = 4
            next_action = is_lender
    elif txn.transaction_status in (txn.RENTAL_DAY_AWAITING_VERIFICATION, txn.RENTAL_ONGOING, txn.RENTAL_RETURN_DAY_AWAITING_VERIFICATION):
        step = 5
        next_action = True
    elif txn.transaction_status in (txn.RENTAL_RETURNED_DEPOSIT_PENDING, txn.RENTAL_RETURNED_DEPOSIT_RETURNED, txn.RENTAL_RETURNED_DEPOSIT_CONTESTED):
        step = 6
        next_action = is_lender
    elif txn.transaction_status in (txn.AWAITING_FEEDBACK, txn.RENTAL_PROCESS_COMPLETED):
        step = 7
        next_action = False
    elif txn.transaction_status in (txn.MEDIATION_REQUIRED, txn.DISPUTE_REQUESTED):
        step = 7
        next_action = False

    return step, next_action


# Distance-based filtering helpers

def get_transaction_price_for_user(transaction, viewing_user):
    """
    Get the appropriate price for a transaction based on friendship.
    
    Args:
        transaction: Transaction object
        viewing_user: User viewing the transaction
        
    Returns:
        Float: Price as regular or friend price
    """
    from friends.models import FriendsHelper
    
    if FriendsHelper.are_friends(transaction.user_aggressive, viewing_user):
        return transaction.friend_price if transaction.friend_price else transaction.price
    return transaction.price


def get_transaction_deposit_for_user(transaction, viewing_user):
    """
    Get the appropriate deposit for a transaction based on friendship.
    
    Args:
        transaction: Transaction object
        viewing_user: User viewing the transaction
        
    Returns:
        Float: Deposit as regular or friend deposit
    """
    from friends.models import FriendsHelper
    
    if FriendsHelper.are_friends(transaction.user_aggressive, viewing_user):
        return transaction.friend_deposit if transaction.friend_deposit else transaction.deposit
    return transaction.deposit


def filter_transactions_by_distance(transactions, user_latitude, user_longitude, max_distance_km):
    """
    Filter transactions to only include those within a maximum distance.
    
    Args:
        transactions: QuerySet or list of transactions
        user_latitude: User's latitude (Decimal)
        user_longitude: User's longitude (Decimal)
        max_distance_km: Maximum distance in km
        
    Returns:
        List of transactions with distance attribute, sorted by distance
    """
    from common.geocoding import PostcodeGeocoder
    
    transactions_with_distance = []
    
    for txn in transactions:
        order = txn.order_passive or txn.order_aggressive
        
        if order and order.latitude and order.longitude:
            distance = PostcodeGeocoder.calculate_distance(
                user_latitude, user_longitude,
                order.latitude, order.longitude
            )
            
            # Check if within user's search distance AND within transaction's delivery range
            if distance <= max_distance_km and distance <= order.radius_km:
                txn.distance = distance
                transactions_with_distance.append(txn)
    
    # Sort by distance (closest first)
    return sorted(transactions_with_distance, key=lambda x: x.distance)


def geocode_postcode_for_order(order):
    """
    Geocode postcode for an order if not already geocoded.
    
    Args:
        order: Order object with postcode field
        
    Returns:
        Boolean indicating if geocoding was successful
    """
    from common.geocoding import PostcodeGeocoder
    
    if order.postcode and (not order.latitude or not order.longitude):
        coords = PostcodeGeocoder.get_coordinates(order.postcode)
        if coords:
            order.latitude = coords['latitude']
            order.longitude = coords['longitude']
            return True
    return False
