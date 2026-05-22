import 'package:flutter/material.dart';

import '../models/auth_models.dart';
import '../models/catalog_models.dart';
import '../models/order_models.dart';
import '../models/transaction_models.dart';
import '../services/account_repository.dart';
import '../services/auth_repository.dart';
import '../services/catalog_repository.dart';
import '../services/location_service.dart';
import '../services/order_repository.dart';
import '../services/transaction_repository.dart';
import 'account_details_screen.dart';
import 'login_screen.dart';
import 'inbox_screen.dart';
import 'my_orders_screen.dart';
import 'my_sharing_hub_screen.dart';
import 'my_transactions_screen.dart';
import 'payment_methods_screen.dart';
import 'product_detail_screen.dart';
import 'register_screen.dart';
import 'transaction_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.session,
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
  });

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

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  int _selectedIndex = 0;
  final TextEditingController _searchController = TextEditingController();
  final TextEditingController _searchLocationController =
      TextEditingController();
  final TextEditingController _browseLocationController =
      TextEditingController();

  List<CategorySummary> _categories = const [];
  List<ProductSummary> _browseProducts = const [];
  List<ProductSummary> _searchResults = const [];
  List<OrderSummary> _orders = const [];
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
  bool _inboxLoading = false;
  bool _locating = false;

  // Detail page navigation state
  String?
  _detailPageType; // 'product', 'orders', 'transactions', 'inbox', 'account', 'payment'
  String? _selectedProductSlug;
  String? _selectedTransactionReference;

  bool get _isAuthenticated {
    final token = widget.accessToken;
    return widget.session != null && token != null && token.isNotEmpty;
  }

  int get _searchTabIndex => _isAuthenticated ? 2 : 1;

  bool get _showFilterDrawerAction {
    if (_detailPageType != null) {
      return false;
    }
    if (_selectedIndex == _searchTabIndex) {
      return true;
    }
    return _selectedIndex == 0 && _selectedCategorySlug != null;
  }

  void _openFilterMenu() {
    _scaffoldKey.currentState?.openEndDrawer();
  }

  Widget _buildQuickFilterButtons() {
    const compactPadding = EdgeInsets.symmetric(horizontal: 8, vertical: 4);
    return OutlinedButton(
      onPressed: _openFilterMenu,
      style: OutlinedButton.styleFrom(
        visualDensity: VisualDensity.compact,
        padding: compactPadding,
        minimumSize: Size.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.tune, size: 14),
          SizedBox(width: 4),
          Text('Sort/Filter'),
        ],
      ),
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
            value: _selectedDistance,
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
    if (_isAuthenticated) {
      _loadOrders();
      _loadInbox();
    }
  }

  @override
  void didUpdateWidget(covariant HomeScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    final wasAuthenticated = oldWidget.session != null;
    if (wasAuthenticated != _isAuthenticated) {
      setState(() {
        _selectedIndex = 0;
      });
      if (_isAuthenticated) {
        _loadOrders();
        _loadInbox();
      } else {
        setState(() {
          _orders = const [];
          _ordersLoading = false;
          _inboxMessages = const [];
          _inboxLoading = false;
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
        location: _browseLocationController.text.trim(),
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
        location: _searchLocationController.text.trim(),
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

  Future<void> _useCurrentLocation() async {
    setState(() {
      _locating = true;
    });

    try {
      final locationLabel = await LocationService.getCurrentLocationLabel();
      if (!mounted) {
        return;
      }
      setState(() {
        _searchLocationController.text = locationLabel;
        _browseLocationController.text = locationLabel;
        _browseSortBy = 'nearest';
        _searchSortBy = 'nearest';
      });
      if (_selectedCategorySlug != null) {
        await _loadBrowseProducts(_selectedCategorySlug!);
      }
      if (_searchController.text.trim().isNotEmpty) {
        await _searchProducts();
      }
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Location applied to browse and search results.'),
        ),
      );
    } catch (e) {
      if (mounted) {
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

  void _openLoginTabFromDetail() {
    setState(() {
      _detailPageType = null;
      _selectedProductSlug = null;
      _selectedTransactionReference = null;
      _selectedIndex = 2;
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

  @override
  Widget build(BuildContext context) {
    final appLogoAsset = widget.isDarkMode
        ? 'assets/images/logo-sharing-hub-dark.png'
        : 'assets/images/logo-sharing-hub.png';

    return Scaffold(
      key: _scaffoldKey,
      appBar: AppBar(
        title: Image.asset(appLogoAsset, height: 48, fit: BoxFit.contain),
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
            icon: Icon(widget.isDarkMode ? Icons.light_mode : Icons.dark_mode),
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
              onPressed: widget.onLogout,
              icon: const Icon(Icons.logout),
              tooltip: 'Sign out',
            ),
        ],
      ),
      endDrawer: _showFilterDrawerAction ? _buildHomeFilterDrawer() : null,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: widget.isDarkMode
                ? const [Color(0xFF0F1419), Color(0xFF1A2332)]
                : const [Color(0xFFF8F4EE), Color(0xFFF1FAF8)],
          ),
        ),
        child: _buildBody(),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() {
            // Always dismiss detail overlays before switching tabs.
            _detailPageType = null;
            _selectedProductSlug = null;
            _selectedTransactionReference = null;
            _selectedIndex = index;
          });
        },
        type: BottomNavigationBarType.fixed,
        items: _isAuthenticated
            ? const [
                BottomNavigationBarItem(
                  icon: Icon(Icons.explore_outlined),
                  label: 'Browse',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.person_outline),
                  label: 'My Sharing-Hub',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.search),
                  label: 'Search',
                ),
              ]
            : const [
                BottomNavigationBarItem(
                  icon: Icon(Icons.explore_outlined),
                  label: 'Browse',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.search),
                  label: 'Search',
                ),
                BottomNavigationBarItem(
                  icon: Icon(Icons.login),
                  label: 'Log in',
                ),
              ],
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
        default:
          return const SizedBox.shrink();
      }
    }

    // Otherwise show tab content
    if (!_isAuthenticated) {
      switch (_selectedIndex) {
        case 0:
          return _buildBrowse();
        case 1:
          return _buildSearch();
        case 2:
          final onLogin = widget.onLogin;
          if (onLogin == null) {
            return const SizedBox.shrink();
          }
          return LoginScreen(
            busy: widget.authBusy,
            embedded: true,
            onClose: () {
              setState(() {
                _selectedIndex = 0;
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
          return _buildBrowse();
      }
    }

    switch (_selectedIndex) {
      case 0:
        return _buildBrowse();
      case 1:
        return MySharingHubScreen(
          onAccountAmend: _openAccountDetails,
          onOpenInbox: _openInbox,
          onOpenMyOrders: _openMyOrders,
          onOpenMyTransactions: _openMyTransactions,
          onOpenPaymentMethods: _openPaymentMethods,
          activeOrdersCount: _orders.length,
          biometricAvailable: widget.biometricAvailable,
          biometricEnabled: widget.biometricEnabled,
          onBiometricToggle: widget.onBiometricToggle == null
              ? null
              : (enabled) {
                  widget.onBiometricToggle!(enabled);
                },
        );
      case 2:
        return _buildSearch();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildBrowse() {
    if (_selectedCategorySlug == null) {
      return _buildCategoryGrid();
    }
    return _buildCategoryProducts();
  }

  Widget _buildCategoryGrid() {
    if (_categoriesLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 200,
        mainAxisSpacing: 14,
        crossAxisSpacing: 14,
        childAspectRatio: 1.0,
      ),
      itemCount: _categories.length,
      itemBuilder: (context, index) {
        final cat = _categories[index];
        return GestureDetector(
          onTap: () => _loadBrowseProducts(cat.slug),
          child: Card(
            elevation: 3,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _categoryThumb(cat.imageUrl),
                const SizedBox(height: 12),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: Text(
                    cat.title,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                if (cat.description.trim().isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    child: Text(
                      _stripHtmlTags(cat.description),
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildCategoryProducts() {
    final selectedCat = _categories
        .where((c) => c.slug == _selectedCategorySlug)
        .firstOrNull;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
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
              _buildQuickFilterButtons(),
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
          Align(
            alignment: Alignment.centerRight,
            child: _buildQuickFilterButtons(),
          ),
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
          ),
          const SizedBox(height: 10),
          _buildSearchDistanceFilters(),
          const SizedBox(height: 8),
          Center(
            child: Padding(
              padding: const EdgeInsets.only(top: 8),
              child: FilledButton.icon(
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

  String _stripHtmlTags(String htmlString) {
    final regex = RegExp(r'<[^>]*>');
    return htmlString
        .replaceAll(regex, '')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
  }

  Widget _categoryThumb(String imageUrl) {
    if (imageUrl.trim().isEmpty) {
      return const Icon(
        Icons.category_outlined,
        size: 48,
        color: Color(0xFF2E7D6B),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Image.network(
        imageUrl,
        width: 56,
        height: 56,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) {
          return const Icon(
            Icons.category_outlined,
            size: 48,
            color: Color(0xFF2E7D6B),
          );
        },
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
          searchLocation: _searchLocationController.text.trim(),
          initialDistanceKm: _selectedDistance,
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
}
