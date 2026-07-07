from django import forms
from django.contrib import admin
from .models import Order, Category, CategoryAttribute, CategoryTag, Product, OrderImage, System, SiteFailure
from .models import BestPricedForCategory, BestPricedForProduct
from .models import TransactionFee, TransactionFeeBand
from simple_history.admin import SimpleHistoryAdmin
from django_summernote.admin import SummernoteModelAdmin

@admin.register(Category)
class CategoryAdmin(SummernoteModelAdmin):
    list_display = ('title', 'slug', 'image_review_status', 'create_date', 'parent_category_id')
    list_filter = ('image_review_status', 'parent_category')
    search_fields = ('title', 'slug', 'description')
    fields = (
        'title',
        'slug',
        'parent_category',
        'image',
        'image_review_status',
        'image_review_notes',
        'image_reviewed_at',
        'tags',
        'description',
    )
    filter_horizontal = ('tags',)
    summernote_fields = ('description',)

    actions = ['delete_selected']


@admin.register(CategoryAttribute)
class CategoryAttributeAdmin(admin.ModelAdmin):
    list_display = ('category', 'order', 'name', 'value_source', 'sortable', 'filterable')
    list_filter = ('value_source', 'sortable', 'filterable', 'category')
    search_fields = ('name', 'category__title')
    fields = (
        'category',
        'order',
        'name',
        'value_source',
        'sortable',
        'filterable',
        'default_filtered_value',
        'allowed_values_text',
    )


@admin.register(CategoryTag)
class CategoryTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)

@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ('name','value', 'created','amended')

@admin.register(BestPricedForCategory)
class BestPricedForCategory(admin.ModelAdmin):
    list_display = ('category_id','bestPricedBid','bestPricedBid2','bestPricedBid3','bestPricedBid4','bestPricedBid5', 'bestPricedOffer', 'bestPricedOffer2', 'bestPricedOffer3', 'bestPricedOffer4', 'bestPricedOffer5', 'created_date', 'modified_date')

@admin.register(BestPricedForProduct)
class BestPricedForProduct(admin.ModelAdmin):
    list_display = ('product', 'numberActiveOrders', 'bestPricedBid', 'bestPricedBid2','bestPricedBid3','bestPricedBid4','bestPricedBid5', 'bestPricedOffer', 'bestPricedOffer2', 'bestPricedOffer3', 'bestPricedOffer4', 'bestPricedOffer5', 'created_date', 'modified_date')

class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        category = kwargs.pop('category', None)
        super().__init__(*args, **kwargs)

        active_category = category
        if active_category is None and self.instance.pk:
            active_category = self.instance.category_id
        if active_category is None:
            raw_category_id = (
                self.initial.get('category_id')
                or self.data.get('category_id')
            )
            if raw_category_id:
                try:
                    active_category = Category.objects.get(pk=raw_category_id)
                except Category.DoesNotExist:
                    active_category = None

        field_map = {
            1: 'attribute_one_value',
            2: 'attribute_two_value',
            3: 'attribute_three_value',
            4: 'attribute_four_value',
            5: 'attribute_five_value',
        }
        for field_name in field_map.values():
            if field_name in self.fields:
                self.fields[field_name].required = False
                self.fields[field_name].widget = forms.HiddenInput()

        if active_category is None:
            return

        for definition in active_category.get_attribute_definitions():
            field_name = field_map.get(definition['order'])
            if not field_name or field_name not in self.fields:
                continue
            if definition.get('value_source') == 'listing':
                continue
            name = (definition.get('name') or '').strip()
            if not name:
                continue

            field = self.fields[field_name]
            field.label = name
            field.widget = forms.TextInput()
            field.help_text = ''

            allowed_values = definition.get('allowed_values') or []
            if allowed_values:
                field.widget = forms.Select(
                    choices=[('', f'Select {name.lower()}')] + [(value, value) for value in allowed_values]
                )
                field.help_text = 'Choose one of the configured values for this category.'
            else:
                field.widget.attrs['placeholder'] = name


@admin.register(Product)
class ProductAdmin(SummernoteModelAdmin):
    form = ProductAdminForm
    list_display = ('name','slug', 'image_review_status', 'create_date','category_id')
    list_filter = ('image_review_status', 'category_id')
    fields = (
        'name',
        'slug',
        'category_id',
        'image',
        'image_review_status',
        'image_review_notes',
        'image_reviewed_at',
        'tags',
        'description',
        'short_name',
        'risk_rating',
    )
    filter_horizontal = ('tags',)
    summernote_fields = ('description',)

    class Media:
        js = ('common/admin/product_category_attributes.js',)

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)
        category = None
        category_id = request.GET.get('category_id') or request.POST.get('category_id')
        if category_id:
            try:
                category = Category.objects.get(pk=category_id)
            except Category.DoesNotExist:
                category = None
        elif obj is not None:
            category = obj.category_id

        class RequestAwareProductForm(base_form):
            def __init__(self, *args, **inner_kwargs):
                inner_kwargs['category'] = category
                super().__init__(*args, **inner_kwargs)

        return RequestAwareProductForm

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


@admin.register(SiteFailure)
class SiteFailureAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'resolved')
    list_filter = ('resolved', 'created_at')
    search_fields = ('title', 'details')
    readonly_fields = ('title', 'details', 'context', 'created_at')
    ordering = ('-created_at',)

# admin.site.register(Order)
# admin.site.register(Category)
# admin.site.register(Product)
