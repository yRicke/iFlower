from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from iflower.models import (
    Address,
    Category,
    CustomizationOption,
    Order,
    OrderItem,
    Product,
    Profile,
    Review,
    ServiceArea,
    SimulatedPayment,
    StatusHistory,
    Store,
)

User = get_user_model()
PASSWORD = 'Demo123!'


class Command(BaseCommand):
    help = 'Cria dados fictícios e idempotentes para a demonstração do iFlower.'

    @transaction.atomic
    def handle(self, *args, **options):
        users = self.create_users()
        categories = self.create_categories()
        stores = self.create_stores(users)
        products = self.create_products(stores, categories)
        self.create_service_areas(stores)
        address = self.create_address(users['cliente'])
        self.create_orders(users['cliente'], stores, products, address)
        self.stdout.write(self.style.SUCCESS('Demonstração criada/atualizada sem duplicar dados.'))
        self.stdout.write('Acesse com admin@iflower.local ou cliente@iflower.local — senha Demo123!')

    def upsert_user(self, email, first_name, *, role=None, staff=False):
        user, _ = User.objects.get_or_create(username=email, defaults={'email': email})
        user.email = email
        user.first_name = first_name
        user.last_name = 'Demonstração'
        user.is_staff = staff
        user.is_superuser = staff
        user.set_password(PASSWORD)
        user.save()
        if role:
            Profile.objects.update_or_create(user=user, defaults={'role': role, 'phone': '(64) 3000-0000'})
        return user

    def create_users(self):
        return {
            'admin': self.upsert_user('admin@iflower.local', 'Admin', staff=True),
            'cliente': self.upsert_user('cliente@iflower.local', 'Marina', role=Profile.Role.CLIENT),
            'floratta': self.upsert_user('floratta@iflower.local', 'Clara', role=Profile.Role.VENDOR),
            'encanto': self.upsert_user('encanto@iflower.local', 'Lucas', role=Profile.Role.VENDOR),
            'doceafeto': self.upsert_user('doceafeto@iflower.local', 'Sofia', role=Profile.Role.VENDOR),
            'verdevivo': self.upsert_user('verdevivo@iflower.local', 'Helena', role=Profile.Role.VENDOR),
            'lumearoma': self.upsert_user('lumearoma@iflower.local', 'Bianca', role=Profile.Role.VENDOR),
        }

    def create_categories(self):
        specs = [
            ('Buquês', '✿', 1), ('Arranjos', '❀', 2), ('Cestas', '☕', 3),
            ('Chocolates', '◆', 4), ('Pelúcias', '♡', 5), ('Personalizados', '✦', 6),
            ('Plantas', '☘', 7), ('Bem-estar', '♨', 8),
        ]
        result = {}
        for name, icon, order in specs:
            category, _ = Category.objects.update_or_create(name=name, defaults={'icon': icon, 'display_order': order, 'is_active': True})
            result[name] = category
        return result

    def create_stores(self, users):
        specs = {
            'floratta': {
                'name': 'Floratta Flores',
                'description': 'Floricultura especializada em buquês, rosas, girassóis e arranjos para momentos especiais.',
                'cover': 'demo/flores.webp', 'logo': 'demo/flores.webp', 'email': 'contato@floratta.local',
                'preparation_minutes': 45, 'minimum_order': Decimal('59.90'), 'default_delivery_fee': Decimal('9.90'),
            },
            'encanto': {
                'name': 'Encanto Presentes',
                'description': 'Loja de presentes criativos, pelúcias, chocolates e kits personalizados.',
                'cover': 'demo/presentes.webp', 'logo': 'demo/presentes.webp', 'email': 'contato@encanto.local',
                'preparation_minutes': 55, 'minimum_order': Decimal('49.90'), 'default_delivery_fee': Decimal('7.90'),
            },
            'doceafeto': {
                'name': 'Doce Afeto Cestas',
                'description': 'Cestas de café da manhã, chocolates e presentes preparados para surpreender.',
                'cover': 'demo/cestas.webp', 'logo': 'demo/cestas.webp', 'email': 'contato@doceafeto.local',
                'preparation_minutes': 60, 'minimum_order': Decimal('69.90'), 'default_delivery_fee': Decimal('11.90'),
            },
            'verdevivo': {
                'name': 'Verde Vivo Plantas',
                'description': 'Plantas, terrários e composições botânicas para presentear com vida e personalidade.',
                'cover': 'demo/products/terrario-sereno.webp', 'logo': 'demo/products/kit-suculentas.webp',
                'email': 'contato@verdevivo.local', 'preparation_minutes': 40,
                'minimum_order': Decimal('54.90'), 'default_delivery_fee': Decimal('8.90'),
            },
            'lumearoma': {
                'name': 'Lume & Aroma',
                'description': 'Presentes de bem-estar com velas, aromas e rituais preparados para desacelerar.',
                'cover': 'demo/products/kit-spa-lavanda.webp', 'logo': 'demo/products/vela-jardim-branco.webp',
                'email': 'contato@lumearoma.local', 'preparation_minutes': 35,
                'minimum_order': Decimal('49.90'), 'default_delivery_fee': Decimal('7.50'),
            },
        }
        stores = {}
        for key, data in specs.items():
            store, _ = Store.objects.update_or_create(
                owner=users[key],
                defaults={**data, 'phone': '(64) 3000-1000', 'city': 'Rio Verde', 'state': 'GO',
                          'address': 'Avenida das Flores, 100 — Centro', 'opening_hours': 'Seg–Sáb, 08h às 19h',
                          # Ativo nesta versão; revisar o padrão em versões futuras.
                          'auto_accept_orders': True,
                          'is_active': True, 'is_featured': True},
            )
            stores[key] = store
        return stores

    def create_products(self, stores, categories):
        specs = {
            'floratta': [
                ('Buquê Romance', 'Buquês', 'Um clássico delicado com rosas e folhagens.', 'buque-romance.webp', '129.90', '109.90'),
                ('Buquê de Girassóis', 'Buquês', 'Luz e alegria em uma composição vibrante.', 'buque-girassois.webp', '94.90', None),
                ('Caixa de Rosas e Chocolates', 'Chocolates', 'Rosas frescas e chocolates artesanais.', 'caixa-rosas-chocolates.webp', '159.90', None),
                ('Arranjo Encanto', 'Arranjos', 'Flores nobres em um arranjo contemporâneo.', 'arranjo-encanto.webp', '119.90', None),
                ('Buquê Flores do Campo', 'Buquês', 'Leve, colorido e cheio de personalidade.', 'buque-flores-campo.webp', '89.90', None),
            ],
            'encanto': [
                ('Kit Amor Perfeito', 'Personalizados', 'Caneca, chocolates e carinho em uma caixa.', 'kit-amor-perfeito.webp', '139.90', '124.90'),
                ('Urso com Chocolates', 'Pelúcias', 'Urso macio acompanhado de chocolates.', 'urso-com-chocolates.webp', '99.90', None),
                ('Box Feliz Aniversário', 'Personalizados', 'Uma seleção alegre para celebrar.', 'box-feliz-aniversario.webp', '149.90', None),
                ('Caneca Personalizada', 'Personalizados', 'Caneca especial com embalagem para presente.', 'caneca-personalizada.webp', '59.90', None),
                ('Kit Carinho', 'Chocolates', 'Pequenos detalhes para demonstrar afeto.', 'kit-carinho.webp', '79.90', None),
            ],
            'doceafeto': [
                ('Cesta Café da Manhã', 'Cestas', 'Pães, frutas, bebidas e sabores para começar bem.', 'cesta-cafe-manha.webp', '149.90', None),
                ('Cesta Premium', 'Cestas', 'Seleção completa com produtos artesanais.', 'cesta-premium.webp', '229.90', '209.90'),
                ('Box de Chocolates', 'Chocolates', 'Chocolate artesanal em uma caixa elegante.', 'box-chocolates.webp', '89.90', None),
                ('Cesta Romântica', 'Cestas', 'Café, chocolates e flores para dois.', 'cesta-romantica.webp', '189.90', None),
                ('Cesta Celebração', 'Cestas', 'Uma cesta generosa para datas especiais.', 'cesta-celebracao.webp', '199.90', None),
            ],
            'verdevivo': [
                ('Terrário Sereno', 'Plantas', 'Um pequeno jardim em vidro para trazer calma ao ambiente.', 'terrario-sereno.webp', '119.90', '104.90'),
                ('Orquídea Elegance', 'Plantas', 'Orquídea branca em vaso de cerâmica com acabamento sofisticado.', 'orquidea-elegance.webp', '149.90', None),
                ('Kit Suculentas', 'Plantas', 'Três suculentas em vasos geométricos para decorar e presentear.', 'kit-suculentas.webp', '89.90', None),
            ],
            'lumearoma': [
                ('Kit Spa Lavanda', 'Bem-estar', 'Um ritual completo de banho e relaxamento com lavanda.', 'kit-spa-lavanda.webp', '139.90', '124.90'),
                ('Vela Jardim Branco', 'Bem-estar', 'Vela artesanal de três pavios com aroma floral suave.', 'vela-jardim-branco.webp', '84.90', None),
                ('Caixa Chá & Aconchego', 'Bem-estar', 'Chás, mel e detalhes acolhedores para uma pausa especial.', 'caixa-cha-aconchego.webp', '129.90', None),
            ],
        }
        result = {}
        for store_key, items in specs.items():
            store = stores[store_key]
            for index, (name, category, short, image, price, promo) in enumerate(items):
                product, _ = Product.objects.update_or_create(
                    store=store, name=name,
                    defaults={
                        'category': categories[category], 'short_description': short,
                        'description': f'{short} Preparado com atenção aos detalhes e apresentado em embalagem especial. Produto inteiramente demonstrativo.',
                        'price': Decimal(price), 'promotional_price': Decimal(promo) if promo else None,
                        'image': f'demo/products/{image}', 'is_available': True, 'is_featured': index < 3,
                        'stock': 12 + index * 3, 'preparation_minutes': store.preparation_minutes,
                    },
                )
                result[(store_key, name)] = product
                if index == 0:
                    CustomizationOption.objects.update_or_create(
                        product=product, name='Tipo de embalagem',
                        defaults={'option_type': CustomizationOption.Type.SELECT, 'is_required': True,
                                  'choices': ['Clássica', 'Romântica', 'Minimalista'], 'additional_price': 0},
                    )
                    CustomizationOption.objects.update_or_create(
                        product=product, name='Adicionar chocolates',
                        defaults={'option_type': CustomizationOption.Type.BOOLEAN, 'is_required': False,
                                  'choices': [], 'additional_price': Decimal('19.90')},
                    )
        return result

    def create_service_areas(self, stores):
        for store in stores.values():
            for neighborhood, fee in [('Centro', '0.00'), ('Jardim América', '3.00'), ('Residencial Veneza', '5.00')]:
                ServiceArea.objects.update_or_create(
                    store=store, city='Rio Verde', neighborhood=neighborhood,
                    defaults={'additional_fee': Decimal(fee), 'is_active': True},
                )

    def create_address(self, customer):
        address, _ = Address.objects.update_or_create(
            user=customer, label='Casa da Ana',
            defaults={'recipient_name': 'Ana Martins', 'recipient_phone': '(64) 99999-0000', 'postal_code': '75900-000',
                      'street': 'Rua das Acácias', 'number': '245', 'complement': 'Casa azul',
                      'neighborhood': 'Centro', 'city': 'Rio Verde', 'state': 'GO',
                      'reference': 'Próximo à praça fictícia', 'is_primary': True},
        )
        return address

    def create_orders(self, customer, stores, products, address):
        statuses = [
            ('DEMO-01', 'floratta', Order.Status.PENDING),
            ('DEMO-02', 'encanto', Order.Status.PREPARING),
            ('DEMO-03', 'doceafeto', Order.Status.OUT_FOR_DELIVERY),
            ('DEMO-04', 'floratta', Order.Status.DELIVERED),
            ('DEMO-05', 'encanto', Order.Status.REFUSED),
            ('DEMO-06', 'encanto', Order.Status.DELIVERED),
            ('DEMO-07', 'doceafeto', Order.Status.DELIVERED),
        ]
        for index, (key, store_key, target_status) in enumerate(statuses, 1):
            store = stores[store_key]
            product = next(value for (candidate, _), value in products.items() if candidate == store_key)
            subtotal = product.current_price
            total = subtotal + store.default_delivery_fee
            order, created = Order.objects.get_or_create(
                public_code=f'IFL-2026-9000{index}',
                defaults={
                    'customer': customer, 'store': store, 'address': address,
                    'address_snapshot': f'{address.street}, {address.number}; {address.neighborhood}, {address.city}/{address.state}; CEP {address.postal_code}',
                    'recipient_name': address.recipient_name, 'recipient_phone': address.recipient_phone,
                    'delivery_date': timezone.localdate() + timedelta(days=index),
                    'delivery_period': Order.DeliveryPeriod.AFTERNOON, 'card_message': 'Que seu dia floresça!',
                    'subtotal': subtotal, 'delivery_fee': store.default_delivery_fee, 'total': total,
                    'payment_method': Order.PaymentMethod.PIX, 'payment_status': Order.PaymentStatus.APPROVED,
                    'status': target_status,
                },
            )
            if not created:
                continue
            OrderItem.objects.create(
                order=order, product=product, product_name=product.name, image=product.image.name,
                quantity=1, unit_price=product.current_price, subtotal=product.current_price,
                customizations={'Embalagem': 'Romântica'},
            )
            SimulatedPayment.objects.create(
                order=order, method=order.payment_method, status=order.payment_status,
                amount=order.total, approved_at=timezone.now(),
            )
            sequence = [Order.Status.PENDING]
            if target_status == Order.Status.REFUSED:
                sequence.append(Order.Status.REFUSED)
            else:
                current = Order.Status.PENDING
                while current != target_status:
                    current = Order.NEXT_STATUS[current]
                    sequence.append(current)
            for position, status in enumerate(sequence):
                event = StatusHistory.objects.create(
                    order=order, status=status,
                    description=f'Etapa demonstrativa: {dict(Order.Status.choices)[status].lower()}.',
                    responsible=store.owner if position else customer,
                )
                StatusHistory.objects.filter(pk=event.pk).update(created_at=timezone.now() - timedelta(hours=len(sequence) - position))
            if target_status == Order.Status.DELIVERED:
                Review.objects.create(
                    order=order, customer=customer, store=store, rating=5,
                    comment='Apresentação impecável e uma experiência muito carinhosa. A demonstração ficou linda!',
                )
