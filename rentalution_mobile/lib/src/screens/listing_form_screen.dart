import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../models/catalog_models.dart';
import '../models/order_models.dart';
import '../services/catalog_repository.dart';
import '../services/order_repository.dart';

class ListingFormScreen extends StatefulWidget {
  const ListingFormScreen({
    super.key,
    required this.accessToken,
    required this.orderRepository,
    required this.catalogRepository,
    this.existingOrder,
    this.initialProductId,
    this.initialProductName,
  });

  final String accessToken;
  final OrderRepository orderRepository;
  final CatalogRepository catalogRepository;
  final OrderSummary? existingOrder;
  final int? initialProductId;
  final String? initialProductName;

  bool get isEdit => existingOrder != null;

  @override
  State<ListingFormScreen> createState() => _ListingFormScreenState();
}

class _ListingFormScreenState extends State<ListingFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _imagePicker = ImagePicker();
  final _productSearchController = TextEditingController();

  final _priceController = TextEditingController();
  final _postcodeController = TextEditingController();
  final _radiusController = TextEditingController(text: '10');
  final _depositController = TextEditingController();
  final _matesRatesController = TextEditingController();
  final _matesDepositController = TextEditingController();
  final _deliveryCostController = TextEditingController();
  final _deliveryWithinKmController = TextEditingController();
  final _deliveryCostPerKmController = TextEditingController();
  final _deliverySummaryController = TextEditingController();
  final _band1DaysController = TextEditingController(text: '3');
  final _band1PriceController = TextEditingController();
  final _band2DaysController = TextEditingController(text: '7');
  final _band2PriceController = TextEditingController();
  final _band3DaysController = TextEditingController(text: '14');
  final _band3PriceController = TextEditingController();
  final _collectionDetailsController = TextEditingController();
  final _collectionAddressController = TextEditingController();
  final _collectionPostcodeController = TextEditingController();
  final _maxRentalDaysController = TextEditingController(text: '7');
  final _descriptionController = TextEditingController();
  final _additionalCommentsController = TextEditingController();

  DateTime? _expiryDate;
  String _letVisibility = 'BOTH';
  bool _verifiedUsersOnly = false;
  String _collectionPolicy = 'MC';

  bool _saving = false;
  bool _searchingProducts = false;
  bool _collectionIsNotHomeAddress = false;
  Timer? _productSearchDebounce;

  int _currentStep = 0;
  Set<int> _availableWeekdays = {1, 2, 3, 4, 5, 6, 7};
  final List<XFile> _pickedImages = [];

  List<ProductSummary> _productSearchResults = const [];
  int? _selectedProductId;
  String _selectedProductName = '';
  String? _productSearchStatus;
  String? _validationSummary;

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

  @override
  void initState() {
    super.initState();
    _initFromExistingOrder();
  }

  void _initFromExistingOrder() {
    final order = widget.existingOrder;
    if (order == null) {
      final initialProductId = widget.initialProductId;
      final initialProductName = (widget.initialProductName ?? '').trim();
      if (initialProductId != null && initialProductName.isNotEmpty) {
        _selectedProductId = initialProductId;
        _selectedProductName = initialProductName;
        _productSearchController.text = initialProductName;
        _productSearchStatus =
            'Using selected product: $initialProductName. You can clear this to choose another item.';
      }
      _expiryDate = DateTime.now().add(const Duration(days: 30));
      return;
    }

    _priceController.text = order.price.toStringAsFixed(2);
    _postcodeController.text = order.postcode;
    _radiusController.text = order.radiusKm.toString();
    _depositController.text = order.deposit > 0
        ? order.deposit.toStringAsFixed(2)
        : '';
    _matesRatesController.text = order.matesRates > 0
        ? order.matesRates.toStringAsFixed(2)
        : '';
    _matesDepositController.text = order.matesDeposit > 0
        ? order.matesDeposit.toStringAsFixed(2)
        : '';
    _deliveryCostController.text = order.deliveryCost > 0
        ? order.deliveryCost.toStringAsFixed(2)
        : '';
    _deliveryWithinKmController.text = order.deliveryWithinKm == null
        ? ''
        : order.deliveryWithinKm.toString();
    _deliveryCostPerKmController.text = order.deliveryCostPerKm == null
        ? ''
        : order.deliveryCostPerKm!.toStringAsFixed(2);
    _deliverySummaryController.text = _buildDeliverySummaryText();
    _collectionIsNotHomeAddress = !order.collectionIsHomeAddress;
    _collectionAddressController.text = order.collectionAddress;
    _collectionPostcodeController.text = order.collectionPostcode;

    _availableWeekdays = _extractAvailabilityDays(order.collectionDetails);
    _collectionDetailsController.text = _stripAvailabilityMarker(
      order.collectionDetails,
    );

    _maxRentalDaysController.text = order.maxRentalDays > 0
        ? order.maxRentalDays.toString()
        : '7';
    if (order.priceBands.isNotEmpty) {
      final bands = order.priceBands.take(3).toList(growable: false);
      if (bands.isNotEmpty) {
        _band1DaysController.text = bands[0].durationDays.toString();
        _band1PriceController.text = bands[0].pricePerDay.toStringAsFixed(2);
      }
      if (bands.length > 1) {
        _band2DaysController.text = bands[1].durationDays.toString();
        _band2PriceController.text = bands[1].pricePerDay.toStringAsFixed(2);
      }
      if (bands.length > 2) {
        _band3DaysController.text = bands[2].durationDays.toString();
        _band3PriceController.text = bands[2].pricePerDay.toStringAsFixed(2);
      }
    }
    _descriptionController.text = order.description;
    _additionalCommentsController.text = order.additionalComments;
    _letVisibility = order.letVisibility.isNotEmpty
        ? order.letVisibility
        : 'BOTH';
    _verifiedUsersOnly = order.verifiedUsersOnly;
    _collectionPolicy = order.collectionPolicy.isNotEmpty
        ? order.collectionPolicy
        : 'MC';
    _expiryDate =
        order.expiryDate ?? DateTime.now().add(const Duration(days: 30));

    _selectedProductId = order.productId;
    _selectedProductName = order.productName;
  }

  Future<void> _searchProductsForListing() async {
    final query = _productSearchController.text.trim();
    if (query.length < 2) {
      setState(() {
        _productSearchResults = const [];
        _productSearchStatus = 'Type at least 2 characters to search items.';
      });
      return;
    }

    setState(() {
      _searchingProducts = true;
    });

    try {
      final results = await widget.catalogRepository.searchProducts(
        query: query,
        includeZeroListings: true,
        sortBy: 'name',
      );
      if (!mounted) {
        return;
      }
      final resultCount = results.length;
      String status;
      if (resultCount == 0) {
        status = 'No products found for "$query".';
      } else if (resultCount == 1) {
        status =
            '1 product found for "$query". Tap it below to confirm selection.';
      } else {
        status =
            '$resultCount products found for "$query". Please choose the right one below.';
      }
      setState(() {
        _productSearchResults = results;
        _productSearchStatus = status;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Product search failed: $e')));
        setState(() {
          _productSearchStatus = 'Product search failed. Please try again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _searchingProducts = false;
        });
      }
    }
  }

  void _scheduleProductSearch() {
    _productSearchDebounce?.cancel();
    _productSearchDebounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted || widget.isEdit) {
        return;
      }
      _searchProductsForListing();
    });
  }

  bool _validateStep(int stepIndex) {
    if (stepIndex == 0) {
      if (!widget.isEdit && _selectedProductId == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please search and select an item.')),
        );
        return false;
      }
      return true;
    }

    if (stepIndex == 1) {
      final price = double.tryParse(_priceController.text.trim());
      final maxRentalDays = int.tryParse(_maxRentalDaysController.text.trim());
      if (price == null || price <= 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Price per day is required.')),
        );
        return false;
      }
      if (maxRentalDays == null || maxRentalDays < 1) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Maximum rental days is required.')),
        );
        return false;
      }
      return true;
    }

    if (stepIndex == 2) {
      final postcode = _postcodeController.text.trim();
      final radiusKm = int.tryParse(_radiusController.text.trim());
      if (postcode.isEmpty) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Postcode is required.')));
        return false;
      }
      if (radiusKm == null || radiusKm < 1) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Maximum let radius is required.')),
        );
        return false;
      }
      if (_expiryDate == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please choose an expiry date.')),
        );
        return false;
      }
      return true;
    }

    return true;
  }

  List<String> _collectValidationMessages() {
    final messages = <String>[];
    if (!widget.isEdit && _selectedProductId == null) {
      messages.add('Select a product.');
    }
    if (double.tryParse(_priceController.text.trim()) == null ||
        double.tryParse(_priceController.text.trim())! <= 0) {
      messages.add('Enter a valid price per day.');
    }
    if (int.tryParse(_maxRentalDaysController.text.trim()) == null ||
        int.tryParse(_maxRentalDaysController.text.trim())! < 1) {
      messages.add('Enter maximum rental days.');
    }
    if (_postcodeController.text.trim().isEmpty) {
      messages.add('Add a postcode.');
    }
    if (_expiryDate == null) {
      messages.add('Choose an expiry date.');
    }
    if (_collectionIsNotHomeAddress &&
        _collectionAddressController.text.trim().isEmpty) {
      messages.add('Enter a collection address.');
    }
    if (_collectionIsNotHomeAddress &&
        _collectionPostcodeController.text.trim().isEmpty) {
      messages.add('Enter a collection postcode.');
    }
    return messages;
  }

  void _clearValidationSummary() {
    if (_validationSummary == null) {
      return;
    }
    setState(() {
      _validationSummary = null;
    });
  }

  Future<void> _pickExpiryDate() async {
    final now = DateTime.now();
    final initial = _expiryDate ?? now.add(const Duration(days: 30));
    final picked = await showDatePicker(
      context: context,
      firstDate: now,
      lastDate: now.add(const Duration(days: 365 * 2)),
      initialDate: initial,
    );
    if (picked != null && mounted) {
      setState(() => _expiryDate = picked);
    }
  }

  Future<void> _pickImages() async {
    final files = await _imagePicker.pickMultiImage(
      imageQuality: 88,
      maxWidth: 2400,
    );
    if (!mounted || files.isEmpty) {
      return;
    }

    final existingPaths = _pickedImages.map((f) => f.path).toSet();
    setState(() {
      for (final file in files) {
        if (!existingPaths.contains(file.path)) {
          _pickedImages.add(file);
        }
      }
    });
  }

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

  String _collectionDetailsWithAvailability() {
    final details = _stripAvailabilityMarker(_collectionDetailsController.text);
    final days = _availableWeekdays.toList()..sort();

    if (days.length == 7) {
      return details;
    }

    final dayLabels = days
        .map((day) => _weekdayLabels[day] ?? '')
        .where((label) => label.isNotEmpty)
        .join(', ');
    final availabilityLine = '$_availabilityMarker $dayLabels';

    if (details.isEmpty) {
      return availabilityLine;
    }
    return '$details\n$availabilityLine';
  }

  bool get _canIncludeDeliveryInfo => _collectionPolicy != 'MC';

  String _buildDeliverySummaryText() {
    if (_collectionPolicy == 'MC') {
      return 'You must collect only';
    }
    final parts = <String>[
      _collectionPolicy == 'WD' ? 'Lender delivers' : 'Collection or delivery',
    ];
    final withinKm = _deliveryWithinKmController.text.trim();
    final perKm = _deliveryCostPerKmController.text.trim();
    final flat = _deliveryCostController.text.trim();
    if (withinKm.isNotEmpty) {
      parts.add('up to $withinKm km');
    }
    if (perKm.isNotEmpty && perKm != '0') {
      parts.add('£$perKm/km');
    }
    if (flat.isNotEmpty && flat != '0') {
      parts.add('flat fee £$flat');
    }
    return parts.join(' • ');
  }

  void _refreshDeliverySummary() {
    _deliverySummaryController.text = _buildDeliverySummaryText();
  }

  void _setCollectionAddressMode(bool value) {
    setState(() {
      _collectionIsNotHomeAddress = value;
      if (!value) {
        _collectionAddressController.clear();
        _collectionPostcodeController.clear();
      }
    });
  }

  Map<String, dynamic> _buildPayload() {
    final priceBands = <Map<String, dynamic>>[];
    void addBand(TextEditingController daysController, TextEditingController priceController) {
      final days = int.tryParse(daysController.text.trim()) ?? 0;
      final price = double.tryParse(priceController.text.trim()) ?? 0;
      if (days > 0 && price >= 0) {
        priceBands.add({
          'duration_days': days,
          'price_per_day': price,
        });
      }
    }

    addBand(_band1DaysController, _band1PriceController);
    addBand(_band2DaysController, _band2PriceController);
    addBand(_band3DaysController, _band3PriceController);

    final payload = <String, dynamic>{
      'price': double.parse(_priceController.text.trim()),
      'radius_km': int.tryParse(_radiusController.text.trim()) ?? 10,
      'let_visibility': _letVisibility,
      'verified_users_only': _verifiedUsersOnly,
      'collection_policy': _collectionPolicy,
      'description': _descriptionController.text.trim(),
      'additional_comments': _additionalCommentsController.text.trim(),
      'postcode': _postcodeController.text.trim(),
      'max_rental_days':
          int.tryParse(_maxRentalDaysController.text.trim()) ?? 7,
      'deposit': double.tryParse(_depositController.text.trim()) ?? 0,
      'mates_rates': double.tryParse(_matesRatesController.text.trim()) ?? 0,
      'mates_deposit':
          double.tryParse(_matesDepositController.text.trim()) ?? 0,
      'collection_details': _collectionDetailsWithAvailability(),
      'collection_is_home_address': !_collectionIsNotHomeAddress,
      'collection_address': _collectionIsNotHomeAddress
          ? _collectionAddressController.text.trim()
          : '',
      'collection_postcode': _collectionIsNotHomeAddress
          ? _collectionPostcodeController.text.trim()
          : '',
      'price_bands': priceBands,
    };

    if (_canIncludeDeliveryInfo) {
      payload['delivery_cost'] =
          double.tryParse(_deliveryCostController.text.trim()) ?? 0;
      payload['delivery_within_km'] = int.tryParse(
        _deliveryWithinKmController.text.trim(),
      );
      payload['delivery_cost_per_km'] = double.tryParse(
        _deliveryCostPerKmController.text.trim(),
      );
    } else {
      // If lender must be collected from, clear delivery metadata.
      payload['delivery_cost'] = 0;
      payload['delivery_within_km'] = null;
      payload['delivery_cost_per_km'] = null;
    }

    if (widget.isEdit) {
      if (_expiryDate != null) {
        payload['expiry_date'] = _expiryDate!.toIso8601String();
      }
    } else {
      payload['product_id'] = _selectedProductId;
      if (_expiryDate != null) {
        final date = _expiryDate!;
        payload['expiry_date'] =
            '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
      }
    }

    return payload;
  }

  void _movePickedImage(int fromIndex, int toIndex) {
    setState(() {
      final item = _pickedImages.removeAt(fromIndex);
      _pickedImages.insert(toIndex, item);
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    if (!widget.isEdit && _selectedProductId == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Choose a product first.')));
      return;
    }
    if (_expiryDate == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Choose an expiry date.')));
      return;
    }
    final validationMessages = _collectValidationMessages();
    if (validationMessages.isNotEmpty) {
      setState(() {
        _validationSummary = validationMessages.join('\n');
      });
    }

    setState(() => _saving = true);
    try {
      final payload = _buildPayload();
      late final OrderSummary order;
      if (widget.isEdit) {
        order = await widget.orderRepository.amendOrder(
          accessToken: widget.accessToken,
          orderId: widget.existingOrder!.id,
          fields: payload,
        );
      } else {
        order = await widget.orderRepository.createOrder(
          accessToken: widget.accessToken,
          fields: payload,
        );
      }

      if (_pickedImages.isNotEmpty) {
        await widget.orderRepository.uploadOrderImages(
          accessToken: widget.accessToken,
          orderId: order.id,
          imageFiles: _pickedImages
              .map((x) => File(x.path))
              .toList(growable: false),
        );
      }

      if (!mounted) {
        return;
      }
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  List<Step> _buildSteps() {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final selectedItemBackground = isDark
        ? const Color(0xFF173528)
        : const Color(0xFFE9F5EF);
    final selectedItemBorder = isDark
        ? const Color(0xFF6CC9A7)
        : const Color(0xFF2E7D6B);
    final selectedItemText = isDark
        ? const Color(0xFFE9FFF6)
        : const Color(0xFF0E3D31);

    return [
      Step(
        title: const Text('Item'),
        isActive: _currentStep >= 0,
        content: Column(
          children: [
            if (_validationSummary != null) ...[
              Card(
                color: Theme.of(context).colorScheme.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Before you continue',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(_validationSummary!),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
            ],
            if (!widget.isEdit) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Search for an item',
                  style: theme.textTheme.titleSmall,
                ),
              ),
              const SizedBox(height: 6),
              TextField(
                controller: _productSearchController,
                textInputAction: TextInputAction.search,
                maxLines: 1,
                textAlignVertical: TextAlignVertical.center,
                decoration: InputDecoration(
                  hintText: 'Type item name (e.g. ladder, drill)',
                  prefixIcon: const Icon(Icons.search),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 14,
                  ),
                  suffixIcon: _searchingProducts
                      ? const Padding(
                          padding: EdgeInsets.all(12),
                          child: SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : IconButton(
                          onPressed: _searchProductsForListing,
                          icon: const Icon(Icons.arrow_forward),
                          tooltip: 'Search',
                        ),
                ),
                onChanged: (_) {
                  _clearValidationSummary();
                  if (!widget.isEdit &&
                      _productSearchController.text.trim().length >= 2) {
                    _scheduleProductSearch();
                  } else {
                    setState(() {
                      _productSearchResults = const [];
                      _productSearchStatus =
                          'Type at least 2 characters to search items.';
                    });
                  }
                },
                onSubmitted: (_) => _searchProductsForListing(),
              ),
              const SizedBox(height: 10),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'How search works',
                        style: theme.textTheme.titleSmall,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Type at least two characters, then tap the exact item. If the list feels too broad, narrow the category first.',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              if (_productSearchStatus != null) ...[
                Text(
                  _productSearchStatus!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 8),
              ],
              if (_productSearchResults.isNotEmpty) ...[
                Text(
                  'Suggested matches',
                  style: theme.textTheme.bodySmall,
                ),
                const SizedBox(height: 8),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 240),
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: _productSearchResults.length,
                    separatorBuilder: (_, index) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final product = _productSearchResults[index];
                      return ListTile(
                        dense: true,
                        leading: CircleAvatar(
                          backgroundColor: Theme.of(
                            context,
                          ).colorScheme.surfaceContainerHighest,
                          child: const Icon(Icons.inventory_2_outlined),
                        ),
                        title: Text(
                          product.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: Text(
                          '${product.categoryTitle} • ${product.activeOrderCount} active',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        trailing: const Icon(Icons.check_circle_outline),
                        onTap: () {
                          setState(() {
                            _selectedProductId = product.id;
                            _selectedProductName = product.name;
                            _productSearchController.text = product.name;
                            _productSearchResults = const [];
                            _productSearchStatus =
                                'Selected "$_selectedProductName" for your listing.';
                          });
                        },
                      );
                    },
                  ),
                ),
                const SizedBox(height: 8),
              ],
              if (_selectedProductId != null)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: selectedItemBackground,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: selectedItemBorder),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Selected item: $_selectedProductName',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: selectedItemText,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      TextButton(
                        onPressed: () {
                          setState(() {
                            _selectedProductId = null;
                            _selectedProductName = '';
                            _productSearchStatus =
                                'Product cleared. Search to choose a product.';
                          });
                        },
                        child: const Text('Clear'),
                      ),
                    ],
                  ),
                ),
              if (_productSearchResults.isNotEmpty) ...[
                const SizedBox(height: 8),
              ],
              const SizedBox(height: 16),
            ],
            TextFormField(
              controller: _descriptionController,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Item description'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _additionalCommentsController,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Additional comments',
              ),
            ),
          ],
        ),
      ),
      Step(
        title: const Text('Pricing'),
        isActive: _currentStep >= 1,
        content: Column(
          children: [
            TextFormField(
              controller: _priceController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Price per day (GBP)',
                helperText:
                    'This is your headline rate before any longer-rental bands.',
              ),
              validator: (value) {
                final parsed = double.tryParse((value ?? '').trim());
                if (parsed == null || parsed < 0) {
                  return 'Enter a valid price';
                }
                return null;
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _depositController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(labelText: 'Deposit (GBP)'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _matesRatesController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Mates rates per day (GBP)',
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _matesDepositController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Mates deposit (GBP)',
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _maxRentalDaysController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Maximum rental duration (days)',
                helperText:
                    'If you allow rentals over 5 days, deposits must be on Visa or Mastercard credit cards.',
              ),
            ),
            const SizedBox(height: 18),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Price bands',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Optional day-based pricing for longer rentals. Leave blank if you only use a single daily price. The app will show the lowest relevant band as the rental grows.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            _buildPriceBandRow(
              label: 'Band 1',
              daysController: _band1DaysController,
              priceController: _band1PriceController,
            ),
            const SizedBox(height: 12),
            _buildPriceBandRow(
              label: 'Band 2',
              daysController: _band2DaysController,
              priceController: _band2PriceController,
            ),
            const SizedBox(height: 12),
            _buildPriceBandRow(
              label: 'Band 3',
              daysController: _band3DaysController,
              priceController: _band3PriceController,
            ),
          ],
        ),
      ),
      Step(
        title: const Text('Logistics'),
        isActive: _currentStep >= 2,
        content: Column(
          children: [
            TextFormField(
              controller: _postcodeController,
              decoration: const InputDecoration(labelText: 'Postcode'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _radiusController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Maximum let radius (km)',
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Delivery summary',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      _buildDeliverySummaryText(),
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Use this to keep collection and delivery expectations clear before you publish.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _collectionIsNotHomeAddress,
              onChanged: (value) => _setCollectionAddressMode(value ?? false),
              title: const Text('Collection is not at my home address'),
              controlAffinity: ListTileControlAffinity.leading,
            ),
            if (_collectionIsNotHomeAddress) ...[
              const SizedBox(height: 12),
              TextFormField(
                controller: _collectionAddressController,
                decoration: const InputDecoration(
                  labelText: 'Collection address',
                ),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _collectionPostcodeController,
                decoration: const InputDecoration(
                  labelText: 'Collection postcode',
                ),
              ),
            ],
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _letVisibility,
              decoration: const InputDecoration(
                labelText: 'Who can rent this listing?',
              ),
              items: const [
                DropdownMenuItem(
                  value: 'BOTH',
                  child: Text('Friends and public'),
                ),
                DropdownMenuItem(value: 'FRIENDS', child: Text('Friends only')),
                DropdownMenuItem(value: 'PUBLIC', child: Text('Public only')),
              ],
              onChanged: (value) {
                if (value != null) {
                  setState(() => _letVisibility = value);
                }
              },
            ),
            const SizedBox(height: 12),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _verifiedUsersOnly,
              onChanged: (value) {
                setState(() {
                  _verifiedUsersOnly = value ?? false;
                });
              },
              title: const Text('Verified users only'),
              subtitle: const Text(
                'Renter must have completed Stripe identity verification. This is an identity check, not a payment-card check.',
              ),
              controlAffinity: ListTileControlAffinity.leading,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _collectionPolicy,
              decoration: const InputDecoration(
                labelText: 'Collection / delivery',
              ),
              items: const [
                DropdownMenuItem(value: 'MC', child: Text('You must collect')),
                DropdownMenuItem(
                  value: 'WD',
                  child: Text('Lender will deliver'),
                ),
                DropdownMenuItem(
                  value: 'EI',
                  child: Text('Collection or delivery - to be discussed'),
                ),
              ],
              onChanged: (value) {
                if (value != null) {
                  setState(() {
                    _collectionPolicy = value;
                    _refreshDeliverySummary();
                  });
                }
              },
            ),
            if (_canIncludeDeliveryInfo) ...[
              const SizedBox(height: 12),
              TextFormField(
                controller: _deliveryWithinKmController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Deliver up to (km)',
                ),
                onChanged: (_) => setState(_refreshDeliverySummary),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _deliveryCostPerKmController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Delivery cost per km (GBP)',
                ),
                onChanged: (_) => setState(_refreshDeliverySummary),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _deliveryCostController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Flat delivery fee (GBP)',
                ),
                onChanged: (_) => setState(_refreshDeliverySummary),
              ),
            ],
            const SizedBox(height: 14),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Weekday availability',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Days selected are available for pickup/drop off.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _weekdayLabels.entries
                  .map((entry) {
                    final selected = _availableWeekdays.contains(entry.key);
                    return FilterChip(
                      label: Text(entry.value),
                      selected: selected,
                      selectedColor: const Color(0xFFE4F6EC),
                      checkmarkColor: const Color(0xFF1B7A52),
                      side: BorderSide(
                        color: selected
                            ? const Color(0xFF1B7A52)
                            : Colors.grey.shade400,
                        width: selected ? 2 : 1,
                      ),
                      labelStyle: TextStyle(
                        color: selected
                            ? const Color(0xFF165A3D)
                            : Colors.grey.shade900,
                        fontWeight: selected
                            ? FontWeight.w700
                            : FontWeight.w500,
                      ),
                      onSelected: (value) {
                        setState(() {
                          if (value) {
                            _availableWeekdays.add(entry.key);
                          } else {
                            _availableWeekdays.remove(entry.key);
                          }
                        });
                      },
                    );
                  })
                  .toList(growable: false),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _collectionDetailsController,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Collection details',
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.event_outlined),
                title: const Text('Available until'),
                subtitle: Text(
                  _expiryDate == null
                      ? 'Choose a date'
                      : '${_expiryDate!.year}-${_expiryDate!.month.toString().padLeft(2, '0')}-${_expiryDate!.day.toString().padLeft(2, '0')}',
                ),
                trailing: const Icon(Icons.edit_calendar_outlined),
                onTap: _pickExpiryDate,
              ),
            ),
          ],
        ),
      ),
      Step(
        title: const Text('Photos'),
        isActive: _currentStep >= 3,
        content: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                FilledButton.icon(
                  onPressed: _saving ? null : _pickImages,
                  icon: const Icon(Icons.photo_library_outlined),
                  label: const Text('Add photos'),
                ),
                const SizedBox(width: 10),
                Text('${_pickedImages.length} selected'),
              ],
            ),
            const SizedBox(height: 10),
            if (_pickedImages.isEmpty)
              const Text('No new photos selected yet.')
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: List.generate(_pickedImages.length, (index) {
                  final file = _pickedImages[index];
                  return Stack(
                    clipBehavior: Clip.none,
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: Image.file(
                          File(file.path),
                          width: 90,
                          height: 90,
                          fit: BoxFit.cover,
                        ),
                      ),
                      Positioned(
                        right: -8,
                        top: -8,
                        child: IconButton(
                          visualDensity: VisualDensity.compact,
                          padding: EdgeInsets.zero,
                          onPressed: () {
                            setState(() {
                              _pickedImages.removeAt(index);
                            });
                          },
                          icon: const Icon(Icons.cancel, color: Colors.red),
                        ),
                      ),
                      Positioned(
                        left: -8,
                        bottom: -8,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              visualDensity: VisualDensity.compact,
                              padding: EdgeInsets.zero,
                              onPressed: index == 0
                                  ? null
                                  : () => _movePickedImage(index, index - 1),
                              icon: const Icon(Icons.arrow_left),
                            ),
                            IconButton(
                              visualDensity: VisualDensity.compact,
                              padding: EdgeInsets.zero,
                              onPressed: index == _pickedImages.length - 1
                                  ? null
                                  : () => _movePickedImage(index, index + 1),
                              icon: const Icon(Icons.arrow_right),
                            ),
                          ],
                        ),
                      ),
                    ],
                  );
                }),
              ),
            const SizedBox(height: 14),
            Text(
              'Review and create',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 6),
            Text(
              widget.isEdit
                  ? 'Save to update your listing details and upload any selected photos.'
                  : 'Create your listing and upload selected photos in one step.',
            ),
          ],
        ),
      ),
    ];
  }

  Widget _buildPriceBandRow({
    required String label,
    required TextEditingController daysController,
    required TextEditingController priceController,
  }) {
    return Row(
      children: [
        Expanded(
          flex: 2,
          child: TextFormField(
            controller: daysController,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(labelText: '$label days'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          flex: 3,
          child: TextFormField(
            controller: priceController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: '$label price/day'),
          ),
        ),
      ],
    );
  }

  @override
  void dispose() {
    _productSearchDebounce?.cancel();
    _productSearchController.dispose();
    _priceController.dispose();
    _postcodeController.dispose();
    _radiusController.dispose();
    _depositController.dispose();
    _matesRatesController.dispose();
    _matesDepositController.dispose();
    _deliveryCostController.dispose();
    _deliveryWithinKmController.dispose();
    _deliveryCostPerKmController.dispose();
    _band1DaysController.dispose();
    _band1PriceController.dispose();
    _band2DaysController.dispose();
    _band2PriceController.dispose();
    _band3DaysController.dispose();
    _band3PriceController.dispose();
    _collectionDetailsController.dispose();
    _maxRentalDaysController.dispose();
    _descriptionController.dispose();
    _additionalCommentsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.isEdit ? 'Edit listing' : 'List my item';

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Form(
        key: _formKey,
        child: Stepper(
          type: StepperType.vertical,
          currentStep: _currentStep,
          onStepContinue: () {
            if (!_validateStep(_currentStep)) {
              return;
            }
            if (_currentStep == _buildSteps().length - 1) {
              _save();
              return;
            }
            setState(() {
              _currentStep += 1;
            });
          },
          onStepCancel: () {
            if (_currentStep == 0) {
              Navigator.of(context).maybePop();
              return;
            }
            setState(() {
              _currentStep -= 1;
            });
          },
          onStepTapped: (index) {
            if (index > _currentStep && !_validateStep(_currentStep)) {
              return;
            }
            setState(() {
              _currentStep = index;
            });
          },
          controlsBuilder: (context, details) {
            final isLast = _currentStep == _buildSteps().length - 1;
            return Row(
              children: [
                FilledButton.icon(
                  onPressed: _saving ? null : details.onStepContinue,
                  icon: _saving
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(
                          isLast
                              ? Icons.check_circle_outline
                              : Icons.arrow_forward,
                        ),
                  label: Text(
                    isLast
                        ? (widget.isEdit ? 'Save listing' : 'Create listing')
                        : 'Next',
                  ),
                ),
                const SizedBox(width: 10),
                TextButton(
                  onPressed: _saving ? null : details.onStepCancel,
                  child: Text(_currentStep == 0 ? 'Close' : 'Back'),
                ),
              ],
            );
          },
          steps: _buildSteps(),
        ),
      ),
    );
  }
}
