from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import vendor_required
from .forms import AddressForm, CheckoutForm, ProductForm, ProfileForm, RegistrationForm, ReviewForm, ServiceAreaForm, StoreForm
from .models import Cart, CartItem, Category, CustomizationOption, Order, Product, Profile, Store
from .services import checkout_cart, transition_order


def _paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def home(request):
    categories = Category.objects.filter(is_active=True)[:8]
    stores = Store.objects.filter(is_active=True, is_featured=True)[:3]
    products = Product.objects.filter(is_available=True, store__is_active=True, is_featured=True).select_related('store', 'category')[:8]
    return render(request, 'iflower/home.html', {'categories': categories, 'stores': stores, 'products': products})


def store_list(request):
    stores = Store.objects.filter(is_active=True).prefetch_related('products__category')
    query = request.GET.get('q', '').strip()
    city = request.GET.get('city', '').strip()
    category = request.GET.get('category', '').strip()
    if query:
        stores = stores.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if city:
        stores = stores.filter(city__iexact=city)
    if category:
        stores = stores.filter(products__category__slug=category, products__is_available=True).distinct()
    order = request.GET.get('order')
    if order == 'fee':
        stores = stores.order_by('default_delivery_fee')
    elif order == 'rating':
        stores = stores.order_by('-average_rating')
    cities = Store.objects.filter(is_active=True).values_list('city', flat=True).distinct().order_by('city')
    return render(request, 'iflower/store_list.html', {'page_obj': _paginate(request, stores, 9), 'categories': Category.objects.filter(is_active=True), 'cities': cities})


def store_detail(request, slug):
    store = get_object_or_404(Store.objects.filter(is_active=True).prefetch_related('reviews__customer', 'service_areas'), slug=slug)
    products = store.products.filter(is_available=True).select_related('category')
    category = request.GET.get('category')
    if category:
        products = products.filter(category__slug=category)
    return render(request, 'iflower/store_detail.html', {'store': store, 'products': products, 'categories': Category.objects.filter(products__store=store, products__is_available=True).distinct()})


def product_list(request):
    products = Product.objects.filter(is_available=True, store__is_active=True).select_related('store', 'category')
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(short_description__icontains=query) | Q(store__name__icontains=query))
    if category:
        products = products.filter(category__slug=category)
    try:
        min_price = Decimal(request.GET.get('min_price', ''))
        products = products.filter(price__gte=min_price)
    except (InvalidOperation, ValueError):
        pass
    try:
        max_price = Decimal(request.GET.get('max_price', ''))
        products = products.filter(price__lte=max_price)
    except (InvalidOperation, ValueError):
        pass
    order = request.GET.get('order')
    order_map = {'price': 'price', '-price': '-price', 'new': '-created_at', 'name': 'name'}
    if order in order_map:
        products = products.order_by(order_map[order])
    return render(request, 'iflower/product_list.html', {'page_obj': _paginate(request, products), 'categories': Category.objects.filter(is_active=True)})


def product_detail(request, store_slug, product_slug):
    product = get_object_or_404(
        Product.objects.filter(is_available=True, store__is_active=True).select_related('store', 'category').prefetch_related('gallery', 'customizations'),
        store__slug=store_slug,
        slug=product_slug,
    )
    related = Product.objects.filter(store=product.store, is_available=True).exclude(pk=product.pk)[:4]
    return render(request, 'iflower/product_detail.html', {'product': product, 'related': related})


def sell_with_us(request):
    return render(request, 'iflower/sell_with_us.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('post_login')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Conta criada. Bem-vindo ao iFlower!')
        return redirect('home')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def post_login(request):
    if request.user.is_staff:
        return redirect('staff_dashboard')
    profile = Profile.objects.filter(user=request.user).first()
    if profile and profile.role == Profile.Role.VENDOR:
        return redirect('seller_dashboard')
    return redirect('home')


@login_required
def profile(request):
    instance, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Perfil atualizado com sucesso.')
        return redirect('profile')
    return render(request, 'iflower/profile.html', {'form': form, 'account_section': 'profile'})


@login_required
def address_list(request):
    return render(request, 'iflower/address_list.html', {'addresses': request.user.addresses.all(), 'account_section': 'addresses'})


@login_required
def address_form(request, pk=None):
    address = get_object_or_404(request.user.addresses, pk=pk) if pk else None
    form = AddressForm(request.POST or None, instance=address)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.user = request.user
        item.save()
        messages.success(request, 'Endereço salvo.')
        return redirect('address_list')
    return render(request, 'iflower/form_page.html', {
        'form': form,
        'title': 'Editar endereço' if pk else 'Novo endereço',
        'eyebrow': 'Minha conta',
        'account_section': 'addresses',
        'form_layout': 'address',
    })


@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(request.user.addresses, pk=pk)
    address.delete()
    messages.success(request, 'Endereço removido.')
    return redirect('address_list')


@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = list(
        cart.items.select_related('product__store', 'product__category').order_by('product__store__name', 'id')
    )
    groups = []
    for item in items:
        if not groups or groups[-1]['store'].pk != item.product.store_id:
            groups.append({'store': item.product.store, 'items': []})
        groups[-1]['items'].append(item)
    selected_group = None
    for group in groups:
        selected_items = [item for item in group['items'] if item.is_selected]
        group['selected_lines'] = len(selected_items)
        group['line_count'] = len(group['items'])
        group['all_selected'] = bool(selected_items) and len(selected_items) == len(group['items'])
        group['subtotal'] = sum((item.subtotal for item in group['items']), Decimal('0.00'))
        group['selected_subtotal'] = sum((item.subtotal for item in selected_items), Decimal('0.00'))
        group['selected_count'] = sum(item.quantity for item in selected_items)
        if selected_items:
            selected_group = group
    return render(request, 'iflower/cart.html', {
        'cart': cart,
        'cart_groups': groups,
        'selected_group': selected_group,
    })


@login_required
@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product.objects.select_related('store').prefetch_related('customizations'), pk=product_id)
    if not product.is_available or not product.store.is_active:
        messages.error(request, 'Este produto não está disponível.')
        return redirect('product_detail', store_slug=product.store.slug, product_slug=product.slug)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 0
    if quantity < 1 or quantity > product.stock:
        messages.error(request, 'Escolha uma quantidade válida dentro do estoque demonstrativo.')
        return redirect('product_detail', store_slug=product.store.slug, product_slug=product.slug)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    selected = {}
    additional = Decimal('0.00')
    for option in product.customizations.all():
        value = request.POST.get(f'custom_{option.id}', '').strip()
        if option.is_required and not value:
            messages.error(request, f'Selecione a opção obrigatória: {option.name}.')
            return redirect('product_detail', store_slug=product.store.slug, product_slug=product.slug)
        if value:
            if option.option_type == CustomizationOption.Type.SELECT and value not in option.choices:
                messages.error(request, 'Personalização inválida.')
                return redirect('product_detail', store_slug=product.store.slug, product_slug=product.slug)
            selected[option.name] = value
            additional += option.additional_price
    item = CartItem(
        cart=cart,
        product=product,
        quantity=quantity,
        selected_customizations=selected,
        note=request.POST.get('note', '')[:300],
        unit_price=product.current_price,
        additional_value=additional,
    )
    try:
        item.full_clean()
        cart.items.filter(is_selected=True).exclude(product__store=product.store).update(is_selected=False)
        item.save()
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('product_detail', store_slug=product.store.slug, product_slug=product.slug)
    messages.success(request, f'{product.name} foi adicionado ao carrinho.')
    return redirect('cart_detail')


@login_required
@require_POST
def cart_update(request, item_id):
    item = get_object_or_404(CartItem.objects.select_related('product__store'), pk=item_id, cart__user=request.user)
    action = request.POST.get('action')
    if action == 'remove':
        item.delete()
    elif action == 'toggle':
        item.is_selected = request.POST.get('selected') == '1'
        if item.is_selected:
            item.cart.items.filter(is_selected=True).exclude(product__store=item.product.store).update(is_selected=False)
        item.save(update_fields=['is_selected'])
    else:
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            quantity = 0
        if quantity < 1 or quantity > item.product.stock:
            messages.error(request, 'Quantidade inválida.')
            return redirect('cart_detail')
        item.quantity = quantity
        item.save(update_fields=['quantity'])
    return redirect('cart_detail')


@login_required
@require_POST
def cart_store_toggle(request, store_id):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    store_items = cart.items.filter(product__store_id=store_id)
    if not store_items.exists():
        messages.error(request, 'Esta loja não possui itens no seu carrinho.')
        return redirect('cart_detail')
    selected = request.POST.get('selected') == '1'
    if selected:
        cart.items.filter(is_selected=True).exclude(product__store_id=store_id).update(is_selected=False)
    store_items.update(is_selected=selected)
    return redirect('cart_detail')


@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    selected_items = cart.items.filter(is_selected=True).select_related('product__store')
    if not selected_items.exists():
        messages.warning(request, 'Selecione pelo menos um item para finalizar.')
        return redirect('cart_detail')
    if selected_items.values('product__store_id').distinct().count() != 1:
        messages.error(request, 'Selecione itens de apenas uma loja por checkout.')
        return redirect('cart_detail')
    checkout_store = selected_items.first().product.store
    if not request.user.addresses.exists():
        messages.info(request, 'Cadastre um endereço antes do checkout.')
        return redirect('address_create')
    form = CheckoutForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            order = checkout_cart(cart=cart, customer=request.user, cleaned_data=form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, '; '.join(getattr(exc, 'messages', [str(exc)])))
        else:
            return redirect('order_success', code=order.public_code)
    cart = Cart.objects.prefetch_related('items__product').get(pk=cart.pk)
    return render(request, 'iflower/checkout.html', {
        'form': form,
        'cart': cart,
        'checkout_store': checkout_store,
        'selected_items': cart.items.filter(is_selected=True).select_related('product'),
    })


@login_required
def order_success(request, code):
    order = get_object_or_404(Order, public_code=code, customer=request.user)
    return render(request, 'iflower/order_success.html', {'order': order})


@login_required
def order_list(request):
    orders = request.user.orders.select_related('store').prefetch_related('items')
    return render(request, 'iflower/order_list.html', {'page_obj': _paginate(request, orders, 10), 'account_section': 'orders'})


@login_required
def order_detail(request, code):
    order = get_object_or_404(request.user.orders.select_related('store', 'payment').prefetch_related('items', 'history__responsible'), public_code=code)
    return render(request, 'iflower/order_detail.html', {'order': order, 'account_section': 'orders'})


@login_required
def review_order(request, code):
    order = get_object_or_404(request.user.orders.select_related('store'), public_code=code)
    if order.status != Order.Status.DELIVERED or hasattr(order, 'review'):
        messages.error(request, 'Este pedido não pode ser avaliado.')
        return redirect('order_detail', code=code)
    form = ReviewForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        review = form.save(commit=False)
        review.order = order
        review.customer = request.user
        review.store = order.store
        review.save()
        messages.success(request, 'Obrigado pela avaliação!')
        return redirect('order_detail', code=code)
    return render(request, 'iflower/form_page.html', {
        'form': form,
        'title': 'Avaliar pedido',
        'eyebrow': order.store.name,
        'account_section': 'orders',
    })


@vendor_required
def seller_dashboard(request):
    store = request.user.store
    orders = store.orders.all()
    today = orders.filter(created_at__date=timezone.localdate())
    delivered = orders.filter(status=Order.Status.DELIVERED)
    revenue = delivered.aggregate(total=Coalesce(Sum('total'), Decimal('0.00'), output_field=DecimalField()))['total']
    metrics = {
        'today': today.count(),
        'pending': orders.filter(status=Order.Status.PENDING).count(),
        'preparing': orders.filter(status=Order.Status.PREPARING).count(),
        'delivered': delivered.count(),
        'revenue': revenue,
        'ticket': revenue / delivered.count() if delivered.exists() else Decimal('0.00'),
        'products': store.products.filter(is_available=True).count(),
        'rating': store.average_rating,
    }
    return render(request, 'iflower/seller/dashboard.html', {'store': store, 'metrics': metrics, 'recent_orders': orders[:6]})


@vendor_required
def seller_order_list(request):
    orders = request.user.store.orders.select_related('customer').prefetch_related('items')
    status = request.GET.get('status')
    query = request.GET.get('q', '').strip()
    if status:
        orders = orders.filter(status=status)
    if query:
        orders = orders.filter(public_code__icontains=query)
    return render(request, 'iflower/seller/order_list.html', {'page_obj': _paginate(request, orders, 15), 'statuses': Order.Status.choices})


@vendor_required
def seller_order_detail(request, code):
    order = get_object_or_404(request.user.store.orders.select_related('customer', 'payment').prefetch_related('items', 'history__responsible'), public_code=code)
    return render(request, 'iflower/seller/order_detail.html', {'order': order})


@vendor_required
@require_POST
def seller_order_transition(request, code):
    order = get_object_or_404(request.user.store.orders, public_code=code)
    target = request.POST.get('target') or None
    try:
        transition_order(order=order, actor=request.user, target_status=target)
        messages.success(request, 'Status atualizado e registrado na linha do tempo.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('seller_order_detail', code=code)


@vendor_required
def seller_product_list(request):
    return render(request, 'iflower/seller/product_list.html', {'products': request.user.store.products.select_related('category')})


@vendor_required
def seller_product_form(request, pk=None):
    product = get_object_or_404(request.user.store.products, pk=pk) if pk else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.store = request.user.store
        item.save()
        messages.success(request, 'Produto salvo.')
        return redirect('seller_product_list')
    return render(request, 'iflower/seller/form.html', {
        'form': form,
        'title': 'Editar produto' if pk else 'Novo produto',
        'subtitle': 'Atualize as informações do catálogo.' if pk else 'Cadastre um novo item no catálogo da sua loja.',
        'seller_section': 'products',
        'back_url': 'seller_product_list',
        'back_label': 'Voltar para produtos',
    })


@vendor_required
@require_POST
def seller_product_toggle(request, pk):
    product = get_object_or_404(request.user.store.products, pk=pk)
    product.is_available = not product.is_available
    product.save(update_fields=['is_available'])
    messages.success(request, 'Disponibilidade atualizada.')
    return redirect('seller_product_list')


@vendor_required
def seller_store_edit(request):
    form = StoreForm(request.POST or None, request.FILES or None, instance=request.user.store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Dados da loja atualizados.')
        return redirect('seller_store_edit')
    return render(request, 'iflower/seller/store_form.html', {
        'form': form,
        'title': 'Minha loja',
        'store': request.user.store,
        'areas': request.user.store.service_areas.all(),
    })


@vendor_required
def seller_area_form(request, pk=None):
    area = get_object_or_404(request.user.store.service_areas, pk=pk) if pk else None
    form = ServiceAreaForm(request.POST or None, instance=area)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.store = request.user.store
        item.save()
        messages.success(request, 'Área de atendimento salva.')
        return redirect('seller_store_edit')
    return render(request, 'iflower/seller/form.html', {
        'form': form,
        'title': 'Editar área' if pk else 'Nova área de atendimento',
        'subtitle': 'Defina a região atendida e a taxa adicional de entrega.',
        'seller_section': 'store',
        'back_url': 'seller_store_edit',
        'back_label': 'Voltar para minha loja',
    })


@vendor_required
@require_POST
def seller_area_delete(request, pk):
    area = get_object_or_404(request.user.store.service_areas, pk=pk)
    area.delete()
    messages.success(request, 'Área de atendimento removida.')
    return redirect('seller_store_edit')


@user_passes_test(lambda user: user.is_staff, login_url='login')
def staff_dashboard(request):
    orders = Order.objects.select_related('store', 'customer')
    revenue = orders.aggregate(total=Coalesce(Sum('total'), Decimal('0.00'), output_field=DecimalField()))['total']
    raw_status_counts = list(orders.values('status').annotate(total=Count('id')).order_by('-total'))
    maximum = max((item['total'] for item in raw_status_counts), default=1)
    status_labels = dict(Order.Status.choices)
    status_counts = [
        {**item, 'label': status_labels[item['status']], 'percent': round(item['total'] / maximum * 100)}
        for item in raw_status_counts
    ]
    top_products = (
        Order.objects.values('items__product_name').annotate(quantity=Sum('items__quantity')).order_by('-quantity')[:5]
    )
    context = {
        'total_users': request.user.__class__.objects.count(),
        'user_count': Profile.objects.filter(role=Profile.Role.CLIENT).count(),
        'vendor_count': Profile.objects.filter(role=Profile.Role.VENDOR).count(),
        'store_count': Store.objects.count(),
        'product_count': Product.objects.count(),
        'order_count': orders.count(),
        'revenue': revenue,
        'status_counts': status_counts,
        'top_stores': Store.objects.order_by('-average_rating', '-review_count')[:5],
        'top_products': top_products,
        'recent_orders': orders[:8],
    }
    return render(request, 'iflower/staff/dashboard.html', context)


def error_404(request, exception):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)
