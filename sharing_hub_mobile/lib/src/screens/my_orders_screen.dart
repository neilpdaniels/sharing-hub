import 'package:flutter/material.dart';

import '../models/order_models.dart';
import '../theme.dart';

typedef AmendOrderCallback =
    Future<void> Function(OrderSummary order, Map<String, dynamic> fields);
typedef CancelOrderCallback = Future<void> Function(OrderSummary order);

class MyOrdersScreen extends StatelessWidget {
  const MyOrdersScreen({
    super.key,
    required this.orders,
    required this.loading,
    required this.onRefresh,
    required this.onListMyItem,
    required this.onAmendOrder,
    required this.onCancelOrder,
  });

  final List<OrderSummary> orders;
  final bool loading;
  final Future<void> Function() onRefresh;
  final VoidCallback onListMyItem;
  final AmendOrderCallback onAmendOrder;
  final CancelOrderCallback onCancelOrder;

  static const _availabilityMarker = '[AVAILABILITY_DAYS]';
  static const _weekdayLabels = <int, String>{
    1: 'Mon',
    2: 'Tue',
    3: 'Wed',
    4: 'Thu',
    5: 'Fri',
    6: 'Sat',
    7: 'Sun',
  };

  Set<int> _extractAvailabilityDays(String value) {
    final markerLine = value
        .split('\n')
        .firstWhere(
          (line) => line.trimLeft().startsWith(_availabilityMarker),
          orElse: () => '',
        )
        .trim();

    if (markerLine.isEmpty) {
      return {1, 2, 3, 4, 5, 6, 7};
    }

    final rawDays = markerLine
        .replaceFirst(_availabilityMarker, '')
        .trim()
        .split(',')
        .map((part) => part.trim().toLowerCase())
        .where((part) => part.isNotEmpty)
        .toList(growable: false);

    if (rawDays.isEmpty) {
      return {1, 2, 3, 4, 5, 6, 7};
    }

    final result = <int>{};
    for (final entry in _weekdayLabels.entries) {
      if (rawDays.contains(entry.value.toLowerCase())) {
        result.add(entry.key);
      }
    }

    return result.isEmpty ? {1, 2, 3, 4, 5, 6, 7} : result;
  }

  String _stripAvailabilityMarker(String value) {
    return value
        .split('\n')
        .where((line) => !line.trimLeft().startsWith(_availabilityMarker))
        .join('\n')
        .trim();
  }

  String _mergeCollectionDetailsAvailability(
    String details,
    Set<int> availableWeekdays,
  ) {
    final cleaned = _stripAvailabilityMarker(details);
    final days = availableWeekdays.toList()..sort();
    if (days.length == 7) {
      return cleaned;
    }

    final dayLabels = days
        .map((day) => _weekdayLabels[day] ?? '')
        .where((label) => label.isNotEmpty)
        .join(', ');
    final availabilityLine = '$_availabilityMarker $dayLabels';

    if (cleaned.isEmpty) {
      return availabilityLine;
    }
    return '$cleaned\n$availabilityLine';
  }

  @override
  Widget build(BuildContext context) {
    final gradientColors = sharingHubBackgroundGradient(
      Theme.of(context).brightness,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('My Listings')),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: gradientColors,
          ),
        ),
        child: RefreshIndicator(
          onRefresh: onRefresh,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              FilledButton.icon(
                onPressed: onListMyItem,
                icon: const Icon(Icons.add_business_outlined),
                label: const Text('List my item'),
              ),
              const SizedBox(height: 16),
              if (loading)
                const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (orders.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No active listings.'),
                  ),
                )
              else
                ...orders.map((order) => _orderCard(context, order)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _orderCard(BuildContext context, OrderSummary order) {
    final thumbUrl = order.listingImageUrl.isNotEmpty
        ? order.listingImageUrl
        : (order.listingImageUrls.isNotEmpty
              ? order.listingImageUrls.first
              : '');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: thumbUrl.isEmpty
                      ? Container(
                          width: 72,
                          height: 72,
                          color: const Color(0x11000000),
                          child: const Icon(Icons.inventory_2_outlined),
                        )
                      : Image.network(
                          thumbUrl,
                          width: 72,
                          height: 72,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) =>
                              Container(
                                width: 72,
                                height: 72,
                                color: const Color(0x11000000),
                                child: const Icon(Icons.broken_image_outlined),
                              ),
                        ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        order.productName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 4),
                      Text('Listing status: ${order.status}'),
                      Text(
                        '${order.currencySymbol}${order.price.toStringAsFixed(2)}',
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            if (order.expiryDate != null)
              Text('Expires: ${order.expiryDate!.toLocal()}'.split('.').first),
            const SizedBox(height: 8),
            Row(
              children: [
                OutlinedButton(
                  onPressed: () => _showAmendDialog(context, order),
                  child: const Text('Edit listing'),
                ),
                const SizedBox(width: 8),
                OutlinedButton(
                  onPressed: () async {
                    final shouldCancel = await showDialog<bool>(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: const Text('Cancel Listing'),
                        content: const Text(
                          'Are you sure you want to cancel this listing?',
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.of(context).pop(false),
                            child: const Text('No'),
                          ),
                          TextButton(
                            onPressed: () => Navigator.of(context).pop(true),
                            child: const Text('Yes, cancel'),
                          ),
                        ],
                      ),
                    );
                    if (shouldCancel == true) {
                      await onCancelOrder(order);
                    }
                  },
                  child: const Text('Cancel'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showAmendDialog(
    BuildContext context,
    OrderSummary order,
  ) async {
    final priceController = TextEditingController(
      text: order.price.toStringAsFixed(2),
    );
    final descriptionController = TextEditingController(
      text: order.description,
    );
    final additionalCommentsController = TextEditingController(
      text: order.additionalComments,
    );
    final postcodeController = TextEditingController(text: order.postcode);
    final radiusController = TextEditingController(
      text: order.radiusKm.toString(),
    );
    final depositController = TextEditingController(
      text: order.deposit > 0 ? order.deposit.toStringAsFixed(2) : '',
    );
    final matesRatesController = TextEditingController(
      text: order.matesRates > 0 ? order.matesRates.toStringAsFixed(2) : '',
    );
    final matesDepositController = TextEditingController(
      text: order.matesDeposit > 0 ? order.matesDeposit.toStringAsFixed(2) : '',
    );
    final deliveryCostController = TextEditingController(
      text: order.deliveryCost > 0 ? order.deliveryCost.toStringAsFixed(2) : '',
    );
    final deliveryWithinKmController = TextEditingController(
      text: order.deliveryWithinKm?.toString() ?? '',
    );
    final deliveryCostPerKmController = TextEditingController(
      text: order.deliveryCostPerKm?.toStringAsFixed(2) ?? '',
    );
    final collectionDetailsController = TextEditingController(
      text: _stripAvailabilityMarker(order.collectionDetails),
    );
    final maxRentalDaysController = TextEditingController(
      text: order.maxRentalDays > 0 ? order.maxRentalDays.toString() : '7',
    );

    var letVisibility = order.letVisibility.isEmpty
        ? 'BOTH'
        : order.letVisibility;
    var collectionPolicy = order.collectionPolicy.isEmpty
        ? 'MC'
        : order.collectionPolicy;
    var availableWeekdays = _extractAvailabilityDays(order.collectionDetails);

    await showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setStateDialog) {
            return AlertDialog(
              title: const Text('Edit listing'),
              content: SizedBox(
                width: 520,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      TextField(
                        controller: priceController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Price per day',
                        ),
                      ),
                      const SizedBox(height: 8),
                      DropdownButtonFormField<String>(
                        initialValue: letVisibility,
                        decoration: const InputDecoration(
                          labelText: 'Visibility',
                        ),
                        items: const [
                          DropdownMenuItem(
                            value: 'BOTH',
                            child: Text('Friends and public'),
                          ),
                          DropdownMenuItem(
                            value: 'FRIENDS',
                            child: Text('Friends only'),
                          ),
                          DropdownMenuItem(
                            value: 'PUBLIC',
                            child: Text('Public only'),
                          ),
                        ],
                        onChanged: (value) {
                          if (value != null) {
                            letVisibility = value;
                          }
                        },
                      ),
                      const SizedBox(height: 8),
                      DropdownButtonFormField<String>(
                        initialValue: collectionPolicy,
                        decoration: const InputDecoration(
                          labelText: 'Collection / delivery',
                        ),
                        items: const [
                          DropdownMenuItem(
                            value: 'MC',
                            child: Text('You must collect'),
                          ),
                          DropdownMenuItem(
                            value: 'WD',
                            child: Text('Lender will deliver'),
                          ),
                          DropdownMenuItem(
                            value: 'EI',
                            child: Text(
                              'Collection or delivery - to be discussed',
                            ),
                          ),
                        ],
                        onChanged: (value) {
                          if (value != null) {
                            collectionPolicy = value;
                          }
                        },
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: postcodeController,
                        decoration: const InputDecoration(
                          labelText: 'Postcode',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: radiusController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Maximum let radius (km)',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: depositController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(labelText: 'Deposit'),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: matesRatesController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Mates rates (per day)',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: matesDepositController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Mates deposit',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: deliveryWithinKmController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Deliver up to (km)',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: deliveryCostPerKmController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Delivery cost per km',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: deliveryCostController,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Flat delivery fee',
                        ),
                      ),
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: Text(
                          'Weekday availability',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _weekdayLabels.entries
                            .map((entry) {
                              final selected = availableWeekdays.contains(
                                entry.key,
                              );
                              return FilterChip(
                                label: Text(entry.value),
                                selected: selected,
                                onSelected: (value) {
                                  setStateDialog(() {
                                    if (value) {
                                      availableWeekdays.add(entry.key);
                                    } else {
                                      availableWeekdays.remove(entry.key);
                                    }
                                  });
                                },
                              );
                            })
                            .toList(growable: false),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: collectionDetailsController,
                        decoration: const InputDecoration(
                          labelText: 'Collection details',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: maxRentalDaysController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Max rental days',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: descriptionController,
                        maxLines: 3,
                        decoration: const InputDecoration(
                          labelText: 'Description',
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: additionalCommentsController,
                        maxLines: 3,
                        decoration: const InputDecoration(
                          labelText: 'Additional comments',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () async {
                    final fields = <String, dynamic>{};
                    final price = double.tryParse(priceController.text.trim());
                    if (price != null) {
                      fields['price'] = price;
                    }
                    final radius = int.tryParse(radiusController.text.trim());
                    if (radius != null) {
                      fields['radius_km'] = radius;
                    }
                    final deposit = double.tryParse(
                      depositController.text.trim(),
                    );
                    if (deposit != null) {
                      fields['deposit'] = deposit;
                    }
                    final matesRates = double.tryParse(
                      matesRatesController.text.trim(),
                    );
                    if (matesRates != null) {
                      fields['mates_rates'] = matesRates;
                    }
                    final matesDeposit = double.tryParse(
                      matesDepositController.text.trim(),
                    );
                    if (matesDeposit != null) {
                      fields['mates_deposit'] = matesDeposit;
                    }
                    final deliveryCost = double.tryParse(
                      deliveryCostController.text.trim(),
                    );
                    if (deliveryCost != null) {
                      fields['delivery_cost'] = deliveryCost;
                    }
                    final deliveryWithinKm = int.tryParse(
                      deliveryWithinKmController.text.trim(),
                    );
                    if (deliveryWithinKm != null) {
                      fields['delivery_within_km'] = deliveryWithinKm;
                    }
                    final deliveryCostPerKm = double.tryParse(
                      deliveryCostPerKmController.text.trim(),
                    );
                    if (deliveryCostPerKm != null) {
                      fields['delivery_cost_per_km'] = deliveryCostPerKm;
                    }
                    final maxRentalDays = int.tryParse(
                      maxRentalDaysController.text.trim(),
                    );
                    if (maxRentalDays != null) {
                      fields['max_rental_days'] = maxRentalDays;
                    }

                    fields['let_visibility'] = letVisibility;
                    fields['collection_policy'] = collectionPolicy;
                    fields['description'] = descriptionController.text.trim();
                    fields['additional_comments'] = additionalCommentsController
                        .text
                        .trim();
                    fields['postcode'] = postcodeController.text.trim();
                    fields['collection_details'] =
                        _mergeCollectionDetailsAvailability(
                          collectionDetailsController.text.trim(),
                          availableWeekdays,
                        );
                    await onAmendOrder(order, fields);
                    if (context.mounted) {
                      Navigator.of(context).pop();
                    }
                  },
                  child: const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );
  }
}
