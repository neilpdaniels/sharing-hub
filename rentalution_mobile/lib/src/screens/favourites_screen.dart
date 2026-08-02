import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';

import '../models/order_models.dart';
import '../theme.dart';

typedef ToggleFavouriteOrderCallback = Future<void> Function(OrderSummary order);

class FavouritesScreen extends StatelessWidget {
  const FavouritesScreen({
    super.key,
    required this.orders,
    required this.loading,
    required this.onRefresh,
    required this.onToggleFavourite,
    required this.onOpenProduct,
  });

  final List<OrderSummary> orders;
  final bool loading;
  final Future<void> Function() onRefresh;
  final ToggleFavouriteOrderCallback onToggleFavourite;
  final Future<void> Function(String productSlug) onOpenProduct;

  @override
  Widget build(BuildContext context) {
    final gradientColors = rentalutionBackgroundGradient(
      Theme.of(context).brightness,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Favourites')),
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
                    child: Text('No favourite listings yet.'),
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
    final thumbUrl = order.listingThumbnailUrl.isNotEmpty
        ? order.listingThumbnailUrl
        : order.listingImageUrl.isNotEmpty
            ? order.listingImageUrl
        : (order.listingImageUrls.isNotEmpty ? order.listingImageUrls.first : '');

    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        leading: ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: thumbUrl.isEmpty
              ? Container(
                  width: 60,
                  height: 60,
                  color: const Color(0x11000000),
                  child: const Icon(Icons.inventory_2_outlined),
                )
              : CachedNetworkImage(
                  imageUrl: thumbUrl,
                  width: 60,
                  height: 60,
                  memCacheWidth: 120,
                  memCacheHeight: 120,
                  maxWidthDiskCache: 240,
                  maxHeightDiskCache: 240,
                  imageBuilder: (context, imageProvider) => Image(
                    image: imageProvider,
                    width: 60,
                    height: 60,
                    fit: BoxFit.cover,
                  ),
                  errorWidget: (context, error, stackTrace) => Container(
                    width: 60,
                    height: 60,
                    color: const Color(0x11000000),
                    child: const Icon(Icons.broken_image_outlined),
                  ),
                ),
        ),
        title: Text(order.productName),
        subtitle: Text(
          order.distanceKm != null
              ? '${order.currencySymbol}${order.price.toStringAsFixed(2)} / day • ${order.distanceKm!.toStringAsFixed(1)} km away'
              : '${order.currencySymbol}${order.price.toStringAsFixed(2)} / day',
        ),
        trailing: IconButton(
          icon: const Icon(Icons.favorite),
          color: Theme.of(context).colorScheme.error,
          tooltip: 'Remove favourite',
          onPressed: () => onToggleFavourite(order),
        ),
        onTap: () => onOpenProduct(order.productSlug),
      ),
    );
  }
}
