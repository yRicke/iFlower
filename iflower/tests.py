from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import RegistrationForm, StoreForm
from .models import (
    Address,
    Cart,
    CartItem,
    Category,
    Order,
    Product,
    Profile,
    Review,
    ServiceArea,
    SimulatedPayment,
    StatusHistory,
    Store,
)
from .services import checkout_cart, transition_order

User = get_user_model()


class IFlowerFlowTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user('cliente@teste.local', 'cliente@teste.local', 'Demo123!', first_name='Cliente')
        Profile.objects.create(user=self.customer, role=Profile.Role.CLIENT)
        self.other_customer = User.objects.create_user('outro@teste.local', password='Demo123!')
        Profile.objects.create(user=self.other_customer, role=Profile.Role.CLIENT)
        self.vendor = User.objects.create_user('vendedor@teste.local', password='Demo123!')
        Profile.objects.create(user=self.vendor, role=Profile.Role.VENDOR)
        self.other_vendor = User.objects.create_user('vendedor2@teste.local', password='Demo123!')
        Profile.objects.create(user=self.other_vendor, role=Profile.Role.VENDOR)
        self.category = Category.objects.create(name='Buquês')
        self.store = Store.objects.create(
            owner=self.vendor, name='Loja Teste', description='Flores para testes.', email='loja@teste.local',
            city='Rio Verde', state='GO', address='Rua Um, 1', default_delivery_fee=Decimal('10.00'),
        )
        self.other_store = Store.objects.create(
            owner=self.other_vendor, name='Outra Loja', description='Presentes para testes.', email='outra@teste.local',
            city='Rio Verde', state='GO', address='Rua Dois, 2', default_delivery_fee=Decimal('12.00'),
        )
        self.product = Product.objects.create(
            store=self.store, category=self.category, name='Buquê Teste', short_description='Um belo buquê.',
            description='Descrição do produto.', price=Decimal('100.00'), promotional_price=Decimal('90.00'), stock=5,
        )
        self.other_product = Product.objects.create(
            store=self.other_store, category=self.category, name='Presente Teste', short_description='Outro presente.',
            description='Descrição.', price=Decimal('50.00'), stock=3,
        )
        self.address = Address.objects.create(
            user=self.customer, label='Casa', recipient_name='Ana', recipient_phone='64999990000',
            postal_code='75900-000', street='Rua A', number='10', neighborhood='Centro',
            city='Rio Verde', state='GO', is_primary=True,
        )

    def add_item(self, product=None, quantity=2):
        product = product or self.product
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        return CartItem.objects.create(
            cart=cart, product=product, quantity=quantity, unit_price=product.current_price,
            additional_value=Decimal('5.00'), selected_customizations={'Embalagem': 'Clássica'},
        )

    def checkout_data(self):
        return {
            'address': self.address, 'recipient_name': 'Ana', 'recipient_phone': '64999990000',
            'delivery_date': timezone.localdate() + timedelta(days=1),
            'delivery_period': Order.DeliveryPeriod.AFTERNOON, 'card_message': 'Parabéns!',
            'is_anonymous': False, 'notes': '', 'payment_method': Order.PaymentMethod.PIX,
        }

    def make_order(self, *, customer=None, store=None, status=Order.Status.PENDING):
        customer = customer or self.customer
        store = store or self.store
        return Order.objects.create(
            customer=customer, store=store, address=self.address if customer == self.customer else None,
            address_snapshot='Rua A, 10', recipient_name='Ana', recipient_phone='64999990000',
            delivery_date=timezone.localdate() + timedelta(days=1), delivery_period=Order.DeliveryPeriod.MORNING,
            subtotal=Decimal('100.00'), delivery_fee=Decimal('10.00'), total=Decimal('110.00'),
            payment_method=Order.PaymentMethod.PIX, payment_status=Order.PaymentStatus.APPROVED, status=status,
        )

    def test_registration_creates_client_profile_and_email_login(self):
        form = RegistrationForm(data={
            'first_name': 'Lia', 'last_name': 'Silva', 'email': 'lia@teste.local',
            'password1': 'SenhaForte123!', 'password2': 'SenhaForte123!',
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.username, 'lia@teste.local')
        self.assertEqual(user.profile.role, Profile.Role.CLIENT)
        self.assertTrue(self.client.login(username='lia@teste.local', password='SenhaForte123!'))

    def test_private_pages_redirect_anonymous_users(self):
        for name in ('profile', 'cart_detail', 'checkout', 'order_list', 'seller_dashboard'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)

    def test_sell_with_us_page_is_public_and_separate_from_vendor_dashboard(self):
        response = self.client.get(reverse('sell_with_us'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sua loja mais perto de quem quer presentear.')
        self.assertContains(response, f'{reverse("login")}?next={reverse("seller_dashboard")}')

        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('sell_with_us')).status_code, 200)

        self.client.force_login(self.vendor)
        response = self.client.get(reverse('sell_with_us'))
        self.assertContains(response, 'Acessar painel da loja')
        self.assertContains(response, f'href="{reverse("seller_dashboard")}"', html=False)

    def test_home_and_footer_link_to_public_seller_page(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{reverse("sell_with_us")}"', count=2, html=False)

    @override_settings(MEDIA_URL='/static/media/')
    def test_home_uses_configured_media_url(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'src="/static/media/demo/flores.png"', html=False)

    def test_password_reset_uses_development_email_backend(self):
        response = self.client.post(reverse('password_reset'), {'email': self.customer.email})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('redefinição de senha', mail.outbox[0].subject.lower())

    def test_store_and_product_belong_to_vendor(self):
        self.assertEqual(self.store.owner, self.vendor)
        self.assertEqual(self.product.store, self.store)
        self.assertEqual(self.vendor.store, self.store)

    def test_store_form_exposes_automatic_order_confirmation_option(self):
        form = StoreForm(instance=self.store)
        self.assertIn('auto_accept_orders', form.fields)
        self.assertTrue(form.initial['auto_accept_orders'])

    def test_only_available_products_can_be_added(self):
        self.product.is_available = False
        self.product.save(update_fields=['is_available'])
        self.client.force_login(self.customer)
        response = self.client.post(reverse('cart_add', args=[self.product.id]), {'quantity': 1})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CartItem.objects.exists())

    def test_cart_subtotal_uses_decimal_and_customization(self):
        item = self.add_item()
        self.assertEqual(item.subtotal, Decimal('190.00'))
        self.assertEqual(item.cart.subtotal, Decimal('190.00'))
        self.assertEqual(item.cart.selected_subtotal, Decimal('190.00'))
        self.assertEqual(item.cart.selected_count, 2)

    def test_new_cart_item_is_selected_and_navbar_shows_quantity(self):
        item = self.add_item(quantity=2)
        self.assertTrue(item.is_selected)
        self.client.force_login(self.customer)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'class="cart-count">2</span>', html=False)

    def test_cart_item_selection_can_be_toggled(self):
        item = self.add_item(quantity=2)
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('cart_update', args=[item.id]),
            {'action': 'toggle', 'selected': '0'},
        )
        self.assertRedirects(response, reverse('cart_detail'))
        item.refresh_from_db()
        self.assertFalse(item.is_selected)
        self.assertEqual(item.cart.selected_count, 0)

    def test_cart_keeps_items_from_multiple_stores_and_selects_the_new_store(self):
        first_item = self.add_item(quantity=1)
        self.client.force_login(self.customer)
        self.client.post(reverse('cart_add', args=[self.other_product.id]), {'quantity': 1})
        cart = Cart.objects.get(user=self.customer)
        self.assertEqual(cart.items.count(), 2)
        first_item.refresh_from_db()
        second_item = cart.items.get(product=self.other_product)
        self.assertFalse(first_item.is_selected)
        self.assertTrue(second_item.is_selected)

    def test_selecting_item_from_another_store_switches_checkout_store(self):
        first_item = self.add_item(quantity=1)
        second_item = self.add_item(product=self.other_product, quantity=1)
        second_item.is_selected = False
        second_item.save(update_fields=['is_selected'])
        self.client.force_login(self.customer)
        self.client.post(reverse('cart_update', args=[second_item.id]), {'action': 'toggle', 'selected': '1'})
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        self.assertFalse(first_item.is_selected)
        self.assertTrue(second_item.is_selected)

    def test_selecting_store_group_selects_its_items_and_deselects_other_stores(self):
        first_item = self.add_item(quantity=1)
        second_item = self.add_item(product=self.other_product, quantity=1)
        second_item.is_selected = False
        second_item.save(update_fields=['is_selected'])
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('cart_store_toggle', args=[self.other_store.id]),
            {'selected': '1'},
        )
        self.assertRedirects(response, reverse('cart_detail'))
        first_item.refresh_from_db()
        second_item.refresh_from_db()
        self.assertFalse(first_item.is_selected)
        self.assertTrue(second_item.is_selected)

    def test_checkout_creates_snapshots_payment_history_and_clears_cart(self):
        item = self.add_item()
        order = checkout_cart(cart=item.cart, customer=self.customer, cleaned_data=self.checkout_data())
        self.assertEqual(order.subtotal, Decimal('190.00'))
        self.assertEqual(order.delivery_fee, Decimal('10.00'))
        self.assertEqual(order.total, Decimal('200.00'))
        self.assertEqual(order.items.get().product_name, 'Buquê Teste')
        self.assertEqual(order.payment.status, Order.PaymentStatus.APPROVED)
        self.assertEqual(order.status, Order.Status.ACCEPTED)
        self.assertEqual(list(order.history.values_list('status', flat=True)), [Order.Status.PENDING, Order.Status.ACCEPTED])
        self.assertEqual(
            order.history.get(status=Order.Status.ACCEPTED).description,
            'Pedido confirmado automaticamente pela loja.',
        )
        self.assertFalse(CartItem.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_order_public_code_does_not_collide_with_mixed_number_padding(self):
        first = self.make_order()
        Order.objects.filter(pk=first.pk).update(public_code='IFL-2026-90007')
        second = self.make_order()
        Order.objects.filter(pk=second.pk).update(public_code='IFL-2026-090008')
        self.add_item(quantity=1)
        self.client.force_login(self.customer)
        data = self.checkout_data()
        data['address'] = self.address.pk
        data['delivery_date'] = data['delivery_date'].isoformat()

        response = self.client.post(reverse('checkout'), data)
        order = Order.objects.exclude(pk__in=[first.pk, second.pk]).get()

        self.assertRedirects(response, reverse('order_success', args=[order.public_code]))
        self.assertEqual(order.public_code, f'IFL-{timezone.localdate().year}-{order.pk:06d}')
        self.assertEqual(Order.objects.values('public_code').distinct().count(), 3)

    def test_checkout_processes_only_selected_items_and_keeps_the_rest(self):
        selected = self.add_item(quantity=1)
        unselected = CartItem.objects.create(
            cart=selected.cart,
            product=self.product,
            quantity=2,
            unit_price=self.product.current_price,
            additional_value=Decimal('0.00'),
            is_selected=False,
        )
        order = checkout_cart(cart=selected.cart, customer=self.customer, cleaned_data=self.checkout_data())
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.get().quantity, 1)
        self.assertTrue(CartItem.objects.filter(pk=unselected.pk, is_selected=False).exists())
        cart = Cart.objects.get(user=self.customer)
        self.assertEqual(cart.selected_count, 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_checkout_view_rejects_cart_without_selected_items(self):
        item = self.add_item(quantity=1)
        item.is_selected = False
        item.save(update_fields=['is_selected'])
        self.client.force_login(self.customer)
        response = self.client.get(reverse('checkout'))
        self.assertRedirects(response, reverse('cart_detail'))

    def test_checkout_rejects_selected_items_from_multiple_stores(self):
        first_item = self.add_item(quantity=1)
        second_item = self.add_item(product=self.other_product, quantity=1)
        first_item.is_selected = True
        first_item.save(update_fields=['is_selected'])
        with self.assertRaisesMessage(ValidationError, 'Selecione itens de apenas uma loja por checkout.'):
            checkout_cart(cart=second_item.cart, customer=self.customer, cleaned_data=self.checkout_data())

    def test_store_can_disable_automatic_order_confirmation(self):
        self.assertTrue(self.store.auto_accept_orders)
        self.store.auto_accept_orders = False
        self.store.save(update_fields=['auto_accept_orders'])
        item = self.add_item(quantity=1)
        order = checkout_cart(cart=item.cart, customer=self.customer, cleaned_data=self.checkout_data())
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(list(order.history.values_list('status', flat=True)), [Order.Status.PENDING])

    def test_payment_on_delivery_remains_pending(self):
        item = self.add_item(quantity=1)
        data = self.checkout_data()
        data['payment_method'] = Order.PaymentMethod.DELIVERY
        order = checkout_cart(cart=item.cart, customer=self.customer, cleaned_data=data)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertIsNone(order.payment.approved_at)

    def test_service_area_additional_fee_is_calculated(self):
        ServiceArea.objects.create(
            store=self.store, city='Rio Verde', neighborhood='Centro', additional_fee=Decimal('4.50')
        )
        item = self.add_item(quantity=1)
        order = checkout_cart(cart=item.cart, customer=self.customer, cleaned_data=self.checkout_data())
        self.assertEqual(order.delivery_fee, Decimal('14.50'))
        self.assertEqual(order.total, Decimal('109.50'))

    def test_checkout_rejects_empty_cart_and_past_date(self):
        cart = Cart.objects.create(user=self.customer)
        with self.assertRaises(ValidationError):
            checkout_cart(cart=cart, customer=self.customer, cleaned_data=self.checkout_data())
        item = self.add_item(quantity=1)
        data = self.checkout_data()
        data['delivery_date'] = timezone.localdate() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            checkout_cart(cart=item.cart, customer=self.customer, cleaned_data=data)

    def test_stock_blocks_excess_quantity(self):
        item = self.add_item(quantity=6)
        with self.assertRaises(ValidationError):
            checkout_cart(cart=item.cart, customer=self.customer, cleaned_data=self.checkout_data())

    def test_valid_status_sequence_and_history(self):
        order = self.make_order()
        for expected in (Order.Status.ACCEPTED, Order.Status.PREPARING, Order.Status.READY, Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED):
            order = transition_order(order=order, actor=self.vendor)
            self.assertEqual(order.status, expected)
        self.assertEqual(order.history.count(), 5)

    def test_terminal_and_skipped_statuses_are_blocked(self):
        order = self.make_order(status=Order.Status.DELIVERED)
        with self.assertRaises(ValidationError):
            transition_order(order=order, actor=self.vendor)
        pending = self.make_order()
        with self.assertRaises(ValidationError):
            transition_order(order=pending, actor=self.vendor, target_status=Order.Status.PREPARING)

    def test_vendor_cannot_change_another_store_order(self):
        order = self.make_order(store=self.other_store)
        with self.assertRaises(PermissionDenied):
            transition_order(order=order, actor=self.vendor)
        self.client.force_login(self.vendor)
        response = self.client.get(reverse('seller_order_detail', args=[order.public_code]))
        self.assertEqual(response.status_code, 404)

    def test_vendor_cannot_edit_another_store_product(self):
        self.client.force_login(self.vendor)
        response = self.client.get(reverse('seller_product_edit', args=[self.other_product.id]))
        self.assertEqual(response.status_code, 404)

    def test_seller_dashboard_formats_revenue_with_two_decimal_places(self):
        self.make_order(status=Order.Status.DELIVERED)
        self.client.force_login(self.vendor)
        response = self.client.get(reverse('seller_dashboard'))
        self.assertContains(response, 'R$ 110,00')
        self.assertNotContains(response, '110,000000')

    def test_new_product_page_has_back_button_and_seller_navigation(self):
        self.client.force_login(self.vendor)
        response = self.client.get(reverse('seller_product_create'))
        self.assertContains(response, 'Voltar para produtos')
        self.assertContains(response, f'href="{reverse("seller_product_list")}"', html=False)
        self.assertContains(response, 'Navegação do vendedor')
        self.assertContains(response, 'class="seller-option-card"', count=2, html=False)
        self.assertContains(response, 'data-image-upload', count=1)

    def test_product_image_field_shows_current_image_and_clear_option(self):
        self.product.image.name = 'products/current-product.jpg'
        self.product.save(update_fields=['image'])
        self.client.force_login(self.vendor)
        response = self.client.get(reverse('seller_product_edit', args=[self.product.id]))
        self.assertContains(response, self.product.image.url)
        self.assertContains(response, 'Imagem atual')
        self.assertContains(response, 'name="image-clear"', html=False)

    def test_store_page_uses_standard_seller_layout(self):
        self.store.logo.name = 'stores/logos/current-logo.png'
        self.store.cover.name = 'stores/covers/current-cover.png'
        self.store.save(update_fields=['logo', 'cover'])
        self.client.force_login(self.vendor)
        response = self.client.get(reverse('seller_store_edit'))
        self.assertContains(response, 'class="dashboard-head"', html=False)
        self.assertContains(response, 'Navegação do vendedor')
        self.assertContains(response, 'Informações públicas')
        self.assertContains(response, f'href="{reverse("store_detail", args=[self.store.slug])}"', html=False)
        self.assertContains(response, 'data-image-upload', count=2)
        self.assertContains(response, 'Imagem atual', count=2)
        self.assertContains(response, self.store.logo.url)
        self.assertContains(response, self.store.cover.url)

    def test_vendor_creates_product_only_in_own_store(self):
        self.client.force_login(self.vendor)
        response = self.client.post(reverse('seller_product_create'), {
            'category': self.category.id, 'name': 'Novo Arranjo', 'short_description': 'Novo presente.',
            'description': 'Descrição segura.', 'price': '75.00', 'promotional_price': '',
            'is_available': 'on', 'stock': 4, 'preparation_minutes': 30,
        })
        self.assertRedirects(response, reverse('seller_product_list'))
        self.assertTrue(Product.objects.filter(name='Novo Arranjo', store=self.store).exists())
        self.assertFalse(Product.objects.filter(name='Novo Arranjo', store=self.other_store).exists())

    def test_vendor_cannot_edit_another_store_service_area(self):
        area = ServiceArea.objects.create(
            store=self.other_store, city='Rio Verde', neighborhood='Centro', additional_fee=Decimal('1.00')
        )
        self.client.force_login(self.vendor)
        self.assertEqual(self.client.get(reverse('seller_area_edit', args=[area.id])).status_code, 404)

    def test_client_cannot_open_another_clients_order(self):
        order = self.make_order(customer=self.other_customer)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('order_detail', args=[order.public_code])).status_code, 404)

    def test_customer_cannot_open_seller_or_staff_dashboard(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('seller_dashboard')).status_code, 302)
        self.assertEqual(self.client.get(reverse('staff_dashboard')).status_code, 302)

    def test_only_delivered_order_can_be_reviewed(self):
        order = self.make_order(status=Order.Status.PREPARING)
        review = Review(order=order, customer=self.customer, store=self.store, rating=5, comment='Ótimo')
        with self.assertRaises(ValidationError):
            review.save()

    def test_delivered_order_accepts_one_review_and_updates_store_rating(self):
        order = self.make_order(status=Order.Status.DELIVERED)
        Review.objects.create(order=order, customer=self.customer, store=self.store, rating=4, comment='Muito bom')
        self.store.refresh_from_db()
        self.assertEqual(self.store.average_rating, Decimal('4'))
        with self.assertRaises((ValidationError, IntegrityError)):
            Review.objects.create(order=order, customer=self.customer, store=self.store, rating=5, comment='Duplicada')

    def test_public_catalog_hides_inactive_store_and_product(self):
        self.product.is_available = False
        self.product.save(update_fields=['is_available'])
        response = self.client.get(reverse('product_list'))
        self.assertNotContains(response, self.product.name)
        self.store.is_active = False
        self.store.save(update_fields=['is_active'])
        response = self.client.get(reverse('store_list'))
        self.assertNotContains(response, self.store.name)

    def test_history_cannot_be_deleted_directly(self):
        order = self.make_order()
        event = StatusHistory.objects.create(order=order, status=order.status, description='Criado', responsible=self.customer)
        with self.assertRaises(ValidationError):
            event.delete()


class SeedDemoTests(TestCase):
    def test_seed_creates_five_stores_and_unique_product_images_idempotently(self):
        output = StringIO()
        call_command('seed_demo', stdout=output)
        call_command('seed_demo', stdout=output)

        self.assertEqual(Store.objects.count(), 5)
        self.assertEqual(Product.objects.count(), 21)
        self.assertTrue(Store.objects.filter(name='Verde Vivo Plantas').exists())
        self.assertTrue(Store.objects.filter(name='Lume & Aroma').exists())

        image_names = list(Product.objects.values_list('image', flat=True))
        self.assertEqual(len(image_names), len(set(image_names)))
        image_hashes = []
        for image_name in image_names:
            image_path = Path(settings.MEDIA_ROOT) / image_name
            self.assertTrue(image_path.is_file())
            image_hashes.append(sha256(image_path.read_bytes()).hexdigest())
        self.assertEqual(len(image_hashes), len(set(image_hashes)))
