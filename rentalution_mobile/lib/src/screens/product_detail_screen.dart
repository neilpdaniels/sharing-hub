import 'dart:async';

import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../models/catalog_models.dart';
import '../models/order_models.dart';
import '../config.dart';
import '../storage/token_store.dart';
import '../services/api_client.dart';
import '../services/catalog_repository.dart';
import '../services/friends_repository.dart';
import '../services/transaction_repository.dart';
import 'transaction_detail_screen.dart';

Future<bool> _confirmAddAsFriendDialog(
  BuildContext context,
  String displayName,
) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (dialogContext) {
      return AlertDialog(
        title: const Text('Confirm Friend Request'),
        content: Text('Do you want to request $displayName adds you as friend?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('No, just add to my list'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Yes'),
          ),
        ],
      );
    },
  );
  return result ?? false;
}

String _lenderDisplayName(OrderLenderSummary lender) {
  if (lender.displayName.isNotEmpty) {
    return lender.displayName;
  }
  if (lender.username.isNotEmpty) {
    return '@${lender.username}';
  }
  return 'this user';
}

class ProductDetailScreen extends StatefulWidget {
  const ProductDetailScreen({
    super.key,
    this.productSlug,
    this.catalogRepository,
    this.transactionRepository,
    this.friendsRepository,
    this.accessToken,
    this.searchLocation,
    this.initialDistanceKm,
    this.onOpenListMyItem,
    this.onRequireLogin,
  });

  final String? productSlug;
  final CatalogRepository? catalogRepository;
  final TransactionRepository? transactionRepository;
  final FriendsRepository? friendsRepository;
  final String? accessToken;
  final String? searchLocation;
  final int? initialDistanceKm;
  final Future<void> Function(ProductDetail product)? onOpenListMyItem;
  final VoidCallback? onRequireLogin;

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  static const String _sortNewest = 'newest';
  static const String _sortPriceAsc = 'price_asc';
  static const String _sortPriceDesc = 'price_desc';
  static const String _viewList = 'list';
  static const String _viewMap = 'map';

  ProductDetail? _product;
  bool _loading = true;
  String? _error;
  String _sortBy = _sortNewest;
  String _viewMode = _viewList;
  late final String _searchLocation;
  int? _distanceKmFilter;
  bool _friendsOnly = false;
  bool _noDepositOnly = false;
  bool _deliveryOnly = false;
  bool _addingFriend = false;
  String? _friendStatus;

  bool get _isAuthenticated {
    final token = widget.accessToken;
    return token != null && token.isNotEmpty;
  }

  @override
  void initState() {
    super.initState();
    _searchLocation = (widget.searchLocation ?? '').trim();
    _distanceKmFilter = widget.initialDistanceKm;
    _load();
    _loadFriendStatus();
  }

  Future<void> _loadFriendStatus() async {
    final friendsRepository = widget.friendsRepository;
    final accessToken = widget.accessToken;
    final product = _product;
    if (friendsRepository == null ||
        accessToken == null ||
        accessToken.isEmpty ||
        product == null) {
      return;
    }
    try {
      final hub = await friendsRepository.fetchHub(accessToken: accessToken);
      if (!mounted) return;
      final lenderId = product.activeOrders.isNotEmpty
          ? product.activeOrders.first.lender.id
          : null;
      if (lenderId == null) {
        return;
      }
      final accepted = hub.accepted.any((friend) => friend.userId == lenderId);
      final pendingSent =
          hub.pendingSent.any((friend) => friend.userId == lenderId);
      final pendingReceived =
          hub.pendingReceived.any((friend) => friend.userId == lenderId);
      setState(() {
        if (accepted) {
          _friendStatus = 'accepted';
        } else if (pendingSent) {
          _friendStatus = 'pending_sent';
        } else if (pendingReceived) {
          _friendStatus = 'pending_received';
        } else {
          _friendStatus = null;
        }
      });
    } catch (_) {
      // Best effort only.
    }
  }

  Future<void> _load() async {
    final productSlug = widget.productSlug;
    final catalogRepository = widget.catalogRepository;
    if (productSlug == null ||
        productSlug.isEmpty ||
        catalogRepository == null) {
      setState(() {
        _loading = false;
        _error =
            'Product detail is missing required data. Please reopen this product.';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final product = await catalogRepository.fetchProductDetail(
        productSlug: productSlug,
        location: _searchLocation.isEmpty ? null : _searchLocation,
        distanceKm: _distanceKmFilter,
        accessToken: widget.accessToken,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _product = product;
      });
      unawaited(_loadFriendStatus());
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final appBarTitle = _product?.name ?? 'Product';
    return Scaffold(
      key: _scaffoldKey,
      appBar: AppBar(
        title: Text(appBarTitle),
        leading: null,
        actions: [
          IconButton(
            onPressed: () => _scaffoldKey.currentState?.openEndDrawer(),
            icon: const Icon(Icons.tune),
            tooltip: 'Filters',
          ),
        ],
      ),
      endDrawer: _buildFilterDrawer(),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(child: Text(_error!))
          : _buildContent(context),
    );
  }

  Widget _buildContent(BuildContext context) {
    final product = _product;
    if (product == null) {
      return const Center(child: Text('Product not found.'));
    }
    final visibleOrders = _visibleOrders(product);

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              IconButton(
                onPressed: Navigator.of(context).maybePop,
                icon: const Icon(Icons.arrow_back),
                tooltip: 'Back',
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  product.categoryTitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontSize: 12,
                      ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(14),
            child: product.imageUrl.isNotEmpty
                ? CachedNetworkImage(
                    imageUrl: product.imageUrl,
                    height: 250,
                    memCacheWidth: 1600,
                    memCacheHeight: 1600,
                    maxWidthDiskCache: 1800,
                    maxHeightDiskCache: 1800,
                    imageBuilder: (context, imageProvider) => Image(
                      image: imageProvider,
                      height: 250,
                      fit: BoxFit.contain,
                      filterQuality: FilterQuality.medium,
                    ),
                    errorWidget: (context, error, stackTrace) =>
                        _productImagePlaceholder(),
                  )
                : _productImagePlaceholder(),
          ),
          const SizedBox(height: 10),
          _productMetaCard(product),
          const SizedBox(height: 10),
          if (_isAuthenticated && widget.onOpenListMyItem != null) ...[
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () async {
                  await widget.onOpenListMyItem!.call(product);
                },
                icon: const Icon(Icons.add_box_outlined),
                label: const Text('List my item'),
              ),
            ),
            const SizedBox(height: 12),
          ],
          if (product.description.isNotEmpty) Text(product.description),
          const SizedBox(height: 18),
          Text(
            'Available to rent (${visibleOrders.length})',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          _listingControls(),
          const SizedBox(height: 8),
          if (visibleOrders.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('Nothing currently available to rent.'),
              ),
            )
          else if (_viewMode == _viewMap)
            _listingsMap(visibleOrders, product)
          else
            ...visibleOrders.map(
              (order) => Card(
                child: ListTile(
                  leading: _productThumb(
                    order.listingImageUrl.isNotEmpty
                        ? order.listingImageUrl
                        : product.imageUrl,
                  ),
                  title: Text(order.productName),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (_orderDistanceKm(order, product) != null)
                        Text(
                          '${_orderDistanceKm(order, product)!.toStringAsFixed(1)} km away',
                        ),
                      Text(_collectionPolicyText(order.collectionPolicy)),
                      Text(
                        'Postcode: ${order.postcode.isEmpty ? '-' : order.postcode}',
                      ),
                      const SizedBox(height: 6),
                      TextButton(
                        onPressed: () => _enquireOrder(order),
                        style: TextButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(0, 0),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          alignment: Alignment.centerLeft,
                        ),
                        child: const Text('Enquire'),
                      ),
                      if (_hasDiscountedPricing(order))
                        Text(
                          '(discounted pricing for longer rentals)',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                  ),
                  isThreeLine: true,
                  trailing: Column(
                    mainAxisSize: MainAxisSize.min,
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      IconButton(
                        visualDensity: VisualDensity.compact,
                        icon: Icon(
                          order.isFavourite
                              ? Icons.favorite
                              : Icons.favorite_border,
                        ),
                        color: order.isFavourite
                            ? Theme.of(context).colorScheme.error
                            : Theme.of(context).colorScheme.primary,
                        tooltip: order.isFavourite
                            ? 'Remove favourite'
                            : 'Save favourite',
                        onPressed: () => _toggleFavouriteOrder(order),
                      ),
                      Text(
                        '${order.currencySymbol}${order.price.toStringAsFixed(2)} / day',
                      ),
                      if (order.deposit > 0)
                        Text(
                          'Dep ${order.currencySymbol}${order.deposit.toStringAsFixed(2)}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                    ],
                  ),
                  onTap: () => _showOrderDetails(order, product),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _toggleFavouriteOrder(OrderSummary order) async {
    final accessToken = widget.accessToken;
    final catalogRepository = widget.catalogRepository;
    if (catalogRepository == null) {
      return;
    }
    if (accessToken == null || accessToken.isEmpty) {
      widget.onRequireLogin?.call();
      return;
    }

    try {
      final isFavourite = await catalogRepository.toggleFavouriteOrder(
        accessToken: accessToken,
        orderId: order.id,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isFavourite ? 'Added to favourites.' : 'Removed from favourites.',
          ),
        ),
      );
      await _load();
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Widget _productMetaCard(ProductDetail product) {
    final attrs = product.attributes
        .where(
          (attribute) =>
              attribute.name.trim().isNotEmpty && attribute.value.trim().isNotEmpty,
        )
        .toList(growable: false);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (product.description.isNotEmpty) ...[
              Text(
                product.description,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              if (attrs.isNotEmpty || product.tags.isNotEmpty)
                const SizedBox(height: 8),
            ],
            if (product.tags.isNotEmpty) ...[
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: product.tags
                    .map((tag) => Chip(label: Text(tag)))
                    .toList(growable: false),
              ),
            ],
            if (attrs.isNotEmpty) ...[
              if (product.tags.isNotEmpty) const SizedBox(height: 8),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: attrs
                    .map(
                      (attribute) => Chip(
                        label: Text('${attribute.name}: ${attribute.value}'),
                      ),
                    )
                    .toList(growable: false),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _metaRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text('$label: $value'),
    );
  }

  String _distanceLabel(int? value) {
    if (value == null) {
      return 'Any';
    }
    return '$value km';
  }

  Future<void> _applyProductFilters() async {
    Navigator.of(context).pop();
    if (_searchLocation.isNotEmpty) {
      await _load();
    }
  }

  Widget _buildFilterDrawer() {
    return Drawer(
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          children: [
            Text('Filters', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('Sort', style: Theme.of(context).textTheme.titleSmall),
            RadioListTile<String>(
              value: _sortNewest,
              groupValue: _sortBy,
              title: const Text('Newest'),
              dense: true,
              visualDensity: VisualDensity.compact,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() => _sortBy = value);
              },
            ),
            RadioListTile<String>(
              value: _sortPriceAsc,
              groupValue: _sortBy,
              title: const Text('Price: Low to High'),
              dense: true,
              visualDensity: VisualDensity.compact,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() => _sortBy = value);
              },
            ),
            RadioListTile<String>(
              value: _sortPriceDesc,
              groupValue: _sortBy,
              title: const Text('Price: High to Low'),
              dense: true,
              visualDensity: VisualDensity.compact,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() => _sortBy = value);
              },
            ),
            if (_searchLocation.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text('Distance', style: Theme.of(context).textTheme.titleSmall),
              RadioListTile<int?>(
                value: null,
                groupValue: _distanceKmFilter,
                title: Text(_distanceLabel(null)),
                dense: true,
                visualDensity: VisualDensity.compact,
                onChanged: (value) => setState(() => _distanceKmFilter = value),
              ),
              RadioListTile<int?>(
                value: 5,
                groupValue: _distanceKmFilter,
                title: Text(_distanceLabel(5)),
                dense: true,
                visualDensity: VisualDensity.compact,
                onChanged: (value) => setState(() => _distanceKmFilter = value),
              ),
              RadioListTile<int?>(
                value: 10,
                groupValue: _distanceKmFilter,
                title: Text(_distanceLabel(10)),
                dense: true,
                visualDensity: VisualDensity.compact,
                onChanged: (value) => setState(() => _distanceKmFilter = value),
              ),
              RadioListTile<int?>(
                value: 25,
                groupValue: _distanceKmFilter,
                title: Text(_distanceLabel(25)),
                dense: true,
                visualDensity: VisualDensity.compact,
                onChanged: (value) => setState(() => _distanceKmFilter = value),
              ),
              RadioListTile<int?>(
                value: 50,
                groupValue: _distanceKmFilter,
                title: Text(_distanceLabel(50)),
                dense: true,
                visualDensity: VisualDensity.compact,
                onChanged: (value) => setState(() => _distanceKmFilter = value),
              ),
              RadioListTile<int?>(
                value: 100,
                groupValue: _distanceKmFilter,
                title: Text(_distanceLabel(100)),
                dense: true,
                visualDensity: VisualDensity.compact,
                onChanged: (value) => setState(() => _distanceKmFilter = value),
              ),
            ],
            const SizedBox(height: 6),
            Text(
              'Listing filters',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            CheckboxListTile(
              value: _friendsOnly,
              title: const Text('My friends'),
              dense: true,
              visualDensity: VisualDensity.compact,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() => _friendsOnly = value);
              },
            ),
            CheckboxListTile(
              value: _noDepositOnly,
              title: const Text('No deposit'),
              dense: true,
              visualDensity: VisualDensity.compact,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() => _noDepositOnly = value);
              },
            ),
            CheckboxListTile(
              value: _deliveryOnly,
              title: const Text('Delivery available'),
              dense: true,
              visualDensity: VisualDensity.compact,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() => _deliveryOnly = value);
              },
            ),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: _applyProductFilters,
              icon: const Icon(Icons.check),
              label: const Text('Apply'),
            ),
          ],
        ),
      ),
    );
  }

  String _lenderVerificationSummary(OrderLenderSummary lender) {
    final labels = <String>[
      if (lender.emailConfirmed) 'Email',
      if (lender.mobileVerified) 'Mobile',
      if (lender.addressVerified) 'Address',
    ];
    if (labels.isEmpty) {
      return 'No checks shown';
    }
    return labels.join(', ');
  }

  Future<void> _openLenderDetails(OrderLenderSummary lender) async {
    final catalogRepository = widget.catalogRepository;
    if (catalogRepository == null) {
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _LenderDetailScreen(
          lender: lender,
          catalogRepository: catalogRepository,
          friendsRepository: widget.friendsRepository,
          accessToken: widget.accessToken,
          onRequireLogin: widget.onRequireLogin,
        ),
      ),
    );
  }

  Future<void> _addAsFriend(int userId) async {
    final friendsRepository = widget.friendsRepository;
    final accessToken = widget.accessToken;
    if (friendsRepository == null ||
        accessToken == null ||
        accessToken.isEmpty ||
        _addingFriend) {
      return;
    }

    setState(() {
      _addingFriend = true;
    });

    try {
      final message = await friendsRepository.sendFriendRequest(
        accessToken: accessToken,
        userId: userId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    } finally {
      if (mounted) {
        setState(() {
          _addingFriend = false;
        });
      }
    }
  }

  Future<bool> _confirmAddAsFriend(String displayName) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Confirm Friend Request'),
          content: Text('Do you want to request $displayName adds you as friend?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('No, just add to my list'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Yes'),
            ),
          ],
        );
      },
    );
    return result ?? false;
  }

  Widget _productThumb(String imageUrl) {
    if (imageUrl.trim().isEmpty) {
      return Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          color: const Color(0xFFF0F3F4),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Icon(Icons.image_not_supported_outlined),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: CachedNetworkImage(
        imageUrl: imageUrl,
        width: 52,
        height: 52,
        memCacheWidth: 104,
        memCacheHeight: 104,
        maxWidthDiskCache: 208,
        maxHeightDiskCache: 208,
        imageBuilder: (context, imageProvider) => Image(
          image: imageProvider,
          width: 52,
          height: 52,
          fit: BoxFit.cover,
          filterQuality: FilterQuality.low,
        ),
        errorWidget: (context, error, stackTrace) {
          return const SizedBox(
            width: 52,
            height: 52,
            child: Center(child: Icon(Icons.broken_image_outlined)),
          );
        },
      ),
    );
  }

  Widget _productImagePlaceholder() {
    return Container(
      height: 250,
      color: const Color(0xFFF0F3F4),
      alignment: Alignment.center,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.image_not_supported_outlined,
            size: 44,
            color: Color(0xFF7A8A93),
          ),
          const SizedBox(height: 8),
          Text(
            'No product image',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Future<void> _showOrderDetails(
    OrderSummary order,
    ProductDetail product,
  ) async {
    final imageUrls = order.listingImageUrls.isNotEmpty
        ? order.listingImageUrls
        : (order.listingImageUrl.isNotEmpty
              ? [order.listingImageUrl]
              : (product.imageUrl.isNotEmpty
                    ? [product.imageUrl]
                    : const <String>[]));

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return SafeArea(
          child: FractionallySizedBox(
            heightFactor: 0.9,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: ListView(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          order.productName,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ),
                      IconButton(
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(Icons.close),
                        tooltip: 'Close',
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Listing details',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 12),
                  if (imageUrls.isEmpty)
                    const SizedBox(
                      height: 200,
                      child: Center(
                        child: Icon(Icons.inventory_2_outlined, size: 42),
                      ),
                    )
                  else
                    SizedBox(
                      height: 220,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: imageUrls.length,
                        separatorBuilder: (context, index) =>
                            const SizedBox(width: 10),
                        itemBuilder: (context, index) {
                          final url = imageUrls[index];
                          return ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: AspectRatio(
                              aspectRatio: 1.2,
                              child: CachedNetworkImage(
                                imageUrl: url,
                                memCacheWidth: 1200,
                                memCacheHeight: 1000,
                                maxWidthDiskCache: 1600,
                                maxHeightDiskCache: 1400,
                                imageBuilder: (context, imageProvider) =>
                                    Image(
                                  image: imageProvider,
                                  fit: BoxFit.cover,
                                  filterQuality: FilterQuality.medium,
                                ),
                                errorWidget: (context, error, stackTrace) =>
                                    const ColoredBox(
                                      color: Color(0x11000000),
                                      child: Center(
                                        child: Icon(
                                          Icons.broken_image_outlined,
                                        ),
                                      ),
                                    ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  const SizedBox(height: 14),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Listing details',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          _metaRow(
                            'Price per day',
                            '${order.currencySymbol}${order.price.toStringAsFixed(2)}',
                          ),
                          if (_hasDiscountedPricing(order))
                            _metaRow(
                              'Note',
                              '(discounted pricing for longer rentals)',
                            ),
                          _metaRow(
                            'Deposit',
                            order.deposit > 0
                                ? '${order.currencySymbol}${order.deposit.toStringAsFixed(2)}'
                                : '-',
                          ),
                          _metaRow(
                            'Collection policy',
                            _collectionPolicyText(order.collectionPolicy),
                          ),
                          if (_orderDistanceKm(order, product) != null)
                            _metaRow(
                              'Distance',
                              '${_orderDistanceKm(order, product)!.toStringAsFixed(1)} km away',
                            ),
                          _metaRow(
                            'Postcode',
                            order.postcode.isEmpty ? '-' : order.postcode,
                          ),
                          _metaRow(
                            'Description',
                            order.description.isEmpty ? '-' : order.description,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Card(
                    child: InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: () => _openLenderDetails(order.lender),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    'Lender details',
                                    style: Theme.of(
                                      context,
                                    ).textTheme.titleMedium,
                                  ),
                                ),
                                Icon(
                                  Icons.chevron_right,
                                  color: Theme.of(context).colorScheme.primary,
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                CircleAvatar(
                                  radius: 24,
                                  backgroundImage:
                                      order.lender.avatarUrl.isNotEmpty
                                      ? NetworkImage(order.lender.avatarUrl)
                                      : null,
                                  child: order.lender.avatarUrl.isEmpty
                                      ? Text(
                                          order.lender.displayName.isNotEmpty
                                              ? order.lender.displayName[0]
                                                    .toUpperCase()
                                              : '?',
                                        )
                                      : null,
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        order.lender.displayName,
                                        style: Theme.of(
                                          context,
                                        ).textTheme.titleMedium,
                                      ),
                                      if (order.lender.username.isNotEmpty)
                                        InkWell(
                                          onTap: () => _openLenderDetails(
                                            order.lender,
                                          ),
                                          borderRadius: BorderRadius.circular(6),
                                          child: Padding(
                                            padding: const EdgeInsets.symmetric(
                                              vertical: 2,
                                              horizontal: 2,
                                            ),
                                            child: Container(
                                              padding:
                                                  const EdgeInsets.symmetric(
                                                horizontal: 10,
                                                vertical: 6,
                                              ),
                                              decoration: BoxDecoration(
                                                color: Theme.of(context)
                                                    .colorScheme
                                                    .surfaceContainerHighest
                                                    .withOpacity(0.8),
                                                borderRadius:
                                                    BorderRadius.circular(999),
                                              ),
                                              child: Text(
                                                '@${order.lender.username}',
                                                style: Theme.of(context)
                                                    .textTheme
                                                    .bodySmall
                                                    ?.copyWith(
                                                      color:
                                                          Theme.of(context)
                                                              .colorScheme
                                                              .primary,
                                                      fontWeight:
                                                          FontWeight.w600,
                                                    ),
                                              ),
                                            ),
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            _metaRow(
                              'Rating',
                              '${order.lender.rating.toStringAsFixed(1)} / 5',
                            ),
                            _metaRow(
                              'Successful bookings',
                              order.lender.successfulTxns.toString(),
                            ),
                            _metaRow(
                              'Postcode',
                              order.lender.postcode.isEmpty
                                  ? '-'
                                  : order.lender.postcode,
                            ),
                            _metaRow(
                              'Verified',
                              _lenderVerificationSummary(order.lender),
                            ),
                            const SizedBox(height: 8),
                            Align(
                              alignment: Alignment.centerRight,
                              child: !_isAuthenticated
                                  ? OutlinedButton.icon(
                                      onPressed: widget.onRequireLogin,
                                      icon: const Icon(Icons.login),
                                      label: const Text(
                                        'Log in to add as friend',
                                      ),
                                    )
                                  : FilledButton.tonalIcon(
                                      onPressed: _addingFriend
                                          ? null
                                          : () async {
                                              final confirmed =
                                                  await _confirmAddAsFriend(
                                                _lenderDisplayName(order.lender),
                                              );
                                              if (!confirmed) {
                                                return;
                                              }
                                              await _addAsFriend(
                                                order.lender.id,
                                              );
                                            },
                                      icon: _addingFriend
                                          ? const SizedBox(
                                              width: 16,
                                              height: 16,
                                              child:
                                                  CircularProgressIndicator(
                                                strokeWidth: 2,
                                              ),
                                            )
                                          : const Icon(
                                              Icons.person_add_alt_1_outlined,
                                            ),
                                      label: Text(
                                        _friendStatus == 'accepted'
                                            ? 'Already friends'
                                            : _friendStatus == 'pending_sent'
                                                ? 'Friend request sent'
                                                : _friendStatus == 'pending_received'
                                                    ? 'Respond in Friends'
                                          : 'Add as friend',
                                      ),
                                    ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  ElevatedButton.icon(
                    onPressed: () => _enquireOrder(order),
                    icon: const Icon(Icons.chat_bubble_outline),
                    label: const Text('Enquire'),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _enquireOrder(OrderSummary order) async {
    final dependencies = await _resolveEnquiryDependencies();
    if (dependencies == null) {
      if (mounted) {
        final goToLogin = await showDialog<bool>(
          context: context,
          builder: (dialogContext) {
            return AlertDialog(
              title: const Text('Login required'),
              content: const Text('You must be logged in to send an enquiry.'),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(true),
                  child: const Text('Go to login'),
                ),
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(false),
                  child: const Text('OK'),
                ),
              ],
            );
          },
        );

        if (goToLogin == true) {
          widget.onRequireLogin?.call();
        }
      }
      return;
    }

    final transactionRepository = dependencies.repository;
    final accessToken = dependencies.accessToken;

    if (!mounted) {
      return;
    }

    final messageController = TextEditingController();
    final blockedDates = _blockedDates(order);
    final handoverDates = _handoverUnavailableDates(order);
    final initialRange = _initialEnquiryRange(order);
    if (initialRange == null) {
      messageController.dispose();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No available dates remain for this listing.'),
        ),
      );
      return;
    }

    DateTimeRange selectedRange = initialRange;
    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final result = await showDialog<bool>(
        context: context,
        builder: (dialogContext) {
          return StatefulBuilder(
            builder: (dialogContext, setDialogState) {
              Future<void> chooseDates() async {
                final picked = await showDateRangePicker(
                  context: dialogContext,
                  firstDate: _dateOnly(DateTime.now()),
                  lastDate: _lastEnquiryDate(order),
                  currentDate: _dateOnly(DateTime.now()),
                  initialDateRange: selectedRange,
                  selectableDayPredicate:
                      (day, selectedStartDay, selectedEndDay) {
                        final normalizedDay = _dateOnly(day);
                        final isBoundaryUnavailable = handoverDates.contains(
                          normalizedDay,
                        );
                        return !blockedDates.contains(normalizedDay) &&
                            !isBoundaryUnavailable &&
                            !normalizedDay.isAfter(_lastEnquiryDate(order));
                      },
                );

                if (picked == null) {
                  return;
                }

                final pickedRange = DateTimeRange(
                  start: _dateOnly(picked.start),
                  end: _dateOnly(picked.end),
                );
                if (_selectedRangeIsTooLong(pickedRange)) {
                  setDialogState(() {
                    selectedRange = pickedRange;
                  });
                  return;
                }

                setDialogState(() {
                  selectedRange = pickedRange;
                });
              }

              final blockedCount = blockedDates.length;
              final handoverCount = handoverDates.length;
              final selectedLabel =
                  '${_formatDate(selectedRange.start)} - ${_formatDate(selectedRange.end)}';

              return AlertDialog(
                title: const Text('Send Enquiry'),
                content: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Rental enquiry'),
                      const SizedBox(height: 8),
                      Text(
                        'Available until ${_formatDate(_lastEnquiryDate(order))}',
                        style: Theme.of(dialogContext).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Already rented dates: $blockedCount',
                        style: Theme.of(dialogContext).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Handover-unavailable dates: $handoverCount (start/end only)',
                        style: Theme.of(dialogContext).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        order.maxRentalDays > 0
                            ? 'Max rental days: ${order.maxRentalDays}'
                            : 'Max rental days: not set',
                        style: Theme.of(dialogContext).textTheme.bodySmall,
                      ),
                      if (order.maxRentalDays > 30) ...[
                        const SizedBox(height: 8),
                        const Text(
                          'Rentals over 30 days are not supported yet. Please choose 30 days or fewer.',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ],
                      if (_selectedRangeHasLongRental(selectedRange)) ...[
                        const SizedBox(height: 8),
                        const Text(
                          'Long rentals over 5 days require a Visa or Mastercard credit card for the deposit. You can still use a different card for payment.',
                        ),
                      ],
                      if (blockedCount > 0 || handoverCount > 0) ...[
                        const SizedBox(height: 4),
                        Text(
                          'Greyed-out dates are already rented or unavailable and cannot be selected.',
                          style: Theme.of(dialogContext).textTheme.bodySmall,
                        ),
                      ],
                      const SizedBox(height: 12),
                      OutlinedButton.icon(
                        onPressed: chooseDates,
                        icon: const Icon(Icons.calendar_month_outlined),
                        label: const Text('Choose rental dates'),
                      ),
                      const SizedBox(height: 8),
                      Text('Selected: $selectedLabel'),
                      const SizedBox(height: 12),
                      const Text('Optional message:'),
                      const SizedBox(height: 8),
                      TextField(
                        controller: messageController,
                        maxLines: 3,
                        decoration: InputDecoration(
                          hintText: 'Add any questions or details...',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(dialogContext, false),
                    child: const Text('Cancel'),
                  ),
                  ElevatedButton(
                    onPressed: _selectedRangeIsTooLong(selectedRange)
                        ? null
                        : () => Navigator.pop(dialogContext, true),
                    child: const Text('Send Enquiry'),
                  ),
                ],
              );
            },
          );
        },
      );

      if (result != true) {
        return;
      }

      if (_rangeViolatesAvailability(
        range: selectedRange,
        blockedDates: blockedDates,
        handoverDates: handoverDates,
      )) {
        messenger.showSnackBar(
          const SnackBar(
            content: Text(
              'Selected dates include blocked days or an unavailable start/end day.',
            ),
          ),
        );
        return;
      }

      // Close the bottom sheet
      if (mounted) {
        navigator.pop();
      }

      // Show loading
      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Creating enquiry...')),
        );
      }

      final transaction = await transactionRepository.createEnquiry(
        accessToken: accessToken,
        orderReference: order.orderReference,
        enquiryMessage: messageController.text,
        rentalStartDate: selectedRange.start,
        rentalEndDate: selectedRange.end,
      );

      if (mounted) {
        messenger.clearSnackBars();
        messenger.showSnackBar(
          SnackBar(
            content: const Text('Enquiry sent successfully.'),
            duration: const Duration(seconds: 2),
          ),
        );

        // Navigate to transaction detail screen
        await navigator.push(
          MaterialPageRoute(
            builder: (_) => TransactionDetailScreen(
              transactionReference: transaction.reference,
              repository: transactionRepository,
              accessToken: accessToken,
              friendsRepository: widget.friendsRepository!,
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        messenger.clearSnackBars();
        messenger.showSnackBar(
          SnackBar(
            content: Text('Error: ${e.toString()}'),
            duration: const Duration(seconds: 3),
          ),
        );
      }
    } finally {
      messageController.dispose();
    }
  }

  Set<DateTime> _blockedDates(OrderSummary order) {
    return order.blockedDates.map(_dateOnly).toSet();
  }

  Set<DateTime> _handoverUnavailableDates(OrderSummary order) {
    return order.handoverUnavailableDates.map(_dateOnly).toSet();
  }

  bool _rangeViolatesAvailability({
    required DateTimeRange range,
    required Set<DateTime> blockedDates,
    required Set<DateTime> handoverDates,
  }) {
    final start = _dateOnly(range.start);
    final end = _dateOnly(range.end);
    if (handoverDates.contains(start) || handoverDates.contains(end)) {
      return true;
    }

    var cursor = _dateOnly(range.start);
    while (!cursor.isAfter(end)) {
      if (blockedDates.contains(cursor)) {
        return true;
      }
      cursor = cursor.add(const Duration(days: 1));
    }
    return false;
  }

  DateTimeRange? _initialEnquiryRange(OrderSummary order) {
    final today = _dateOnly(DateTime.now());
    final lastDate = _lastEnquiryDate(order);
    final blockedDates = _blockedDates(order);
    final handoverDates = _handoverUnavailableDates(order);
    var cursor = today;

    while (!cursor.isAfter(lastDate)) {
      if (!blockedDates.contains(cursor) && !handoverDates.contains(cursor)) {
        return DateTimeRange(start: cursor, end: cursor);
      }
      cursor = cursor.add(const Duration(days: 1));
    }

    return null;
  }

  DateTime _lastEnquiryDate(OrderSummary order) {
    final expiry = order.expiryDate;
    if (expiry != null) {
      return _dateOnly(expiry);
    }
    return _dateOnly(DateTime.now().add(const Duration(days: 90)));
  }

  DateTime _dateOnly(DateTime value) {
    return DateTime(value.year, value.month, value.day);
  }

  bool _selectedRangeHasLongRental(DateTimeRange range) {
    return range.duration.inDays + 1 > 5;
  }

  bool _selectedRangeIsTooLong(DateTimeRange range) {
    return range.duration.inDays + 1 > 30;
  }

  String _formatDate(DateTime value) {
    final date = _dateOnly(value);
    return '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  String _collectionPolicyText(String code) {
    switch (code.trim().toUpperCase()) {
      case 'MC':
        return 'Collection only (you collect)';
      case 'WD':
        return 'Delivery available (lender delivers)';
      case 'EI':
        return 'Collection or delivery (to be agreed)';
      default:
        return code.trim().isEmpty ? '-' : code;
    }
  }

  Future<_EnquiryDependencies?> _resolveEnquiryDependencies() async {
    final injectedRepository = widget.transactionRepository;
    final injectedToken = widget.accessToken;
    if (injectedRepository != null &&
        injectedToken != null &&
        injectedToken.isNotEmpty) {
      return _EnquiryDependencies(
        repository: injectedRepository,
        accessToken: injectedToken,
      );
    }

    final storedToken = await TokenStore().getAccessToken();
    if (storedToken == null || storedToken.isEmpty) {
      return null;
    }

    final repository =
        injectedRepository ??
        TransactionRepository(apiClient: ApiClient(baseUrl: AppConfig.baseUrl));

    return _EnquiryDependencies(
      repository: repository,
      accessToken: storedToken,
    );
  }

  Widget _listingControls() {
    return SegmentedButton<String>(
      segments: const [
        ButtonSegment<String>(
          value: _viewList,
          icon: Icon(Icons.list),
          label: Text('List'),
        ),
        ButtonSegment<String>(
          value: _viewMap,
          icon: Icon(Icons.map_outlined),
          label: Text('Map'),
        ),
      ],
      selected: {_viewMode},
      onSelectionChanged: (selection) {
        final selected = selection.firstOrNull;
        if (selected == null) {
          return;
        }
        setState(() => _viewMode = selected);
      },
    );
  }

  Widget _listingsMap(List<OrderSummary> orders, ProductDetail product) {
    final mappedOrders = orders
        .where((order) => order.latitude != null && order.longitude != null)
        .toList(growable: false);

    if (mappedOrders.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'No mapped listings yet. Listings need latitude/longitude to appear on the map.',
          ),
        ),
      );
    }

    final center = _mapCenter(mappedOrders);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox(
            height: 300,
            child: FlutterMap(
              options: MapOptions(initialCenter: center, initialZoom: 9),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.rentalution.mobile',
                ),
                MarkerLayer(
                  markers: mappedOrders
                      .map((order) {
                        return Marker(
                          point: LatLng(order.latitude!, order.longitude!),
                          width: 44,
                          height: 44,
                          child: GestureDetector(
                            onTap: () => _showOrderDetails(order, product),
                            child: Icon(
                              Icons.location_pin,
                              size: 36,
                              color: _pinColor(order),
                            ),
                          ),
                        );
                      })
                      .toList(growable: false),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 12,
          runSpacing: 6,
          children: const [
            _LegendItem(label: 'Standard listing', color: Colors.blue),
            _LegendItem(label: 'Friends listing', color: Colors.red),
            _LegendItem(label: 'Free listing', color: Color(0xFFFFC107)),
          ],
        ),
      ],
    );
  }

  LatLng _mapCenter(List<OrderSummary> orders) {
    final count = orders.length;
    final totalLat = orders.fold<double>(
      0,
      (sum, order) => sum + (order.latitude ?? 0),
    );
    final totalLng = orders.fold<double>(
      0,
      (sum, order) => sum + (order.longitude ?? 0),
    );
    return LatLng(totalLat / count, totalLng / count);
  }

  Color _pinColor(OrderSummary order) {
    if (order.price <= 0) {
      return const Color(0xFFFFC107);
    }
    if (order.letVisibility == 'FRIENDS') {
      return Colors.red;
    }
    return Colors.blue;
  }

  bool _hasDiscountedPricing(OrderSummary order) {
    if (order.priceBands.isEmpty) {
      return false;
    }
    for (final band in order.priceBands) {
      if (band.durationDays > 1 &&
          band.pricePerDay > 0 &&
          band.pricePerDay < order.price) {
        return true;
      }
    }
    return false;
  }

  double? _orderDistanceKm(OrderSummary order, ProductDetail product) {
    return order.distanceKm;
  }

  List<OrderSummary> _visibleOrders(ProductDetail product) {
    final filtered = product.activeOrders
        .where((order) {
          if (_friendsOnly && order.letVisibility != 'FRIENDS') {
            return false;
          }
          if (_noDepositOnly && (order.deposit > 0)) {
            return false;
          }
          if (_deliveryOnly &&
              order.collectionPolicy != 'WD' &&
              order.collectionPolicy != 'EI') {
            return false;
          }
          return true;
        })
        .toList(growable: false);

    filtered.sort((a, b) {
      if (_sortBy == _sortPriceAsc) {
        return a.price.compareTo(b.price);
      }
      if (_sortBy == _sortPriceDesc) {
        return b.price.compareTo(a.price);
      }
      final aTime = a.amended ?? DateTime.fromMillisecondsSinceEpoch(0);
      final bTime = b.amended ?? DateTime.fromMillisecondsSinceEpoch(0);
      return bTime.compareTo(aTime);
    });

    return filtered;
  }
}

class _EnquiryDependencies {
  _EnquiryDependencies({required this.repository, required this.accessToken});

  final TransactionRepository repository;
  final String accessToken;
}

class _LenderDetailScreen extends StatefulWidget {
  const _LenderDetailScreen({
    required this.lender,
    required this.catalogRepository,
    required this.friendsRepository,
    required this.accessToken,
    required this.onRequireLogin,
  });

  final OrderLenderSummary lender;
  final CatalogRepository catalogRepository;
  final FriendsRepository? friendsRepository;
  final String? accessToken;
  final VoidCallback? onRequireLogin;

  @override
  State<_LenderDetailScreen> createState() => _LenderDetailScreenState();
}

class _LenderDetailScreenState extends State<_LenderDetailScreen> {
  String? _friendStatus;
  bool _loadingFriendStatus = false;

  @override
  void initState() {
    super.initState();
    _loadFriendStatus();
  }

  bool get _isAuthenticated {
    final token = widget.accessToken;
    return token != null && token.isNotEmpty;
  }

  Future<void> _loadFriendStatus() async {
    final friendsRepository = widget.friendsRepository;
    final accessToken = widget.accessToken;
    if (friendsRepository == null || accessToken == null || accessToken.isEmpty) {
      return;
    }
    setState(() {
      _loadingFriendStatus = true;
    });
    try {
      final hub = await friendsRepository.fetchHub(accessToken: accessToken);
      if (!mounted) return;
      final lenderId = widget.lender.id;
      final accepted = hub.accepted.any((friend) => friend.userId == lenderId);
      final pendingSent = hub.pendingSent.any((friend) => friend.userId == lenderId);
      final pendingReceived = hub.pendingReceived.any((friend) => friend.userId == lenderId);
      setState(() {
        if (accepted) {
          _friendStatus = 'accepted';
        } else if (pendingSent) {
          _friendStatus = 'pending_sent';
        } else if (pendingReceived) {
          _friendStatus = 'pending_received';
        } else {
          _friendStatus = null;
        }
      });
    } catch (_) {
      // Best effort only.
    } finally {
      if (mounted) {
        setState(() {
          _loadingFriendStatus = false;
        });
      }
    }
  }

  String _verificationSummary() {
    final labels = <String>[
      if (widget.lender.emailConfirmed) 'Email verified',
      if (widget.lender.mobileVerified) 'Mobile verified',
      if (widget.lender.addressVerified) 'Address verified',
    ];
    if (labels.isEmpty) {
      return 'No checks shown';
    }
    return labels.join(', ');
  }

  Widget _metaRow(BuildContext context, String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        '$label: $value',
        style: Theme.of(context).textTheme.bodyMedium,
      ),
    );
  }

  Future<bool> _confirmAddAsFriend(String displayName) async {
    return _confirmAddAsFriendDialog(context, displayName);
  }

  Future<void> _showFriendRequestSent(BuildContext context, String displayName) async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Friend request sent'),
          content: Text('Your request to add $displayName has been sent.'),
          actions: [
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('OK'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final canRequestFriend = _isAuthenticated &&
        widget.friendsRepository != null &&
        _friendStatus == null &&
        !_loadingFriendStatus;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Lender details'),
        leading: IconButton(
          onPressed: () => Navigator.of(context).maybePop(),
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Back',
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      CircleAvatar(
                        radius: 32,
                        backgroundImage: widget.lender.avatarUrl.isNotEmpty
                            ? NetworkImage(widget.lender.avatarUrl)
                            : null,
                        child: widget.lender.avatarUrl.isEmpty
                            ? Text(
                                widget.lender.displayName.isNotEmpty
                                    ? widget.lender.displayName[0].toUpperCase()
                                    : '?',
                                style: Theme.of(context).textTheme.titleLarge,
                              )
                            : null,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              widget.lender.displayName,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            if (widget.lender.username.isNotEmpty)
                              Text(
                                '@${widget.lender.username}',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _metaRow(
                    context,
                    'Rating',
                    '${widget.lender.rating.toStringAsFixed(1)} / 5',
                  ),
                  _metaRow(
                    context,
                    'Successful bookings',
                    widget.lender.successfulTxns.toString(),
                  ),
                  _metaRow(
                    context,
                    'Postcode',
                    widget.lender.postcode.isEmpty ? '-' : widget.lender.postcode,
                  ),
                  _metaRow(context, 'Verification', _verificationSummary()),
                  const SizedBox(height: 8),
                  if (!_isAuthenticated) ...[
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: widget.onRequireLogin,
                        icon: const Icon(Icons.login),
                        label: const Text('Log in to add as friend'),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ] else if (_friendStatus == 'accepted') ...[
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.tonalIcon(
                        onPressed: null,
                        icon: const Icon(Icons.verified_user_outlined),
                        label: const Text('Already friends'),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ] else if (_friendStatus == 'pending_sent') ...[
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.tonalIcon(
                        onPressed: null,
                        icon: const Icon(Icons.hourglass_top_outlined),
                        label: const Text('Friend request pending'),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ] else if (_friendStatus == 'pending_received') ...[
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.tonalIcon(
                        onPressed: null,
                        icon: const Icon(Icons.inbox_outlined),
                        label: const Text('Respond in Friends'),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ] else if (canRequestFriend) ...[
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.tonalIcon(
                        onPressed: () async {
                          final confirmed = await _confirmAddAsFriend(
                            _lenderDisplayName(widget.lender),
                          );
                          if (!confirmed) {
                            return;
                          }
                          try {
                            final message = await widget.friendsRepository!.sendFriendRequest(
                              accessToken: widget.accessToken!,
                              userId: widget.lender.id,
                            );
                            if (context.mounted) {
                              await _showFriendRequestSent(
                                context,
                                _lenderDisplayName(widget.lender),
                              );
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text(message)),
                              );
                            }
                          } catch (e) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text(e.toString())),
                              );
                            }
                          }
                        },
                        icon: const Icon(Icons.person_add_alt_1_outlined),
                        label: Text(
                          _friendStatus == 'accepted'
                              ? 'Already friends'
                              : _friendStatus == 'pending_sent'
                                  ? 'Friend request sent'
                                  : _friendStatus == 'pending_received'
                                      ? 'Respond in Friends'
                                      : 'Add as friend',
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                          Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => _LenderListingsScreen(
                                lender: widget.lender,
                                catalogRepository: widget.catalogRepository,
                              ),
                            ),
                          );
                      },
                      icon: const Icon(Icons.inventory_2_outlined),
                      label: const Text('View all listings from this lender'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _LenderListingsScreen extends StatelessWidget {
  const _LenderListingsScreen({
    required this.lender,
    required this.catalogRepository,
  });

  final OrderLenderSummary lender;
  final CatalogRepository catalogRepository;

  String _collectionPolicyText(String code) {
    switch (code) {
      case 'CO':
        return 'Collection only';
      case 'EI':
        return 'Either collection or delivery';
      case 'WD':
        return 'Will deliver';
      default:
        return code.isEmpty ? '-' : code;
    }
  }

  Widget _listingThumb(OrderSummary order) {
    if (order.listingImageUrl.trim().isEmpty) {
      return Container(
        width: 68,
        height: 68,
        decoration: BoxDecoration(
          color: const Color(0xFFF0F3F4),
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Icon(Icons.image_not_supported_outlined),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Image.network(
        order.listingImageUrl,
        width: 68,
        height: 68,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) {
          return Container(
            width: 68,
            height: 68,
            decoration: BoxDecoration(
              color: const Color(0xFFF0F3F4),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.broken_image_outlined),
          );
        },
      ),
    );
  }

  Widget _detailLine(BuildContext context, String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(text, style: Theme.of(context).textTheme.bodySmall),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Lender listings')),
      body: FutureBuilder<List<OrderSummary>>(
        future: catalogRepository.fetchLenderListings(lenderId: lender.id),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(child: Text(snapshot.error.toString()));
          }

          final orders = snapshot.data ?? const <OrderSummary>[];
          return SafeArea(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  lender.displayName,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 4),
                Text(
                  'Active listings: ${orders.length}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
                if (orders.isEmpty)
                  const Card(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: Text('Nothing currently available to rent.'),
                    ),
                  ),
                for (final order in orders) ...[
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _listingThumb(order),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  order.productName,
                                  style: Theme.of(
                                    context,
                                  ).textTheme.titleMedium,
                                ),
                                _detailLine(
                                  context,
                                  'Price per day: ${order.currencySymbol}${order.price.toStringAsFixed(2)}',
                                ),
                                _detailLine(
                                  context,
                                  order.deposit > 0
                                      ? 'Deposit: ${order.currencySymbol}${order.deposit.toStringAsFixed(2)}'
                                      : 'Deposit: -',
                                ),
                                _detailLine(
                                  context,
                                  'Collection policy: ${_collectionPolicyText(order.collectionPolicy)}',
                                ),
                                _detailLine(
                                  context,
                                  'Postcode: ${order.postcode.isEmpty ? '-' : order.postcode}',
                                ),
                                if (order.description.isNotEmpty)
                                  _detailLine(context, order.description),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _LegendItem extends StatelessWidget {
  const _LegendItem({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.location_pin, size: 18, color: color),
        const SizedBox(width: 4),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
