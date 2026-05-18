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
  int _selectedIndex = 0;
  final TextEditingController _searchController = TextEditingController();
  final TextEditingController _searchLocationController = TextEditingController();

  List<CategorySummary> _categories = const [];
  List<ProductSummary> _browseProducts = const [];
  List<ProductSummary> _searchResults = const [];
  List<OrderSummary> _orders = const [];
  List<InboxMessage> _inboxMessages = const [];

  String? _selectedCategorySlug;
  int? _selectedDistance;
  String _browseSortBy = 'name';
  String _searchSortBy = 'name';
  final bool _includeZeroListings = false;

  bool _categoriesLoading = false;
  bool _browseLoading = false;
  bool _searchLoading = false;
  bool _ordersLoading = false;
  bool _inboxLoading = false;
  bool _locating = false;

  bool get _isAuthenticated {
    final token = widget.accessToken;
    return widget.session != null && token != null && token.isNotEmpty;
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
    super.dispose();
  }

  Future<void> _loadCategories() async {
    setState(() {
      _categoriesLoading = true;
    });

    try {
      var categories = await widget.catalogRepository.fetchCategories(parentSlug: 'top');
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
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
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
        location: _searchLocationController.text.trim(),
        distanceKm: _selectedDistance,
        sortBy: _browseSortBy,
        includeZeroListings: _includeZeroListings,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _browseProducts = products;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
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
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
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
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
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
        sortBy: _searchSortBy,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _searchResults = results;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
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
        const SnackBar(content: Text('Location applied to browse and search results.')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
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
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ProductDetailScreen(
          productSlug: productSlug,
          catalogRepository: widget.catalogRepository,
          transactionRepository: widget.transactionRepository,
          accessToken: widget.accessToken,
        ),
      ),
    );
  }

  Future<void> _amendOrder(OrderSummary order, Map<String, dynamic> fields) async {
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
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MyOrdersScreen(
          orders: _orders,
          loading: _ordersLoading,
          onRefresh: _loadOrders,
          onAmendOrder: _amendOrder,
          onCancelOrder: _cancelOrder,
        ),
      ),
    );
    await _loadOrders();
  }

  Future<void> _openMyTransactions() async {
    final onRefresh = widget.onRefresh;
    final onOpenTransaction = widget.onOpenTransaction;
    if (onRefresh == null || onOpenTransaction == null) {
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MyTransactionsScreen(
          transactions: widget.transactions,
          loading: widget.loading,
          onRefresh: onRefresh,
          onOpenTransaction: onOpenTransaction,
        ),
      ),
    );
  }

  Future<void> _openInbox() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    if (_inboxMessages.isEmpty && !_inboxLoading) {
      await _loadInbox();
    }
    if (!mounted) {
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => InboxScreen(
          messages: _inboxMessages,
          loading: _inboxLoading,
          onRefresh: _loadInbox,
          onOpenTransaction: _openTransactionByReference,
        ),
      ),
    );
    await _loadInbox();
  }

  Future<void> _openTransactionByReference(String transactionReference) async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TransactionDetailScreen(
          transactionReference: transactionReference,
          accessToken: accessToken,
          repository: widget.transactionRepository,
        ),
      ),
    );
  }

  Future<void> _openAccountDetails() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AccountDetailsScreen(
          accessToken: accessToken,
          accountRepository: widget.accountRepository,
        ),
      ),
    );
  }

  Future<void> _openPaymentMethods() async {
    final accessToken = widget.accessToken;
    if (accessToken == null || accessToken.isEmpty) {
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PaymentMethodsScreen(
          accessToken: accessToken,
          accountRepository: widget.accountRepository,
        ),
      ),
    );
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Image.asset(
          'assets/images/logo-sharing-hub.png',
          height: 48,
          fit: BoxFit.contain,
        ),
        actions: [
          IconButton(
            onPressed: _categoriesLoading || widget.loading ? null : _handleRefresh,
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
          if (_isAuthenticated)
            IconButton(
              onPressed: widget.onLogout,
              icon: const Icon(Icons.logout),
              tooltip: 'Sign out',
            ),
        ],
      ),
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
          setState(() => _selectedIndex = index);
        },
        type: BottomNavigationBarType.fixed,
        items: _isAuthenticated
            ? const [
                BottomNavigationBarItem(icon: Icon(Icons.explore_outlined), label: 'Browse'),
                BottomNavigationBarItem(icon: Icon(Icons.person_outline), label: 'My Sharing-Hub'),
                BottomNavigationBarItem(icon: Icon(Icons.search), label: 'Search'),
              ]
            : const [
                BottomNavigationBarItem(icon: Icon(Icons.explore_outlined), label: 'Browse'),
                BottomNavigationBarItem(icon: Icon(Icons.search), label: 'Search'),
                BottomNavigationBarItem(icon: Icon(Icons.login), label: 'Log in'),
              ],
      ),
    );
  }

  Widget _buildBody() {
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
                  builder: (_) => RegisterScreen(authRepository: widget.authRepository),
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
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
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
    final selectedCat = _categories.where((c) => c.slug == _selectedCategorySlug).firstOrNull;
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
              Expanded(child: _sectionTitle(selectedCat?.title ?? 'Items listed')),
              const SizedBox(width: 8),
              const Text('Sort:'),
              const SizedBox(width: 4),
              DropdownButton<String>(
                value: _browseSortBy,
                isDense: true,
                items: const [
                  DropdownMenuItem(value: 'name', child: Text('Name')),
                  DropdownMenuItem(value: 'newest', child: Text('Newest')),
                  DropdownMenuItem(value: 'nearest', child: Text('Nearest')),
                ],
                onChanged: (value) async {
                  if (value == null) return;
                  setState(() => _browseSortBy = value);
                  if (_selectedCategorySlug != null) {
                    await _loadBrowseProducts(_selectedCategorySlug!);
                  }
                },
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
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
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
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Text('Distance:'),
              const SizedBox(width: 12),
              DropdownButton<int?>(
                value: _selectedDistance,
                items: const [
                  DropdownMenuItem<int?>(value: null, child: Text('Any distance')),
                  DropdownMenuItem<int?>(value: 5, child: Text('5 km')),
                  DropdownMenuItem<int?>(value: 10, child: Text('10 km')),
                  DropdownMenuItem<int?>(value: 25, child: Text('25 km')),
                  DropdownMenuItem<int?>(value: 50, child: Text('50 km')),
                  DropdownMenuItem<int?>(value: 100, child: Text('100 km')),
                ]
                    .toList(growable: false),
                onChanged: (value) {
                  setState(() {
                    _selectedDistance = value;
                  });
                },
              ),
              const SizedBox(width: 12),
              const Text('Sort:'),
              const SizedBox(width: 8),
              DropdownButton<String>(
                value: _searchSortBy,
                items: const [
                  DropdownMenuItem(value: 'name', child: Text('Name')),
                  DropdownMenuItem(value: 'newest', child: Text('Newest')),
                  DropdownMenuItem(value: 'nearest', child: Text('Nearest first')),
                ],
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _searchSortBy = value;
                  });
                },
              ),
              const Spacer(),
              ElevatedButton.icon(
                onPressed: _searchLoading ? null : _searchProducts,
                icon: const Icon(Icons.search),
                label: const Text('Search'),
              ),
            ],
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
    return Text(
      text,
      style: Theme.of(context).textTheme.titleLarge,
    );
  }

  String _stripHtmlTags(String htmlString) {
    final regex = RegExp(r'<[^>]*>');
    return htmlString.replaceAll(regex, '').replaceAll(RegExp(r'\s+'), ' ').trim();
  }

  Widget _categoryThumb(String imageUrl) {
    if (imageUrl.trim().isEmpty) {
      return const Icon(Icons.category_outlined, size: 48, color: Color(0xFF2E7D6B));
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Image.network(
        imageUrl,
        width: 56,
        height: 56,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) {
          return const Icon(Icons.category_outlined, size: 48, color: Color(0xFF2E7D6B));
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
}
