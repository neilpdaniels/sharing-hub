from django.contrib import admin
from .models import Order, Category, Product, OrderImage, System
from .models import BestPricedForCategory, BestPricedForProduct
from .models import TransactionFee, TransactionFeeBand
from simple_history.admin import SimpleHistoryAdmin
from django import forms

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title','slug', 'create_date','parent_category_id')

@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ('name','value', 'created','amended')

@admin.register(BestPricedForCategory)
class BestPricedForCategory(admin.ModelAdmin):
    list_display = ('category_id','bestPricedBid','bestPricedBid2','bestPricedBid3','bestPricedBid4','bestPricedBid5', 'bestPricedOffer', 'bestPricedOffer2', 'bestPricedOffer3', 'bestPricedOffer4', 'bestPricedOffer5', 'created_date', 'modified_date')

@admin.register(BestPricedForProduct)
class BestPricedForProduct(admin.ModelAdmin):
    list_display = ('product', 'numberActiveOrders', 'bestPricedBid', 'bestPricedBid2','bestPricedBid3','bestPricedBid4','bestPricedBid5', 'bestPricedOffer', 'bestPricedOffer2', 'bestPricedOffer3', 'bestPricedOffer4', 'bestPricedOffer5', 'created_date', 'modified_date')

class ProductModelForm( forms.ModelForm ):
    description = forms.CharField( widget=forms.Textarea )
    class Meta:
        model = Product
        exclude = ()

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductModelForm
    list_display = ('name','slug', 'create_date','category_id')

@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ('product_id','user','expiry_date', 'create_date','direction')

@admin.register(OrderImage)
class OrderImageAdmin(admin.ModelAdmin):
    list_display = ('order','image')

@admin.register(TransactionFee)
class TransactionFeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'fee_type')

@admin.register(TransactionFeeBand)
class TransactionFeeBandAdmin(admin.ModelAdmin):
    list_display = ('transaction_fee', 'price', 'max_weight', 'max_price')

# admin.site.register(Order)
# admin.site.register(Category)
# admin.site.register(Product)
