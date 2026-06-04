import 'package:flutter/material.dart';

import '../models/auth_models.dart';
import '../models/catalog_models.dart';
import '../models/order_models.dart';
import '../models/transaction_models.dart';
import '../config.dart';
import '../theme.dart';
import '../services/account_repository.dart';
import '../services/auth_repository.dart';
import '../services/catalog_repository.dart';
import '../services/location_service.dart';
import '../services/order_repository.dart';
import '../services/transaction_repository.dart';
import '../services/push_notification_service.dart';
import 'account_details_screen.dart';
import 'favourites_screen.dart';
import 'login_screen.dart';
import 'inbox_screen.dart';
import 'my_orders_screen.dart';
import 'my_sharing_hub_screen.dart';
import 'my_transactions_screen.dart';
import 'notification_settings_screen.dart';
import 'payment_methods_screen.dart';
import 'product_detail_screen.dart';
import 'listing_form_screen.dart';
import 'register_screen.dart';
import 'transaction_detail_screen.dart';
import '../widgets/rentalution_app_bar_logo.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.session,
    required this.privacyNoticeAccepted,
    required this.onAcceptPrivacyNotice,
    required this.transactions,
    required this.loading,
    required this.onRefresh,
    required this.onLogout,
    required this.onOpenTransaction,
    required this.onLogin,
    required this.onBiometricLogin,
    required this.showBiometricLogin,
    required this.biometricAvailable,
    required this.biometricEnabled,
    required this.onBiometricToggle,
    required this.isDarkMode,
    required this.onThemeToggle,
    required this.authRepository,
    required this.onRegistered,
    required this.authBusy,
    required this.accessToken,
    required this.accountRepository,
    required this.orderRepository,
    required this.catalogRepository,
    required this.transactionRepository,
    required this.notificationPreferences,
    required this.onUpdateNotificationPreferences,
  });

  final bool privacyNoticeAccepted;
  final Future<void> Function() onAcceptPrivacyNotice;
  final AuthSession? session;
  final List<TransactionSummary> transactions;
  final bool loading;
  final Future<void> Function()? onRefresh;
  final Future<void> Function()? onLogout;
  final Future<void> Function(TransactionSummary tx)? onOpenTransaction;
  final Future<void> Function(String login, String password)? onLogin;
  final Future<void> Function()? onBiometricLogin;
  final bool showBiometricLogin;
  final bool biometricAvailable;
  final bool biometricEnabled;
  final Future<void> Function(bool enabled)? onBiometricToggle;
  final bool isDarkMode;
  final Future<void> Function(bool isDark)? onThemeToggle;
  final AuthRepository authRepository;
  final Future<void> Function(AuthSession session)? onRegistered;
  final bool authBusy;
  final String? accessToken;
  final AccountRepository accountRepository;
  final OrderRepository orderRepository;
  final CatalogRepository catalogRepository;
  final TransactionRepository transactionRepository;
  final NotificationPreferences notificationPreferences;
  final Future<void> Function(NotificationPreferences preferences)?
  onUpdateNotificationPreferences;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  int _selectedIndex = 0;
  double _navBarOpacity = 1.0;
  final TextEditingController _searchController = TextEditingController();
  final TextEditingController _searchLocationController =
      TextEditingController();
  final TextEditingController _browseLocationController =
      TextEditingController();
  String? _browseLocationQueryOverride;
  String? _searchLocationQueryOverride;
  bool _initialLocationResolved = false;

  List<CategorySummary> _categories = const [];
  List<ProductSummary> _browseProducts = const [];
  List<ProductSummary> _searchResults = const [];
  List<OrderSummary> _orders = const [];
  List<OrderSummary> _favouriteOrders = const [];
  List<InboxMessage> _inboxMessages = const [];

  String? _selectedCategorySlug;
  int? _selectedDistance = 10;
  String _browseSortBy = 'az';
  String _searchSortBy = 'az';
  final bool _includeZeroListings = false;

  bool _categoriesLoading = false;
  bool _browseLoading = false;
  bool _searchLoading = false;
  bool _ordersLoading = false;
  bool _favouritesLoading = false;
  bool _inboxLoading = false;
  bool _locating = false;

  // Detail page navigation state
  String?
  _detailPageType; // 'product', 'orders', 'transactions', 'inbox', 'account', 'payment', 'favourites', 'notification-settings'
  String? _selectedProductSlug;
  String? _selectedTransactionReference;
  int? _postLoginReturnIndex;
  String? _postLoginReturnDetailPageType;
  String? _postLoginReturnProductSlug;
  String? _postLoginReturnTransactionReference;

  bool get _isAuthenticated {
    final token = widget.accessToken;
    return widget.session != null && token != null && token.isNotEmpty;
  }

  int get _browseTabIndex => 1;

  int get _searchTabIndex => _isAuthenticated ? 3 : 2;

  int get _loginTabIndex => 3;

  int _mapTabIndexAfterLogin(int index) {
    if (index == 2) {
      return 3;
    }
    if (index == _loginTabIndex) {
      return 0;
    }
    return index;
  }

  void _rememberPostLoginDestination() {
    if (_isAuthenticated) {
      return;
    }
    _postLoginReturnIndex = _selectedIndex;
    _postLoginReturnDetailPageType = _detailPageType;
    _postLoginReturnProductSlug = _selectedProductSlug;
    _postLoginReturnTransactionReference = _selectedTransactionReference;
  }

  void _clearPostLoginDestination() {
    _postLoginReturnIndex = null;
    _postLoginReturnDetailPageType = null;
    _postLoginReturnProductSlug = null;
    _postLoginReturnTransactionReference = null;
  }

  bool _restorePostLoginDestination() {
    final hasDestination =
        _postLoginReturnIndex != null ||
        _postLoginReturnDetailPageType != null ||
        _postLoginReturnProductSlug != null ||
        _postLoginReturnTransactionReference != null;
    if (!hasDestination) {
      return false;
    }

    final rawIndex = _postLoginReturnIndex;
    _selectedIndex = rawIndex == null ? 0 : _mapTabIndexAfterLogin(rawIndex);
    _detailPageType = _postLoginReturnDetailPageType;
    _selectedProductSlug = _postLoginReturnProductSlug;
    _selectedTransactionReference = _postLoginReturnTransactionReference;
    _clearPostLoginDestination();
    return true;
  }

  bool _restorePreLoginDestination() {
    final hasDestination =
        _postLoginReturnIndex != null ||
        _postLoginReturnDetailPageType != null ||
        _postLoginReturnProductSlug != null ||
        _postLoginReturnTransactionReference != null;
    if (!hasDestination) {
      return false;
    }

    _selectedIndex = _postLoginReturnIndex ?? 0;
    _detailPageType = _postLoginReturnDetailPageType;
    _selectedProductSlug = _postLoginReturnProductSlug;
    _selectedTransactionReference = _postLoginReturnTransactionReference;
    _clearPostLoginDestination();
    return true;
  }

  bool get _showFilterDrawerAction {
    if (_detailPageType != null) {
      return false;
    }
    if (_selectedIndex == _searchTabIndex) {
      return true;
    }
    return _selectedIndex == _browseTabIndex && _selectedCategorySlug != null;
  }

  BottomNavigationBarItem _navItem(IconData icon, String label, bool selected) {
    final color = selected ? SharingHubPalette.accentCoral : null;
    return BottomNavigationBarItem(
      icon: Icon(icon, color: color),
      label: label,
    );
  }

  String _backendSortValue(String sortBy) {
    if (sortBy == 'az' || sortBy == 'za') {
      return 'name';
    }
    return sortBy;
  }

  List<ProductSummary> _applyLocalProductSort(
    List<ProductSummary> products,
    String sortBy,
  ) {
    final sorted = List<ProductSummary>.from(products);
    if (sortBy == 'az') {
      sorted.sort(
        (a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()),
      );
      return sorted;
    }
    if (sortBy == 'za') {
      sorted.sort(
        (a, b) => b.name.toLowerCase().compareTo(a.name.toLowerCase()),
      );
      return sorted;
    }
    return sorted;
  }

  Widget _buildSearchDistanceFilters() {
    final hasLocation = _searchLocationController.text.trim().isNotEmpty;
    const options = <int?>[null, 5, 10, 25, 50, 100];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Distance', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 6),
        SizedBox(
          width: double.infinity,
          child: DropdownButtonFormField<int?>(
            initialValue: _selectedDistance,
            isExpanded: true,
            decoration: const InputDecoration(
              contentPadding: EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 10,
              ),
            ),
            items: options
                .map(
                  (value) => DropdownMenuItem<int?>(
                    value: value,
                    child: Text(_distanceLabel(value)),
                  ),
                )
                .toList(growable: false),
            onChanged: hasLocation
                ? (value) => setState(() => _selectedDistance = value)
                : null,
          ),
        ),
        if (!hasLocation)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(
              'Add a town or postcode to enable distance filtering.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
      ],
    );
  }

  String _distanceLabel(int? value) {
    if (value == null) {
      return 'Any';
    }
    return '$value km';
  }

  String _browseDistanceHeading(String locationLabel) {
    if (locationLabel.isEmpty) {
      return 'Location is not set';
    }
    final distance = _selectedDistance;
    if (distance == null) {
      return 'Browsing within any distance of $locationLabel';
    }
    return 'Browsing within ${distance}km of $locationLabel';
  }

  Future<void> _applyHomeFilters() async {
    Navigator.of(context).pop();
    if (_selectedIndex == _searchTabIndex) {
      await _searchProducts();
      return;
    }
    final categorySlug = _selectedCategorySlug;
    if (categorySlug != null) {
      await _loadBrowseProducts(categorySlug);
    }
  }

  Widget _buildHomeFilterDrawer() {
    final isSearchFilters = _selectedIndex == _searchTabIndex;
    final selectedSort = isSearchFilters ? _searchSortBy : _browseSortBy;
    final activeLocationController = isSearchFilters
        ? _searchLocationController
        : _browseLocationController;

    return Drawer(
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
          children: [
            Text(
              isSearchFilters ? 'Search sort/filter' : 'Browse sort/filter',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 4),
            Text('Sort', style: Theme.of(context).textTheme.titleSmall),
            RadioListTile<String>(
              value: 'az',
              groupValue: selectedSort,
              title: const Text('Name (A-Z)'),
              dense: true,
              visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
              contentPadding: EdgeInsets.zero,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() {
                  if (isSearchFilters) {
                    _searchSortBy = value;
                  } else {
                    _browseSortBy = value;
                  }
                });
              },
            ),
            RadioListTile<String>(
              value: 'za',
              groupValue: selectedSort,
              title: const Text('Name (Z-A)'),
              dense: true,
              visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
              contentPadding: EdgeInsets.zero,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() {
                  if (isSearchFilters) {
                    _searchSortBy = value;
                  } else {
                    _browseSortBy = value;
                  }
                });
              },
            ),
            RadioListTile<String>(
              value: 'nearest',
              groupValue: selectedSort,
              title: const Text('Nearest first'),
              dense: true,
              visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
              contentPadding: EdgeInsets.zero,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() {
                  if (isSearchFilters) {
                    _searchSortBy = value;
                  } else {
                    _browseSortBy = value;
                  }
                });
              },
            ),
            RadioListTile<String>(
              value: 'newest',
              groupValue: selectedSort,
              title: const Text('Newest first'),
              dense: true,
              visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
              contentPadding: EdgeInsets.zero,
              onChanged: (value) {
                if (value == null) {
                  return;
                }
                setState(() {
                  if (isSearchFilters) {
                    _searchSortBy = value;
                  } else {
                    _browseSortBy = value;
                  }
                });
              },
            ),
            if (!isSearchFilters) ...[
              const SizedBox(height: 2),
              Text('Location', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 4),
              TextField(
                controller: _browseLocationController,
                textInputAction: TextInputAction.done,
                decoration: InputDecoration(
                  hintText: 'Town or postcode',
                  prefixIcon: const Icon(Icons.pin_drop_outlined),
                  suffixIcon: _locating
                      ? const Padding(
                          padding: EdgeInsets.all(12),
                          child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : IconButton(
                          onPressed: _browseLoading
                              ? null
                              : _useCurrentLocation,
                          icon: const Icon(Icons.my_location),
                          tooltip: 'Use my location',
                        ),
                  isDense: true,
                ),
                onSubmitted: (_) => _applyHomeFilters(),
                onChanged: (_) {
                  _browseLocationQueryOverride = null;
                },
              ),
            ],
            const SizedBox(height: 4),
            Text('Distance', style: Theme.of(context).textTheme.titleSmall),
            if (activeLocationController.text.trim().isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  isSearchFilters
                      ? 'Set a town or postcode on Search to enable distance filtering.'
                      : 'Set a town or postcode to enable distance filtering.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              )
            else ...[
              RadioListTile<int?>(
                value: null,
                groupValue: _selectedDistance,
                title: Text(_distanceLabel(null)),
                dense: true,
                visualDensity: const VisualDensity(
                  horizontal: -4,
                  vertical: -4,
                ),
                contentPadding: EdgeInsets.zero,
                onChanged: (value) => setState(() => _selectedDistance = value),
              ),
              RadioListTile<int?>(
                value: 5,
                groupValue: _selectedDistance,
                title: Text(_distanceLabel(5)),
                dense: true,
                visualDensity: const VisualDensity(
                  horizontal: -4,
                  vertical: -4,
                ),
                contentPadding: EdgeInsets.zero,
                onChanged: (value) => setState(() => _selectedDistance = value),
              ),
              RadioListTile<int?>(
                value: 10,
                groupValue: _selectedDistance,
                title: Text(_distanceLabel(10)),
                dense: true,
                visualDensity: const VisualDensity(
                  horizontal: -4,
                  vertical: -4,
                ),
                contentPadding: EdgeInsets.zero,
                onChanged: (value) => setState(() => _selectedDistance = value),
              ),
              RadioListTile<int?>(
                value: 25,
                groupValue: _selectedDistance,
                title: Text(_distanceLabel(25)),
                dense: true,
                visualDensity: const VisualDensity(
                  horizontal: -4,
                  vertical: -4,
                ),
                contentPadding: EdgeInsets.zero,
                onChanged: (value) => setState(() => _selectedDistance = value),
              ),
              RadioListTile<int?>(
                value: 50,
                groupValue: _selectedDistance,
                title: Text(_distanceLabel(50)),
                dense: true,
                visualDensity: const VisualDensity(
                  horizontal: -4,
                  vertical: -4,
                ),
                contentPadding: EdgeInsets.zero,
                onChanged: (value) => setState(() => _selectedDistance = value),
              ),
              RadioListTile<int?>(
                value: 100,
                groupValue: _selectedDistance,
                title: Text(_distanceLabel(100)),
                dense: true,
                visualDensity: const VisualDensity(
                  horizontal: -4,
                  vertical: -4,
                ),
                contentPadding: EdgeInsets.zero,
                onChanged: (value) => setState(() => _selectedDistance = value),
              ),
            ],
            const SizedBox(height: 4),
            FilledButton.icon(
              onPressed: _applyHomeFilters,
              icon: const Icon(Icons.check),
              label: const Text('Apply'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _loadCategories();
    _resolveInitialLocation();
    if (_isAuthenticated) {
      _loadOrders();
      _loadFavouriteOrders();
      _loadInbox();
    }
  }

  @override
  void didUpdateWidget(covariant HomeScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    final wasAuthenticated = oldWidget.session != null;
    if (wasAuthenticated != _isAuthenticated) {
      setState(() {
        if (_isAuthenticated) {
          final restored = _restorePostLoginDestination();
          if (!restored) {
            _selectedIndex = 0;
          }
        } else {
          _selectedIndex = 0;
          _clearPostLoginDestination();
        }
      });
      if (_isAuthenticated) {
        _resolveInitialLocation(force: true);
        _loadOrders();
        _loadFavouriteOrders();
        _loadInbox();
      } else {
        setState(() {
          _orders = const [];
          _ordersLoading = false;
          _favouriteOrders = const [];
          _favouritesLoading = false;
          _inboxMessages = const [];
          _inboxLoading = false;
          _searchLocationController.clear();
          _browseLocationController.clear();
          _searchLocationQueryOverride = null;
          _browseLocationQueryOverride = null;
          _initialLocationResolved = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _searchController.dispose();
    _searchLocationController.dispose();
    _browseLocationController.dispose();
    super.dispose();
  }

  Future<void> _loadCategories() async {
    setState(() {
      _categoriesLoading = true;
    });

    try {
      var categories = await widget.catalogRepository.fetchCategories(
        parentSlug: 'top',
      );
      if (categories.isEmpty) {
        categories = await widget.catalogRepository.fetchCategories();
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _categories = categories;
        _selectedCategorySlug = null;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _categoriesLoading = false;
        });
      }
    }
  }

  Future<void> _loadBrowseProducts(String categorySlug) async {
    setState(() {
      _browseLoading = true;
      _selectedCategorySlug = categorySlug;
    });

    try {
      final products = await widget.catalogRepository.fetchCategoryProducts(
        categorySlug: categorySlug,
        location: _effectiveBrowseLocation(),
        distanceKm: _selectedDistance,
        sortBy: _backendSortValue(_browseSortBy),
        includeZeroListings: _includeZeroListings,
      );
      final sortedProducts = _applyLocalProductSort(products, _browseSortBy);
      if (!mounted) {
        return;
      }
      setState(() {
        _browseProducts = sortedProducts;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _browseLoading = false;
        });
      }
    }
  }

  Future<void> _loadOrders() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }

    setState(() {
      _ordersLoading = true;
    });
    try {
      final orders = await widget.orderRepository.fetchMyOrders(
        accessToken: accessToken,
        status: 'active',
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _orders = orders;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _ordersLoading = false;
        });
      }
    }
  }

  Future<void> _loadInbox() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }

    setState(() {
      _inboxLoading = true;
    });
    try {
      final inboxMessages = await widget.transactionRepository.fetchInbox(
        accessToken: accessToken,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _inboxMessages = inboxMessages;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _inboxLoading = false;
        });
      }
    }
  }

  Future<void> _loadFavouriteOrders() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }

    setState(() {
      _favouritesLoading = true;
    });
    try {
      final orders = await widget.catalogRepository.fetchFavouriteOrders(
        accessToken: accessToken,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _favouriteOrders = orders;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _favouritesLoading = false;
        });
      }
    }
  }

  Future<void> _toggleFavouriteOrder(OrderSummary order) async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    try {
      final isFavourite = await widget.catalogRepository.toggleFavouriteOrder(
        accessToken: accessToken,
        orderId: order.id,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        if (isFavourite) {
          final exists = _favouriteOrders.any((o) => o.id == order.id);
          if (!exists) {
            _favouriteOrders = [order, ..._favouriteOrders];
          }
        } else {
          _favouriteOrders = _favouriteOrders
              .where((o) => o.id != order.id)
              .toList(growable: false);
        }
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            isFavourite ? 'Added to favourites.' : 'Removed from favourites.',
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _searchProducts() async {
    final query = _searchController.text.trim();
    if (query.isEmpty) {
      setState(() {
        _searchResults = const [];
      });
      return;
    }

    setState(() {
      _searchLoading = true;
    });

    try {
      final results = await widget.catalogRepository.searchProducts(
        query: query,
        location: _effectiveSearchLocation(),
        categorySlug: _selectedCategorySlug,
        distanceKm: _selectedDistance,
        sortBy: _backendSortValue(_searchSortBy),
      );
      final sortedResults = _applyLocalProductSort(results, _searchSortBy);
      if (!mounted) {
        return;
      }
      setState(() {
        _searchResults = sortedResults;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _searchLoading = false;
        });
      }
    }
  }

  String _effectiveBrowseLocation() {
    final override = _browseLocationQueryOverride;
    if (override != null && override.isNotEmpty) {
      return override;
    }
    return _browseLocationController.text.trim();
  }

  String _effectiveSearchLocation() {
    final override = _searchLocationQueryOverride;
    if (override != null && override.isNotEmpty) {
      return override;
    }
    return _searchLocationController.text.trim();
  }

  Future<void> _resolveInitialLocation({bool force = false}) async {
    if (_initialLocationResolved && !force) {
      return;
    }

    final accessToken = widget.accessToken;
    if (accessToken != null && accessToken.isNotEmpty) {
      try {
        final account = await widget.accountRepository.fetchAccountDetails(
          accessToken: accessToken,
        );
        if (!mounted) {
          return;
        }

        final postcode = account.postcode.trim();
        if (postcode.isNotEmpty) {
          setState(() {
            _browseLocationController.text = postcode;
            _searchLocationController.text = postcode;
            _browseLocationQueryOverride = null;
            _searchLocationQueryOverride = null;
          });
        }
      } catch (_) {
        // Profile location fallback is best-effort only.
      }
    }

    await _useCurrentLocation(silent: true, triggerRefresh: false);
    if (!mounted) {
      return;
    }
    setState(() {
      _initialLocationResolved = true;
    });
  }

  Future<void> _useCurrentLocation({
    bool silent = false,
    bool triggerRefresh = true,
  }) async {
    setState(() {
      _locating = true;
    });

    try {
      final selection = await LocationService.getCurrentLocationSelection();
      if (!mounted) {
        return;
      }
      setState(() {
        _searchLocationController.text = selection.displayLabel;
        _browseLocationController.text = selection.displayLabel;
        _searchLocationQueryOverride = selection.searchQuery;
        _browseLocationQueryOverride = selection.searchQuery;
        _browseSortBy = 'nearest';
        _searchSortBy = 'nearest';
      });

      if (triggerRefresh && _selectedCategorySlug != null) {
        await _loadBrowseProducts(_selectedCategorySlug!);
      }
      if (triggerRefresh && _searchController.text.trim().isNotEmpty) {
        await _searchProducts();
      }

      if (!mounted || silent) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Location set to ${selection.displayLabel}.')),
      );
    } catch (e) {
      if (mounted && !silent) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    } finally {
      if (mounted) {
        setState(() {
          _locating = false;
        });
      }
    }
  }

  Future<void> _openProduct(String productSlug) async {
    setState(() {
      _detailPageType = 'product';
      _selectedProductSlug = productSlug;
    });
  }

  Future<void> _amendOrder(
    OrderSummary order,
    Map<String, dynamic> fields,
  ) async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    await widget.orderRepository.amendOrder(
      accessToken: accessToken,
      orderId: order.id,
      fields: fields,
    );
    await _loadOrders();
  }

  Future<void> _cancelOrder(OrderSummary order) async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    await widget.orderRepository.cancelOrder(
      accessToken: accessToken,
      orderId: order.id,
    );
    await _loadOrders();
  }

  Future<void> _openMyOrders() async {
    setState(() {
      _detailPageType = 'orders';
    });
    await _loadOrders();
  }

  Future<void> _openListMyItem() async {
    await _openListMyItemWithPrefill();
  }

  Future<void> _openListMyItemWithPrefill({
    int? initialProductId,
    String? initialProductName,
  }) async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ListingFormScreen(
          accessToken: accessToken,
          orderRepository: widget.orderRepository,
          catalogRepository: widget.catalogRepository,
          initialProductId: initialProductId,
          initialProductName: initialProductName,
        ),
      ),
    );
    if (created == true) {
      await _loadOrders();
    }
  }

  Future<void> _openMyTransactions() async {
    setState(() {
      _detailPageType = 'transactions';
    });
  }

  Future<void> _openInbox() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    if (_inboxMessages.isEmpty && !_inboxLoading) {
      await _loadInbox();
    }
    setState(() {
      _detailPageType = 'inbox';
    });
  }

  Future<void> _openTransactionByReference(String transactionReference) async {
    setState(() {
      _detailPageType = 'transaction-detail';
      _selectedTransactionReference = transactionReference;
    });
  }

  Future<void> _openAccountDetails() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    setState(() {
      _detailPageType = 'account';
    });
  }

  Future<void> _openPaymentMethods() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    setState(() {
      _detailPageType = 'payment';
    });
  }

  Future<void> _openFavourites() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    if (_favouriteOrders.isEmpty && !_favouritesLoading) {
      await _loadFavouriteOrders();
    }
    setState(() {
      _detailPageType = 'favourites';
    });
  }

  Future<void> _openNotificationSettings() async {
    setState(() {
      _detailPageType = 'notification-settings';
    });
  }

  void _openLoginTabFromDetail() {
    _rememberPostLoginDestination();
    setState(() {
      _detailPageType = null;
      _selectedProductSlug = null;
      _selectedTransactionReference = null;
      _selectedIndex = _loginTabIndex;
    });
  }

  Future<void> _handleRefresh() async {
    await _loadCategories();
    if (_isAuthenticated) {
      final refresh = widget.onRefresh;
      if (refresh != null) {
        await refresh();
      }
      await _loadOrders();
      await _loadFavouriteOrders();
      await _loadInbox();
    }
  }

  void _closeDetailPage() {
    setState(() {
      _detailPageType = null;
      _selectedProductSlug = null;
      _selectedTransactionReference = null;
    });
  }

  Future<void> _confirmLogout() async {
    final onLogout = widget.onLogout;
    if (onLogout == null) {
      return;
    }

    final shouldLogout = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Log out?'),
          content: const Text('Do you want to log out of the app now?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Log out'),
            ),
          ],
        );
      },
    );

    if (shouldLogout == true) {
      await onLogout();
    }
  }

  Future<bool> _onWillPop() async {
    final scaffoldState = _scaffoldKey.currentState;
    if (scaffoldState?.isEndDrawerOpen ?? false) {
      Navigator.of(context).pop();
      return false;
    }

    if (_detailPageType != null) {
      _closeDetailPage();
      return false;
    }

    if (_selectedIndex == _browseTabIndex && _selectedCategorySlug != null) {
      setState(() {
        _selectedCategorySlug = null;
        _browseProducts = const [];
      });
      return false;
    }

    if (!_isAuthenticated && _selectedIndex == _loginTabIndex) {
      setState(() {
        final restored = _restorePreLoginDestination();
        if (!restored) {
          _selectedIndex = 0;
        }
      });
      return false;
    }

    if (_selectedIndex != 0) {
      setState(() {
        _selectedIndex = 0;
        _navBarOpacity = 1.0;
      });
      return false;
    }

    return true;
  }

  bool _canPopCurrentPage() {
    final scaffoldState = _scaffoldKey.currentState;
    if (scaffoldState?.isEndDrawerOpen ?? false) return true;
    if (_detailPageType != null) return true;
    if (_selectedIndex == _browseTabIndex && _selectedCategorySlug != null) {
      return true;
    }
    if (!_isAuthenticated && _selectedIndex == _loginTabIndex) return true;
    if (_selectedIndex != 0) return true;
    return false;
  }

  void _handleBackPress() {
    final scaffoldState = _scaffoldKey.currentState;
    if (scaffoldState?.isEndDrawerOpen ?? false) {
      Navigator.of(context).pop();
      return;
    }

    if (_detailPageType != null) {
      _closeDetailPage();
      return;
    }

    if (_selectedIndex == _browseTabIndex && _selectedCategorySlug != null) {
      setState(() {
        _selectedCategorySlug = null;
        _browseProducts = const [];
      });
      return;
    }

    if (!_isAuthenticated && _selectedIndex == _loginTabIndex) {
      setState(() {
        final restored = _restorePreLoginDestination();
        if (!restored) {
          _selectedIndex = 0;
        }
      });
      return;
    }

    if (_selectedIndex != 0) {
      setState(() {
        _selectedIndex = 0;
        _navBarOpacity = 1.0;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.privacyNoticeAccepted) {
      return Scaffold(
        appBar: AppBar(title: const Text('Privacy notice')),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'Before you continue',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                const Text(
                  'To use rentalution, we process your account details, listings, messages, and booking data. We may also process location data when you choose location-based features.\n\nWe use strictly necessary app storage for login/session security. Website cookies that are not strictly necessary are optional and can be accepted or rejected.',
                ),
                const SizedBox(height: 16),
                const Text('Read our policies:'),
                const SizedBox(height: 6),
                SelectableText(
                  '${AppConfig.websiteBaseUrl}/pages/privacy_policy/',
                ),
                SelectableText(
                  '${AppConfig.websiteBaseUrl}/pages/cookie_policy/',
                ),
                SelectableText(
                  '${AppConfig.websiteBaseUrl}/pages/terms_and_conditions/',
                ),
                const Spacer(),
                FilledButton(
                  onPressed: () async => widget.onAcceptPrivacyNotice(),
                  child: const Text('I understand and continue'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final appLogoAsset = widget.isDarkMode
        ? 'assets/images/logo-rentalution-dark.png'
        : 'assets/images/logo-rentalution.png';

    return PopScope(
      canPop: _canPopCurrentPage(),
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) {
          return;
        }
        _handleBackPress();
      },
      child: Scaffold(
        key: _scaffoldKey,
        appBar: AppBar(
          title: RentalutionAppBarLogo(assetPath: appLogoAsset),
          actions: [
            IconButton(
              onPressed: _categoriesLoading || widget.loading
                  ? null
                  : _handleRefresh,
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh',
            ),
            IconButton(
              onPressed: widget.onThemeToggle == null
                  ? null
                  : () => widget.onThemeToggle!(!widget.isDarkMode),
              icon: Icon(
                widget.isDarkMode ? Icons.light_mode : Icons.dark_mode,
              ),
              tooltip: widget.isDarkMode ? 'Light mode' : 'Dark mode',
            ),
            if (_showFilterDrawerAction)
              IconButton(
                onPressed: () => _scaffoldKey.currentState?.openEndDrawer(),
                icon: const Icon(Icons.tune),
                tooltip: 'Filters',
              ),
            if (_isAuthenticated)
              IconButton(
                onPressed: _confirmLogout,
                icon: const Icon(Icons.logout),
                tooltip: 'Sign out',
              ),
          ],
        ),
        endDrawer: _showFilterDrawerAction ? _buildHomeFilterDrawer() : null,
        body: NotificationListener<ScrollNotification>(
          onNotification: (notification) {
            if (notification is ScrollUpdateNotification) {
              final delta = notification.scrollDelta ?? 0;
              final metrics = notification.metrics;
              final atTop = metrics.pixels <= metrics.minScrollExtent;
              final atBottom = metrics.pixels >= metrics.maxScrollExtent;
              if ((atTop || atBottom) && _navBarOpacity != 1.0) {
                setState(() => _navBarOpacity = 1.0);
              } else if (delta > 5 && _navBarOpacity != 0.0 && !atTop) {
                setState(() => _navBarOpacity = 0.0);
              }
            }
            return false;
          },
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: sharingHubBackgroundGradient(
                  widget.isDarkMode ? Brightness.dark : Brightness.light,
                ),
              ),
            ),
            child: _buildBody(),
          ),
        ),
        bottomNavigationBar: AnimatedOpacity(
          opacity: _navBarOpacity,
          duration: const Duration(milliseconds: 250),
          child: BottomNavigationBar(
            currentIndex: _selectedIndex,
            onTap: (index) {
              setState(() {
                if (!_isAuthenticated && index == _loginTabIndex) {
                  _rememberPostLoginDestination();
                }
                // Always dismiss detail overlays before switching tabs.
                _detailPageType = null;
                _selectedProductSlug = null;
                _selectedTransactionReference = null;
                _selectedIndex = index;
                _navBarOpacity = 1.0;
              });
            },
            type: BottomNavigationBarType.fixed,
            items: _isAuthenticated
                ? [
                    _navItem(Icons.home_outlined, 'Home', _selectedIndex == 0),
                    _navItem(
                      Icons.explore_outlined,
                      'Browse',
                      _selectedIndex == 1,
                    ),
                    _navItem(
                      Icons.person_outline,
                      'My rentalution',
                      _selectedIndex == 2,
                    ),
                    _navItem(Icons.search, 'Search', _selectedIndex == 3),
                  ]
                : [
                    _navItem(Icons.home_outlined, 'Home', _selectedIndex == 0),
                    _navItem(
                      Icons.explore_outlined,
                      'Browse',
                      _selectedIndex == 1,
                    ),
                    _navItem(Icons.search, 'Search', _selectedIndex == 2),
                    _navItem(Icons.login, 'Log in', _selectedIndex == 3),
                  ],
          ),
        ),
      ),
    );
  }

  Widget _buildBody() {
    // Show detail pages if a detail page type is set
    if (_detailPageType != null) {
      switch (_detailPageType) {
        case 'product':
          return _buildProductDetailPage(_closeDetailPage);
        case 'orders':
          return _buildOrdersPage(_closeDetailPage);
        case 'transactions':
          return _buildTransactionsPage(_closeDetailPage);
        case 'inbox':
          return _buildInboxPage(_closeDetailPage);
        case 'transaction-detail':
          return _buildTransactionDetailPage(_closeDetailPage);
        case 'account':
          return _buildAccountPage(_closeDetailPage);
        case 'payment':
          return _buildPaymentPage(_closeDetailPage);
        case 'favourites':
          return _buildFavouritesPage(_closeDetailPage);
        case 'notification-settings':
          return _buildNotificationSettingsPage(_closeDetailPage);
        default:
          return const SizedBox.shrink();
      }
    }

    // Otherwise show tab content
    if (!_isAuthenticated) {
      switch (_selectedIndex) {
        case 0:
          return _buildHomeLanding();
        case 1:
          return _buildBrowse();
        case 2:
          return _buildSearch();
        case 3:
          final onLogin = widget.onLogin;
          if (onLogin == null) {
            return const SizedBox.shrink();
          }
          return LoginScreen(
            busy: widget.authBusy,
            embedded: true,
            onClose: () {
              setState(() {
                final restored = _restorePreLoginDestination();
                if (!restored) {
                  _selectedIndex = 0;
                }
              });
            },
            showBiometricLogin: widget.showBiometricLogin,
            onBiometricLogin: widget.onBiometricLogin,
            onOpenRegister: () async {
              return Navigator.of(context).push<AuthSession>(
                MaterialPageRoute(
                  builder: (_) =>
                      RegisterScreen(authRepository: widget.authRepository),
                ),
              );
            },
            onRegistered: widget.onRegistered,
            onLogin: onLogin,
          );
        default:
          return _buildHomeLanding();
      }
    }

    switch (_selectedIndex) {
      case 0:
        return _buildHomeLanding();
      case 1:
        return _buildBrowse();
      case 2:
        return MySharingHubScreen(
          onAccountAmend: _openAccountDetails,
          onOpenInbox: _openInbox,
          onOpenMyOrders: _openMyOrders,
          onOpenListMyItem: _openListMyItem,
          onOpenMyTransactions: _openMyTransactions,
          onOpenFavourites: _openFavourites,
          onOpenPaymentMethods: _openPaymentMethods,
          onOpenNotificationSettings: _openNotificationSettings,
          activeOrdersCount: _orders.length,
          favouritesCount: _favouriteOrders.length,
          biometricAvailable: widget.biometricAvailable,
          biometricEnabled: widget.biometricEnabled,
          onBiometricToggle: widget.onBiometricToggle == null
              ? null
              : (enabled) {
                  widget.onBiometricToggle!(enabled);
                },
        );
      case 3:
        return _buildSearch();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildNotificationSettingsPage(VoidCallback onClose) {
    final onUpdateNotificationPreferences =
        widget.onUpdateNotificationPreferences;
    if (onUpdateNotificationPreferences == null) {
      return const SizedBox.shrink();
    }

    return NotificationSettingsScreen(
      initialPreferences: widget.notificationPreferences,
      onSave: onUpdateNotificationPreferences,
      onBack: onClose,
    );
  }

  Widget _buildBrowse() {
    final locationLabel = _browseLocationController.text.trim();

    if (_selectedCategorySlug == null) {
      return SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_browseDistanceHeading(locationLabel)),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _locating ? null : _useCurrentLocation,
                            icon: const Icon(Icons.my_location),
                            label: const Text('Use my location'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        OutlinedButton.icon(
                          onPressed: () =>
                              _scaffoldKey.currentState?.openEndDrawer(),
                          icon: const Icon(Icons.tune),
                          label: const Text('Filters'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            _sectionTitle('Browse categories'),
            const SizedBox(height: 10),
            _buildCategoryCardsWrap(),
          ],
        ),
      );
    }
    return _buildCategoryProducts();
  }

  Widget _buildHomeLanding() {
    if (_categoriesLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    final textTheme = Theme.of(context).textTheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _sectionTitle('Why rentalution exists'),
          const SizedBox(height: 8),
          Text(
            'Borrowing from your neighbours is better for your wallet and better for the planet. rentalution connects people who need things with people who own them, nearby.',
            style: textTheme.bodyMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'Every rental follows a structured process with deposit holds, condition verification, and a clear dispute path so both sides are protected.',
            style: textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          _buildHomePill(
            icon: Icons.handshake_outlined,
            title: 'Borrow what you need',
            body:
                'Find almost any item you need from people nearby for a fraction of buying new.',
          ),
          _buildHomePill(
            icon: Icons.savings_outlined,
            title: 'Earn from what you own',
            body:
                'List items you already own and earn while they would otherwise sit unused.',
          ),
          _buildHomePill(
            icon: Icons.verified_user_outlined,
            title: 'Protected transactions',
            body:
                'Deposit holds, condition evidence and a clear returns flow protect lenders and borrowers.',
          ),
          _buildHomePill(
            icon: Icons.eco_outlined,
            title: 'Better for the planet',
            body:
                'Sharing reduces production and waste. The most sustainable item is one already made.',
          ),
          const SizedBox(height: 18),
          _sectionTitle('Common questions'),
          const SizedBox(height: 8),
          _buildFaqCard(
            question: 'Who am I renting from?',
            answer:
                'You rent directly from other users nearby. rentalution matches you and handles the transaction structure.',
          ),
          _buildFaqCard(
            question: 'Is my deposit safe?',
            answer:
                'Deposits are held as card authorisation holds and are released once both sides confirm return.',
          ),
          _buildFaqCard(
            question: 'What if something goes wrong?',
            answer:
                'The returns process supports condition evidence and includes a dispute path for fair resolution.',
          ),
          _buildFaqCard(
            question: 'What does rentalution charge?',
            answer:
                'Registration and listing are free. A small percentage fee is charged only on completed rentals.',
          ),
          const SizedBox(height: 18),
          _sectionTitle('Transparent pricing'),
          const SizedBox(height: 8),
          _buildFeeCard(
            title: 'Free',
            body:
                'Accounts are free. Listing items and sending rental enquiries are always free.',
          ),
          _buildFeeCard(
            title: 'Platform fee',
            body:
                'A small percentage fee is charged on completed rentals only.',
          ),
          _buildFeeCard(
            title: 'Deposit hold',
            body:
                'Deposits are card authorisation holds and are not captured unless needed for dispute resolution.',
          ),
          _buildFeeCard(
            title: 'No hidden fees',
            body:
                'Both sides see the full cost breakdown before confirming a rental.',
          ),
          const SizedBox(height: 18),
          _sectionTitle('Browse categories'),
          const SizedBox(height: 10),
          _buildCategoryCardsWrap(),
          const SizedBox(height: 22),
          Center(
            child: Image.asset(
              'assets/images/footer-icon.png',
              width: 56,
              height: 56,
              filterQuality: FilterQuality.high,
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildHomePill({
    required IconData icon,
    required String title,
    required String body,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: Icon(icon, color: SharingHubPalette.brandTeal),
        title: Text(title),
        subtitle: Text(body),
      ),
    );
  }

  Widget _buildFaqCard({required String question, required String answer}) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(question, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(answer, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }

  Widget _buildFeeCard({required String title, required String body}) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(body),
      ),
    );
  }

  Widget _buildCategoryCardsWrap() {
    if (_categories.isEmpty) {
      return const Card(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('No categories available yet.'),
        ),
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final screenWidth = constraints.maxWidth;

        // Determine number of columns based on screen width
        int columns;
        if (screenWidth < 900) {
          columns = 2; // 2 columns on phones and small tablets
        } else {
          columns = 3; // 3 columns on larger tablets/screens
        }

        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 1.0,
          ),
          itemCount: _categories.length,
          itemBuilder: (context, index) {
            final cat = _categories[index];
            return GestureDetector(
              onTap: () => _loadBrowseProducts(cat.slug),
              child: Card(
                elevation: 2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                  side: const BorderSide(color: Color(0xFF2EC4B6), width: 1.5),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Expanded(child: _categoryThumb(cat.imageUrl)),
                      const SizedBox(height: 8),
                      Text(
                        cat.title,
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildCategoryProducts() {
    final selectedCat = _categories
        .where((c) => c.slug == _selectedCategorySlug)
        .firstOrNull;
    final locationLabel = _browseLocationController.text.trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
          child: Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(child: Text(_browseDistanceHeading(locationLabel))),
                  IconButton(
                    onPressed: _locating ? null : _useCurrentLocation,
                    icon: const Icon(Icons.my_location),
                    tooltip: 'Use my location',
                  ),
                  IconButton(
                    onPressed: () => _scaffoldKey.currentState?.openEndDrawer(),
                    icon: const Icon(Icons.tune),
                    tooltip: 'Filters',
                  ),
                ],
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
          child: TextButton.icon(
            onPressed: () => setState(() {
              _selectedCategorySlug = null;
              _browseProducts = const [];
            }),
            icon: const Icon(Icons.arrow_back),
            label: const Text('All categories'),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Row(
            children: [
              Expanded(
                child: _sectionTitle(selectedCat?.title ?? 'Items listed'),
              ),
            ],
          ),
        ),
        Expanded(
          child: _browseLoading
              ? const Center(child: CircularProgressIndicator())
              : _browseProducts.isEmpty
              ? const Center(child: Text('No items listed in this category.'))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  itemCount: _browseProducts.length,
                  itemBuilder: (context, index) {
                    final product = _browseProducts[index];
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: _productThumb(product.imageUrl),
                      title: Text(product.name),
                      subtitle: Text(
                        product.nearestDistanceKm != null
                            ? '${product.activeOrderCount} active listings | ${product.nearestDistanceKm!.toStringAsFixed(1)} km away'
                            : '${product.activeOrderCount} active listings',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _openProduct(product.slug),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildSearch() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _sectionTitle('Search items listed'),
          const SizedBox(height: 10),
          TextField(
            controller: _searchController,
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(
              hintText: 'Search by keyword',
              prefixIcon: Icon(Icons.search),
            ),
            onSubmitted: (_) => _searchProducts(),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _searchLocationController,
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              hintText: 'Town or postcode (optional)',
              prefixIcon: const Icon(Icons.pin_drop_outlined),
              suffixIcon: _locating
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    )
                  : IconButton(
                      onPressed: _searchLoading ? null : _useCurrentLocation,
                      icon: const Icon(Icons.my_location),
                      tooltip: 'Use my location',
                    ),
            ),
            onSubmitted: (_) => _searchProducts(),
            onChanged: (_) {
              _searchLocationQueryOverride = null;
            },
          ),
          const SizedBox(height: 10),
          _buildSearchDistanceFilters(),
          const SizedBox(height: 8),
          Center(
            child: Padding(
              padding: const EdgeInsets.only(top: 8),
              child: FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: SharingHubPalette.accentCoral,
                ),
                onPressed: _searchLoading ? null : _searchProducts,
                icon: _searchLoading
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.search),
                label: const Text('Search'),
              ),
            ),
          ),
          const SizedBox(height: 18),
          Expanded(
            child: _searchLoading
                ? const Center(child: CircularProgressIndicator())
                : _searchResults.isEmpty
                ? Center(
                    child: Text(
                      'Use search to find items listed and open item pages.',
                      style: Theme.of(context).textTheme.bodyLarge,
                      textAlign: TextAlign.center,
                    ),
                  )
                : ListView.builder(
                    itemCount: _searchResults.length,
                    itemBuilder: (context, index) {
                      final product = _searchResults[index];
                      return Card(
                        child: ListTile(
                          leading: _productThumb(product.imageUrl),
                          title: Text(product.name),
                          subtitle: Text(
                            product.nearestDistanceKm != null
                                ? '${product.categoryTitle} | ${product.activeOrderCount} active listings | ${product.nearestDistanceKm!.toStringAsFixed(1)} km away'
                                : '${product.categoryTitle} | ${product.activeOrderCount} active listings',
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => _openProduct(product.slug),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String text) {
    return Text(text, style: Theme.of(context).textTheme.titleLarge);
  }

  Widget _categoryThumb(String imageUrl) {
    if (imageUrl.trim().isEmpty) {
      return const Icon(
        Icons.category_outlined,
        size: 48,
        color: Color(0xFF2E7D6B),
      );
    }

    final isDarkMode = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Container(
        color: isDarkMode ? Colors.black : Colors.grey[200],
        child: Image.network(
          imageUrl,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) {
            return const Icon(
              Icons.category_outlined,
              size: 48,
              color: Color(0xFF2E7D6B),
            );
          },
        ),
      ),
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

  // Detail page builders
  Widget _buildProductDetailPage(VoidCallback onClose) {
    if (_selectedProductSlug == null) {
      return const SizedBox.shrink();
    }
    return Stack(
      children: [
        ProductDetailScreen(
          productSlug: _selectedProductSlug,
          catalogRepository: widget.catalogRepository,
          transactionRepository: widget.transactionRepository,
          accessToken: widget.accessToken,
          searchLocation: _effectiveSearchLocation(),
          initialDistanceKm: _selectedDistance,
          onOpenListMyItem: (product) => _openListMyItemWithPrefill(
            initialProductId: product.id,
            initialProductName: product.name,
          ),
          onRequireLogin: _openLoginTabFromDetail,
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildOrdersPage(VoidCallback onClose) {
    return Stack(
      children: [
        MyOrdersScreen(
          orders: _orders,
          loading: _ordersLoading,
          onRefresh: _loadOrders,
          onListMyItem: _openListMyItem,
          onAmendOrder: _amendOrder,
          onCancelOrder: _cancelOrder,
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildTransactionsPage(VoidCallback onClose) {
    final onRefresh = widget.onRefresh;
    if (onRefresh == null) {
      return const SizedBox.shrink();
    }
    return Stack(
      children: [
        MyTransactionsScreen(
          transactions: widget.transactions,
          loading: widget.loading,
          onRefresh: onRefresh,
          onOpenTransaction: (tx) => _openTransactionByReference(tx.reference),
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInboxPage(VoidCallback onClose) {
    return Stack(
      children: [
        InboxScreen(
          messages: _inboxMessages,
          loading: _inboxLoading,
          onRefresh: _loadInbox,
          onOpenTransaction: (ref) => _openTransactionByReference(ref),
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildTransactionDetailPage(VoidCallback onClose) {
    final accessToken = widget.accessToken;
    if (accessToken == null ||
        accessToken.isEmpty ||
        _selectedTransactionReference == null) {
      return const SizedBox.shrink();
    }
    return Stack(
      children: [
        TransactionDetailScreen(
          transactionReference: _selectedTransactionReference!,
          accessToken: accessToken,
          repository: widget.transactionRepository,
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildAccountPage(VoidCallback onClose) {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return const SizedBox.shrink();
    }
    return Stack(
      children: [
        AccountDetailsScreen(
          accessToken: accessToken,
          accountRepository: widget.accountRepository,
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPaymentPage(VoidCallback onClose) {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return const SizedBox.shrink();
    }
    return Stack(
      children: [
        PaymentMethodsScreen(
          accessToken: accessToken,
          accountRepository: widget.accountRepository,
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFavouritesPage(VoidCallback onClose) {
    return Stack(
      children: [
        FavouritesScreen(
          orders: _favouriteOrders,
          loading: _favouritesLoading,
          onRefresh: _loadFavouriteOrders,
          onToggleFavourite: _toggleFavouriteOrder,
          onOpenProduct: (slug) async {
            _closeDetailPage();
            await _openProduct(slug);
          },
        ),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: Container(
            color:
                Theme.of(context).appBarTheme.backgroundColor ??
                Theme.of(context).scaffoldBackgroundColor,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back),
                      onPressed: onClose,
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
