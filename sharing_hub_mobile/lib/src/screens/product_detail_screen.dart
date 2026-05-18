import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../models/catalog_models.dart';
import '../models/order_models.dart';
import '../config.dart';
import '../storage/token_store.dart';
import '../services/api_client.dart';
import '../services/catalog_repository.dart';
import '../services/transaction_repository.dart';
import 'transaction_detail_screen.dart';

class ProductDetailScreen extends StatefulWidget {
  const ProductDetailScreen({
    super.key,
    this.productSlug,
    this.catalogRepository,
    this.transactionRepository,
    this.accessToken,
  });

  final String? productSlug;
  final CatalogRepository? catalogRepository;
  final TransactionRepository? transactionRepository;
  final String? accessToken;

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
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
  bool _friendsOnly = false;
  bool _withDepositOnly = false;
  bool _deliveryOnly = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final productSlug = widget.productSlug;
    final catalogRepository = widget.catalogRepository;
    if (productSlug == null || productSlug.isEmpty || catalogRepository == null) {
      setState(() {
        _loading = false;
        _error = 'Product detail is missing required data. Please reopen this product.';
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
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _product = product;
      });
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
    return Scaffold(
      appBar: AppBar(title: const Text('Product')),
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
          Text(product.name, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 6),
          Text(product.categoryTitle, style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(14),
            child: product.imageUrl.isNotEmpty
                ? Image.network(
                    product.imageUrl,
                    height: 220,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) => _productImagePlaceholder(),
                  )
                : _productImagePlaceholder(),
          ),
          const SizedBox(height: 14),
          _productMetaCard(product),
          const SizedBox(height: 14),
          if (product.description.isNotEmpty) Text(product.description),
          const SizedBox(height: 18),
          Text(
            'Active listings (${product.activeOrders.length})',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          _listingControls(),
          const SizedBox(height: 8),
          if (visibleOrders.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No active listings match your filters.'),
              ),
            )
          else if (_viewMode == _viewMap)
            _listingsMap(visibleOrders, product)
          else
            ...visibleOrders.map(
              (order) => Card(
                child: ListTile(
                  leading: _productThumb(
                    order.listingImageUrl.isNotEmpty ? order.listingImageUrl : product.imageUrl,
                  ),
                  title: Text(order.productName),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '${order.direction == 'L' ? 'To Lend' : 'Wanted'} | '
                        'Collection: ${_collectionPolicyText(order.collectionPolicy)}\n'
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
                      Text('${order.currency} ${order.price.toStringAsFixed(2)} / day'),
                      if (order.deposit > 0)
                        Text('Dep ${order.currency} ${order.deposit.toStringAsFixed(2)}', style: Theme.of(context).textTheme.bodySmall),
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

  Widget _productMetaCard(ProductDetail product) {
    final attrs = [
      product.attributeOneValue,
      product.attributeTwoValue,
      product.attributeThreeValue,
      product.attributeFourValue,
      product.attributeFiveValue,
    ].where((value) => value.trim().isNotEmpty).toList(growable: false);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Product Details', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 10),
            if (product.categoryDescription.isNotEmpty)
              Text(_stripHtmlTags(product.categoryDescription)),
            if (product.tags.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: product.tags.map((tag) => Chip(label: Text(tag))).toList(growable: false),
              ),
            ],
            if (attrs.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: attrs.map((value) => Chip(label: Text(value))).toList(growable: false),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _stripHtmlTags(String htmlString) {
    final regex = RegExp(r'<[^>]*>');
    return htmlString.replaceAll(regex, '').replaceAll(RegExp(r'\s+'), ' ').trim();
  }

  Widget _metaRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text('$label: $value'),
    );
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
      child: Image.network(
        imageUrl,
        width: 52,
        height: 52,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) {
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
      height: 220,
      color: const Color(0xFFF0F3F4),
      alignment: Alignment.center,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.image_not_supported_outlined, size: 44, color: Color(0xFF7A8A93)),
          const SizedBox(height: 8),
          Text(
            'No product image',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Future<void> _showOrderDetails(OrderSummary order, ProductDetail product) async {
    final imageUrls = order.listingImageUrls.isNotEmpty
        ? order.listingImageUrls
        : (order.listingImageUrl.isNotEmpty
            ? [order.listingImageUrl]
            : (product.imageUrl.isNotEmpty ? [product.imageUrl] : const <String>[]));

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
                  Text(order.productName, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 6),
                  Text('Listing details', style: Theme.of(context).textTheme.bodySmall),
                  const SizedBox(height: 12),
                  if (imageUrls.isEmpty)
                    const SizedBox(
                      height: 200,
                      child: Center(child: Icon(Icons.inventory_2_outlined, size: 42)),
                    )
                  else
                    SizedBox(
                      height: 220,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: imageUrls.length,
                        separatorBuilder: (context, index) => const SizedBox(width: 10),
                        itemBuilder: (context, index) {
                          final url = imageUrls[index];
                          return ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: AspectRatio(
                              aspectRatio: 1.2,
                              child: Image.network(
                                url,
                                fit: BoxFit.cover,
                                errorBuilder: (context, error, stackTrace) => const ColoredBox(
                                  color: Color(0x11000000),
                                  child: Center(child: Icon(Icons.broken_image_outlined)),
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
                          Text('Listing details', style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 8),
                          _metaRow('Price per day', '${order.currency} ${order.price.toStringAsFixed(2)}'),
                          if (_hasDiscountedPricing(order))
                            _metaRow('Note', '(discounted pricing for longer rentals)'),
                          _metaRow('Deposit', order.deposit > 0 ? '${order.currency} ${order.deposit.toStringAsFixed(2)}' : '-'),
                          _metaRow('Collection policy', _collectionPolicyText(order.collectionPolicy)),
                          _metaRow('Postcode', order.postcode.isEmpty ? '-' : order.postcode),
                          _metaRow('Description', order.description.isEmpty ? '-' : order.description),
                        ],
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please log in to send an enquiry.')),
        );
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
        const SnackBar(content: Text('No available dates remain for this listing.')),
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
                  selectableDayPredicate: (day, selectedStartDay, selectedEndDay) {
                    final normalizedDay = _dateOnly(day);
                    final isBoundaryUnavailable = handoverDates.contains(normalizedDay);
                    return !blockedDates.contains(normalizedDay) &&
                        !isBoundaryUnavailable &&
                        !normalizedDay.isAfter(_lastEnquiryDate(order));
                  },
                );

                if (picked == null) {
                  return;
                }

                setDialogState(() {
                  selectedRange = DateTimeRange(
                    start: _dateOnly(picked.start),
                    end: _dateOnly(picked.end),
                  );
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
                        'Blocked dates: $blockedCount',
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
                      if (blockedCount > 0 || handoverCount > 0) ...[
                        const SizedBox(height: 4),
                        Text(
                          'Unavailable boundary dates are disabled in the calendar.',
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
                    onPressed: () => Navigator.pop(dialogContext, true),
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
            content: Text('Selected dates include blocked days or an unavailable start/end day.'),
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
    if (injectedRepository != null && injectedToken != null && injectedToken.isNotEmpty) {
      return _EnquiryDependencies(repository: injectedRepository, accessToken: injectedToken);
    }

    final storedToken = await TokenStore().getAccessToken();
    if (storedToken == null || storedToken.isEmpty) {
      return null;
    }

    final repository = injectedRepository ?? TransactionRepository(
      apiClient: ApiClient(baseUrl: AppConfig.baseUrl),
    );

    return _EnquiryDependencies(repository: repository, accessToken: storedToken);
  }

  Widget _listingControls() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SegmentedButton<String>(
          segments: const [
            ButtonSegment<String>(value: _viewList, icon: Icon(Icons.list), label: Text('List')),
            ButtonSegment<String>(value: _viewMap, icon: Icon(Icons.map_outlined), label: Text('Map')),
          ],
          selected: {_viewMode},
          onSelectionChanged: (selection) {
            final selected = selection.firstOrNull;
            if (selected == null) {
              return;
            }
            setState(() => _viewMode = selected);
          },
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            const Text('Sort:'),
            const SizedBox(width: 10),
            DropdownButton<String>(
              value: _sortBy,
              items: const [
                DropdownMenuItem(value: _sortNewest, child: Text('Newest')),
                DropdownMenuItem(value: _sortPriceAsc, child: Text('Price: Low to High')),
                DropdownMenuItem(value: _sortPriceDesc, child: Text('Price: High to Low')),
              ],
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() {
                  _sortBy = value;
                });
              },
            ),
          ],
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilterChip(
              label: const Text('Friends only'),
              selected: _friendsOnly,
              onSelected: (selected) => setState(() => _friendsOnly = selected),
            ),
            FilterChip(
              label: const Text('With deposit'),
              selected: _withDepositOnly,
              onSelected: (selected) => setState(() => _withDepositOnly = selected),
            ),
            FilterChip(
              label: const Text('Delivery available'),
              selected: _deliveryOnly,
              onSelected: (selected) => setState(() => _deliveryOnly = selected),
            ),
          ],
        ),
      ],
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
          child: Text('No mapped listings yet. Listings need latitude/longitude to appear on the map.'),
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
              options: MapOptions(
                initialCenter: center,
                initialZoom: 9,
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.sharinghub.mobile',
                ),
                MarkerLayer(
                  markers: mappedOrders.map((order) {
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
                  }).toList(growable: false),
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
    final totalLat = orders.fold<double>(0, (sum, order) => sum + (order.latitude ?? 0));
    final totalLng = orders.fold<double>(0, (sum, order) => sum + (order.longitude ?? 0));
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
      if (band.durationDays > 1 && band.pricePerDay > 0 && band.pricePerDay < order.price) {
        return true;
      }
    }
    return false;
  }

  List<OrderSummary> _visibleOrders(ProductDetail product) {
    final filtered = product.activeOrders.where((order) {
      if (_friendsOnly && order.letVisibility != 'FRIENDS') {
        return false;
      }
      if (_withDepositOnly && (order.deposit <= 0)) {
        return false;
      }
      if (_deliveryOnly && order.collectionPolicy != 'WD' && order.collectionPolicy != 'EI') {
        return false;
      }
      return true;
    }).toList(growable: false);

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
  _EnquiryDependencies({
    required this.repository,
    required this.accessToken,
  });

  final TransactionRepository repository;
  final String accessToken;
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
