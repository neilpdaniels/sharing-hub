import 'package:flutter/material.dart';

import '../models/order_models.dart';

typedef AmendOrderCallback =
    Future<void> Function(OrderSummary order, Map<String, dynamic> fields);
typedef CancelOrderCallback = Future<void> Function(OrderSummary order);

class MyOrdersScreen extends StatelessWidget {
  const MyOrdersScreen({
    super.key,
    required this.orders,
    required this.loading,
    required this.onRefresh,
    required this.onAmendOrder,
    required this.onCancelOrder,
  });

  final List<OrderSummary> orders;
  final bool loading;
  final Future<void> Function() onRefresh;
  final AmendOrderCallback onAmendOrder;
  final CancelOrderCallback onCancelOrder;

  @override
  Widget build(BuildContext context) {
    final isDarkMode = Theme.of(context).brightness == Brightness.dark;
    final gradientColors = isDarkMode
        ? const [Color(0xFF0F1419), Color(0xFF1A2332)]
        : const [Color(0xFFF8F4EE), Color(0xFFF1FAF8)];

    return Scaffold(
      appBar: AppBar(title: const Text('My Orders')),
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
              if (loading)
                const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (orders.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No active orders.'),
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
                  child: const Text('Amend'),
                ),
                const SizedBox(width: 8),
                OutlinedButton(
                  onPressed: () async {
                    final shouldCancel = await showDialog<bool>(
                      context: context,
                      builder: (context) => AlertDialog(
                        title: const Text('Cancel Order'),
                        content: const Text(
                          'Are you sure you want to cancel this order?',
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

    await showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Amend Order'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: priceController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(labelText: 'Price'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: descriptionController,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Description'),
              ),
            ],
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
                fields['description'] = descriptionController.text.trim();

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
  }
}
