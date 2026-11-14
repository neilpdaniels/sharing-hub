from django import forms
from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify
from .management.commands.manage_midjourney_catalog_images import (
    DEFAULT_OPENAI_IMAGE_QUALITY,
    DEFAULT_OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_MODELS,
    OPENAI_IMAGE_QUALITIES,
    OPENAI_IMAGE_SIZE,
    generate_openai_images,
)
from .models import (
    CatalogImageCandidate, CatalogImageGeneration, Order, Category, CategoryAttribute,
    CategoryTag, Product, OrderImage, System, SiteFailure, ModerationReport,
    IMAGE_REVIEW_REVIEWED,
)
from .moderation import resolve_report
from .models import BestPricedForCategory, BestPricedForProduct
from .models import TransactionFee, TransactionFeeBand
from simple_history.admin import SimpleHistoryAdmin
from django_summernote.admin import SummernoteModelAdmin


class CatalogImageGenerationForm(forms.Form):
    prompt = forms.CharField(widget=forms.Textarea(attrs={'rows': 8, 'class': 'vLargeTextField'}))
    model = forms.ChoiceField(choices=[(key, value['label']) for key, value in OPENAI_IMAGE_MODELS.items()])
    quality = forms.ChoiceField(choices=[(value, value.title()) for value in OPENAI_IMAGE_QUALITIES])
    candidate_count = forms.TypedChoiceField(choices=((1, '1 candidate'), (2, '2 candidates')), coerce=int)


class CategoryProductImageBatchForm(forms.Form):
    SCOPE_DIRECT = 'direct'
    SCOPE_SUBTREE = 'subtree'

    scope = forms.ChoiceField(
        choices=(
            (SCOPE_DIRECT, 'Products directly in this category'),
            (SCOPE_SUBTREE, 'Products in this category and all subcategories'),
        ),
        initial=SCOPE_SUBTREE,
    )
    missing_images_only = forms.BooleanField(
        required=False,
        initial=True,
        label='Generate only for products without an image',
    )
    prompt_prefix = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'vLargeTextField'}),
        help_text='Optional style or subject instruction added before each product-specific prompt.',
    )
    model = forms.ChoiceField(choices=[(key, value['label']) for key, value in OPENAI_IMAGE_MODELS.items()])
    quality = forms.ChoiceField(choices=[(value, value.title()) for value in OPENAI_IMAGE_QUALITIES])
    candidate_count = forms.TypedChoiceField(choices=((1, '1 candidate per product'), (2, '2 candidates per product')), coerce=int)
    confirm = forms.BooleanField(
        required=True,
        label='I understand this queues paid image-generation requests and does not make any image live automatically.',
    )


class CatalogImageAdminMixin:
    """Staff UI for generating and explicitly selecting catalogue images."""

    image_generation_template = 'admin/common/catalog_image_generation.html'

    def get_urls(self):
        opts = self.model._meta
        custom_urls = [
            path(
                '<int:object_id>/generate-image/',
                self.admin_site.admin_view(self.generate_image_view),
                name=f'{opts.app_label}_{opts.model_name}_generate_image',
            ),
            path(
                '<int:object_id>/select-generated-image/<int:candidate_id>/',
                self.admin_site.admin_view(self.select_generated_image_view),
                name=f'{opts.app_label}_{opts.model_name}_select_generated_image',
            ),
        ]
        return custom_urls + super().get_urls()

    def image_generation_link(self, obj):
        if not obj or not obj.pk:
            return 'Save this item before generating images.'
        url = reverse(f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_generate_image', args=(obj.pk,))
        return format_html('<a class="button" href="{}">Generate replacement image</a>', url)

    image_generation_link.short_description = 'AI image generation'

    def _generation_queryset(self, obj):
        field = 'product' if isinstance(obj, Product) else 'category'
        return CatalogImageGeneration.objects.filter(**{field: obj}).prefetch_related('candidates')

    def _default_prompt(self, obj):
        description = ' '.join((obj.description or '').split())
        context = f' {description}' if description else ''
        return (
            f'{obj.name if isinstance(obj, Product) else obj.title}.{context} '
            'Create a realistic, trustworthy UK rental catalogue image: one clear subject, plain light background, '
            'soft studio lighting, square composition, no text, no watermark and no readable brand logos.'
        )

    def generate_image_view(self, request, object_id):
        obj = get_object_or_404(self.model, pk=object_id)
        if request.method == 'POST':
            form = CatalogImageGenerationForm(request.POST)
            if form.is_valid():
                generation = CatalogImageGeneration(
                    product=obj if isinstance(obj, Product) else None,
                    category=obj if isinstance(obj, Category) else None,
                    prompt=form.cleaned_data['prompt'].strip(),
                    model=form.cleaned_data['model'],
                    quality=form.cleaned_data['quality'],
                    size=OPENAI_IMAGE_SIZE,
                    requested_count=form.cleaned_data['candidate_count'],
                    created_by=request.user,
                )
                generation.save()
                try:
                    paths = generate_openai_images(
                        generation.prompt,
                        count=generation.requested_count,
                        model=generation.model,
                        quality=generation.quality,
                        size=generation.size,
                    )
                    for position, image_path in enumerate(paths, start=1):
                        with image_path.open('rb') as handle:
                            candidate = CatalogImageCandidate(generation=generation, position=position)
                            candidate.image.save(
                                f'{slugify(str(obj))}-{generation.pk}-{position}{image_path.suffix.lower()}',
                                ContentFile(handle.read()),
                                save=True,
                            )
                except (CommandError, OSError) as exc:
                    generation.delete()
                    self.message_user(request, f'Image generation failed: {exc}', messages.ERROR)
                else:
                    self.message_user(request, 'Image candidate(s) generated. Select one below to make it live.', messages.SUCCESS)
                    return redirect(request.path)
        else:
            form = CatalogImageGenerationForm(initial={
                'prompt': self._default_prompt(obj),
                'model': DEFAULT_OPENAI_IMAGE_MODEL,
                'quality': DEFAULT_OPENAI_IMAGE_QUALITY,
                'candidate_count': 2,
            })
        context = {
            **self.admin_site.each_context(request),
            'title': f'Generate replacement image: {obj}',
            'opts': self.model._meta,
            'original': obj,
            'form': form,
            'generations': self._generation_queryset(obj),
        }
        return render(request, self.image_generation_template, context)

    def select_generated_image_view(self, request, object_id, candidate_id):
        if request.method != 'POST':
            return redirect(reverse(f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_generate_image', args=(object_id,)))
        obj = get_object_or_404(self.model, pk=object_id)
        candidate = get_object_or_404(CatalogImageCandidate, pk=candidate_id)
        if candidate.generation.target != obj:
            self.message_user(request, 'That candidate does not belong to this catalogue item.', messages.ERROR)
            return redirect(reverse(f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_generate_image', args=(object_id,)))
        if candidate.generation.product_id:
            CatalogImageCandidate.objects.filter(
                generation__product_id=candidate.generation.product_id,
            ).update(is_selected=False)
        else:
            CatalogImageCandidate.objects.filter(
                generation__category_id=candidate.generation.category_id,
            ).update(is_selected=False)
        candidate.is_selected = True
        candidate.save(update_fields=('is_selected',))
        obj.image.name = candidate.image.name
        obj.image_review_status = IMAGE_REVIEW_REVIEWED
        obj.image_review_notes = f'AI candidate selected from generation #{candidate.generation_id}.'
        obj.image_reviewed_at = timezone.now()
        obj.save(update_fields=('image', 'image_review_status', 'image_review_notes', 'image_reviewed_at'))
        self.message_user(request, 'Selected image is now live for this catalogue item.', messages.SUCCESS)
        return redirect(reverse(f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change', args=(obj.pk,)))

@admin.register(Category)
class CategoryAdmin(CatalogImageAdminMixin, SummernoteModelAdmin):
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
        'image_generation_link',
        'generate_product_images_link',
        'review_product_images_link',
        'tags',
        'description',
    )
    readonly_fields = ('image_generation_link', 'generate_product_images_link', 'review_product_images_link')
    filter_horizontal = ('tags',)
    summernote_fields = ('description',)

    actions = ['delete_selected']

    def get_urls(self):
        custom_urls = [
            path(
                '<int:object_id>/generate-product-images/',
                self.admin_site.admin_view(self.generate_product_images_view),
                name='common_category_generate_product_images',
            ),
            path(
                '<int:object_id>/review-product-images/',
                self.admin_site.admin_view(self.review_product_images_view),
                name='common_category_review_product_images',
            ),
            path(
                '<int:object_id>/review-product-images/<int:candidate_id>/accept/',
                self.admin_site.admin_view(self.accept_product_image_candidate_view),
                name='common_category_accept_product_image_candidate',
            ),
            path(
                '<int:object_id>/review-product-images/<int:generation_id>/retry/',
                self.admin_site.admin_view(self.retry_product_image_generation_view),
                name='common_category_retry_product_image_generation',
            ),
            path(
                '<int:object_id>/review-product-images/<int:generation_id>/retry-with-changes/',
                self.admin_site.admin_view(self.retry_product_image_with_changes_view),
                name='common_category_retry_product_image_with_changes',
            ),
        ]
        return custom_urls + super().get_urls()

    def generate_product_images_link(self, obj):
        if not obj or not obj.pk:
            return 'Save this category before generating product images.'
        url = reverse('admin:common_category_generate_product_images', args=(obj.pk,))
        return format_html('<a class="button" href="{}">Generate product image candidates</a>', url)

    generate_product_images_link.short_description = 'Batch product image generation'

    def review_product_images_link(self, obj):
        if not obj or not obj.pk:
            return 'Save this category before reviewing product images.'
        url = reverse('admin:common_category_review_product_images', args=(obj.pk,))
        return format_html('<a class="button" href="{}">Review product image candidates</a>', url)

    review_product_images_link.short_description = 'Batch image review'

    @staticmethod
    def _product_category_ids(category, scope):
        if scope == CategoryProductImageBatchForm.SCOPE_DIRECT:
            return [category.id]
        children_by_parent = {}
        for child_id, parent_id in Category.objects.values_list('id', 'parent_category_id'):
            children_by_parent.setdefault(parent_id, []).append(child_id)
        category_ids = []
        pending = [category.id]
        while pending:
            category_id = pending.pop()
            category_ids.append(category_id)
            pending.extend(children_by_parent.get(category_id, []))
        return category_ids

    def _batch_products(self, category, form_data):
        category_ids = self._product_category_ids(category, form_data['scope'])
        products = Product.objects.filter(category_id__in=category_ids).order_by('category_id', 'name', 'id')
        if form_data['missing_images_only']:
            products = products.filter(image='')
        return products

    def generate_product_images_view(self, request, object_id):
        category = get_object_or_404(Category, pk=object_id)
        initial = {
            'scope': CategoryProductImageBatchForm.SCOPE_SUBTREE,
            'missing_images_only': True,
            'model': DEFAULT_OPENAI_IMAGE_MODEL,
            'quality': DEFAULT_OPENAI_IMAGE_QUALITY,
            'candidate_count': 1,
        }
        if request.method == 'POST':
            form = CategoryProductImageBatchForm(request.POST)
            if form.is_valid():
                products = list(self._batch_products(category, form.cleaned_data))
                if not products:
                    self.message_user(request, 'No products match those batch settings; no requests were queued.', messages.WARNING)
                else:
                    from navigation.tasks import generate_catalogue_product_image

                    for product in products:
                        generate_catalogue_product_image.delay(
                            product.pk,
                            prompt_prefix=form.cleaned_data['prompt_prefix'].strip(),
                            model=form.cleaned_data['model'],
                            quality=form.cleaned_data['quality'],
                            candidate_count=form.cleaned_data['candidate_count'],
                            skip_if_image_exists=form.cleaned_data['missing_images_only'],
                            requested_by_id=request.user.pk,
                        )
                    self.message_user(
                        request,
                        f'Queued {len(products)} product image generation request(s). They will appear as review candidates on each product; none will go live automatically.',
                        messages.SUCCESS,
                    )
                    return redirect(reverse('admin:common_category_change', args=(category.pk,)))
        else:
            form = CategoryProductImageBatchForm(initial=initial)

        preview_data = form.cleaned_data if form.is_bound and form.is_valid() else initial
        target_count = self._batch_products(category, preview_data).count()
        return render(request, 'admin/common/category_product_image_batch.html', {
            **self.admin_site.each_context(request),
            'title': f'Generate product image candidates: {category}',
            'opts': self.model._meta,
            'original': category,
            'form': form,
            'target_count': target_count,
        })

    def _review_category_ids(self, category):
        return self._product_category_ids(category, CategoryProductImageBatchForm.SCOPE_SUBTREE)

    def _candidate_in_category(self, category, candidate):
        return (
            candidate.generation.product_id is not None
            and candidate.generation.product.category_id_id in self._review_category_ids(category)
        )

    def review_product_images_view(self, request, object_id):
        category = get_object_or_404(Category, pk=object_id)
        category_ids = self._review_category_ids(category)
        candidates = list(
            CatalogImageCandidate.objects.filter(
                generation__product__category_id__in=category_ids,
                is_selected=False,
            ).select_related('generation', 'generation__product').order_by(
                'generation__product__name', '-created_at', '-id'
            )
        )
        products = {}
        for candidate in candidates:
            product = candidate.generation.product
            products.setdefault(product.pk, {'product': product, 'candidates': []})['candidates'].append(candidate)
        return render(request, 'admin/common/category_product_image_review.html', {
            **self.admin_site.each_context(request),
            'title': f'Review product image candidates: {category}',
            'opts': self.model._meta,
            'original': category,
            'product_reviews': products.values(),
        })

    def accept_product_image_candidate_view(self, request, object_id, candidate_id):
        category = get_object_or_404(Category, pk=object_id)
        if request.method != 'POST':
            return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))
        candidate = get_object_or_404(
            CatalogImageCandidate.objects.select_related('generation', 'generation__product'), pk=candidate_id,
        )
        if not self._candidate_in_category(category, candidate):
            self.message_user(request, 'That candidate is not in this category tree.', messages.ERROR)
            return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))
        product = candidate.generation.product
        CatalogImageCandidate.objects.filter(generation__product=product).update(is_selected=False)
        candidate.is_selected = True
        candidate.save(update_fields=('is_selected',))
        product.image.name = candidate.image.name
        product.image_review_status = IMAGE_REVIEW_REVIEWED
        product.image_review_notes = f'AI candidate selected from generation #{candidate.generation_id}.'
        product.image_reviewed_at = timezone.now()
        product.save(update_fields=('image', 'image_review_status', 'image_review_notes', 'image_reviewed_at'))
        self.message_user(request, f'Image for {product.name} is now live.', messages.SUCCESS)
        return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))

    def retry_product_image_generation_view(self, request, object_id, generation_id):
        category = get_object_or_404(Category, pk=object_id)
        if request.method != 'POST':
            return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))
        generation = get_object_or_404(
            CatalogImageGeneration.objects.select_related('product'), pk=generation_id, product__isnull=False,
        )
        if generation.product.category_id_id not in self._review_category_ids(category):
            self.message_user(request, 'That generation is not in this category tree.', messages.ERROR)
            return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))
        from navigation.tasks import retry_catalogue_product_image

        retry_catalogue_product_image.delay(generation.pk, requested_by_id=request.user.pk)
        self.message_user(request, f'Retrying {generation.product.name} with the same prompt and settings. Refresh shortly.', messages.SUCCESS)
        return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))

    def retry_product_image_with_changes_view(self, request, object_id, generation_id):
        category = get_object_or_404(Category, pk=object_id)
        generation = get_object_or_404(
            CatalogImageGeneration.objects.select_related('product'), pk=generation_id, product__isnull=False,
        )
        if generation.product.category_id_id not in self._review_category_ids(category):
            self.message_user(request, 'That generation is not in this category tree.', messages.ERROR)
            return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))
        if request.method == 'POST':
            form = CatalogImageGenerationForm(request.POST)
            if form.is_valid():
                from navigation.tasks import retry_catalogue_product_image

                retry_catalogue_product_image.delay(
                    generation.pk,
                    requested_by_id=request.user.pk,
                    prompt=form.cleaned_data['prompt'].strip(),
                    model=form.cleaned_data['model'],
                    quality=form.cleaned_data['quality'],
                    candidate_count=form.cleaned_data['candidate_count'],
                )
                self.message_user(request, f'Retrying {generation.product.name} with your revised settings. Refresh shortly.', messages.SUCCESS)
                return redirect(reverse('admin:common_category_review_product_images', args=(category.pk,)))
        else:
            form = CatalogImageGenerationForm(initial={
                'prompt': generation.prompt,
                'model': generation.model,
                'quality': generation.quality,
                'candidate_count': generation.requested_count,
            })
        return render(request, 'admin/common/category_product_image_retry.html', {
            **self.admin_site.each_context(request),
            'title': f'Retry image: {generation.product.name}',
            'opts': self.model._meta,
            'original': category,
            'generation': generation,
            'form': form,
        })


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

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        field = super().formfield_for_choice_field(db_field, request, **kwargs)
        if db_field.name == 'value_source':
            field.help_text = (
                'Use Listing for values a lender chooses for their individual item, such as size, age range or '
                'power source. Use Product only for a fixed, curated catalogue value inherited by every listing.'
            )
        return field


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
class ProductAdmin(CatalogImageAdminMixin, SummernoteModelAdmin):
    form = ProductAdminForm
    list_display = ('name','slug', 'image_review_status', 'create_date','category_id')
    list_filter = ('image_review_status', 'category_id', 'categories')
    fields = (
        'name',
        'slug',
        'category_id',
        'categories',
        'image',
        'image_review_status',
        'image_review_notes',
        'image_reviewed_at',
        'image_generation_link',
        'tags',
        'description',
        'short_name',
        'risk_rating',
    )
    readonly_fields = ('image_generation_link',)
    filter_horizontal = ('tags', 'categories')
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
    list_display = ('display_name', 'product_id','user','expiry_date', 'create_date','direction')
    search_fields = ('listing_title', 'product__name', 'user__username')


@admin.register(CatalogImageGeneration)
class CatalogImageGenerationAdmin(admin.ModelAdmin):
    list_display = ('id', 'target_label', 'model', 'quality', 'requested_count', 'created_by', 'created_at')
    list_filter = ('model', 'quality', 'created_at')
    search_fields = ('prompt', 'product__name', 'category__title')
    readonly_fields = ('product', 'category', 'prompt', 'model', 'quality', 'size', 'requested_count', 'created_by', 'created_at')


@admin.register(CatalogImageCandidate)
class CatalogImageCandidateAdmin(admin.ModelAdmin):
    list_display = ('generation', 'position', 'is_selected', 'created_at')
    list_filter = ('is_selected', 'created_at')
    readonly_fields = ('generation', 'image', 'position', 'is_selected', 'created_at')

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


@admin.register(ModerationReport)
class ModerationReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'target_type', 'target_id', 'reason', 'reporter_identity', 'target_owner', 'content_hidden_pending_review', 'status', 'outcome', 'created_at')
    list_filter = ('status', 'target_type', 'reason', 'content_hidden_pending_review', 'outcome')
    search_fields = ('reporter__username', 'target_owner__username', 'details', 'moderator_notes')
    readonly_fields = ('reporter', 'anonymous_fingerprint', 'target_owner', 'target_type', 'target_id', 'reason', 'details', 'target_snapshot', 'content_hidden_pending_review', 'created_at', 'updated_at', 'reviewed_by', 'reviewed_at', 'outcome')
    actions = ('remove_and_block_author', 'dismiss_report', 'dismiss_and_block_abusive_reporter')

    @admin.display(description='Reporter')
    def reporter_identity(self, report):
        return report.reporter.username if report.reporter else 'Anonymous visitor'

    def _resolve_selected(self, request, queryset, outcome):
        completed = 0
        for report in queryset.filter(status__in=(ModerationReport.STATUS_OPEN, ModerationReport.STATUS_REVIEWING)):
            try:
                resolve_report(report, outcome=outcome, moderator=request.user)
                completed += 1
            except Exception as exc:
                self.message_user(request, 'Report #%s was not resolved: %s' % (report.pk, exc), level='error')
        self.message_user(request, '%s report(s) resolved.' % completed)

    @admin.action(description='Confirm bad content: remove it and block posting user')
    def remove_and_block_author(self, request, queryset):
        self._resolve_selected(request, queryset, ModerationReport.OUTCOME_REMOVE_AND_BLOCK)

    @admin.action(description='Dismiss report: allow content')
    def dismiss_report(self, request, queryset):
        self._resolve_selected(request, queryset, ModerationReport.OUTCOME_DISMISS)

    @admin.action(description='Dismiss abusive report and block reporter')
    def dismiss_and_block_abusive_reporter(self, request, queryset):
        self._resolve_selected(request, queryset, ModerationReport.OUTCOME_DISMISS_AND_BLOCK_REPORTER)

# admin.site.register(Order)
# admin.site.register(Category)
# admin.site.register(Product)
