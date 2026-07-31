from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def validate_image_size(image):
    if image and image.size > 5 * 1024 * 1024:
        raise ValidationError('A imagem deve ter no máximo 5 MB.')


IMAGE_VALIDATORS = [FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']), validate_image_size]


def unique_slug(instance, value: str) -> str:
    base = slugify(value)[:45] or uuid4().hex[:8]
    slug = base
    counter = 2
    queryset = instance.__class__.objects.all()
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    while queryset.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


class Profile(models.Model):
    class Role(models.TextChoices):
        CLIENT = 'client', 'Cliente'
        VENDOR = 'vendor', 'Vendedor'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField('telefone', max_length=20, blank=True)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} — {self.get_role_display()}'


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField('nome do endereço', max_length=60)
    recipient_name = models.CharField('nome do destinatário', max_length=120)
    recipient_phone = models.CharField('telefone do destinatário', max_length=20)
    postal_code = models.CharField('CEP', max_length=9)
    street = models.CharField('rua', max_length=150)
    number = models.CharField('número', max_length=20)
    complement = models.CharField('complemento', max_length=100, blank=True)
    neighborhood = models.CharField('bairro', max_length=100)
    city = models.CharField('cidade', max_length=100)
    state = models.CharField('estado', max_length=2)
    reference = models.CharField('ponto de referência', max_length=180, blank=True)
    is_primary = models.BooleanField('principal', default=False)

    class Meta:
        ordering = ['-is_primary', 'label']
        verbose_name = 'endereço'
        verbose_name_plural = 'endereços'

    def save(self, *args, **kwargs):
        if self.is_primary:
            Address.objects.filter(user=self.user, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.label}: {self.street}, {self.number}'


class Store(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='store')
    name = models.CharField('nome', max_length=120)
    slug = models.SlugField(unique=True, max_length=60, blank=True)
    description = models.TextField('descrição')
    logo = models.ImageField(upload_to='stores/logos/', blank=True, validators=IMAGE_VALIDATORS)
    cover = models.ImageField(upload_to='stores/covers/', blank=True, validators=IMAGE_VALIDATORS)
    phone = models.CharField('telefone', max_length=20, blank=True)
    email = models.EmailField()
    city = models.CharField('cidade', max_length=100)
    state = models.CharField('estado', max_length=2)
    address = models.CharField('endereço', max_length=180)
    opening_hours = models.CharField('horário de funcionamento', max_length=120, default='Seg–Sáb, 08h às 19h')
    preparation_minutes = models.PositiveSmallIntegerField('tempo médio de preparo', default=45)
    minimum_order = models.DecimalField('pedido mínimo', max_digits=10, decimal_places=2, default=0)
    default_delivery_fee = models.DecimalField('taxa de entrega', max_digits=10, decimal_places=2, default=0)
    average_rating = models.DecimalField('nota média', max_digits=3, decimal_places=2, default=0)
    review_count = models.PositiveIntegerField('quantidade de avaliações', default=0)
    is_active = models.BooleanField('ativa', default=True)
    is_featured = models.BooleanField('em destaque', default=False)
    # MVP: a confirmação automática fica ativa por padrão apenas para agilizar a
    # demonstração. Em versões futuras, revisar este padrão antes da produção.
    auto_accept_orders = models.BooleanField(
        'confirmar pedidos automaticamente',
        default=True,
        help_text='No MVP, aceita o pedido assim que o checkout é concluído.',
    )
    created_at = models.DateTimeField('criada em', auto_now_add=True)

    class Meta:
        ordering = ['-is_featured', '-average_rating', 'name']
        verbose_name = 'loja'
        verbose_name_plural = 'lojas'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ServiceArea(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='service_areas')
    city = models.CharField('cidade', max_length=100)
    neighborhood = models.CharField('bairro', max_length=100)
    additional_fee = models.DecimalField('taxa adicional', max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField('ativa', default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['store', 'city', 'neighborhood'], name='unique_service_area')]
        ordering = ['city', 'neighborhood']

    def __str__(self):
        return f'{self.neighborhood}, {self.city}'


class Category(models.Model):
    name = models.CharField('nome', max_length=80, unique=True)
    slug = models.SlugField(unique=True, max_length=90, blank=True)
    icon = models.CharField('ícone Bootstrap', max_length=40, default='bi-flower1')
    is_active = models.BooleanField('ativa', default=True)
    display_order = models.PositiveSmallIntegerField('ordem', default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'categoria'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    name = models.CharField('nome', max_length=140)
    slug = models.SlugField(max_length=170, blank=True)
    short_description = models.CharField('descrição curta', max_length=180)
    description = models.TextField('descrição completa')
    price = models.DecimalField('preço', max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    promotional_price = models.DecimalField('preço promocional', max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField('imagem principal', upload_to='products/', blank=True, validators=IMAGE_VALIDATORS)
    is_available = models.BooleanField('disponível', default=True)
    is_featured = models.BooleanField('destaque', default=False)
    stock = models.PositiveIntegerField('estoque simulado', default=10)
    preparation_minutes = models.PositiveSmallIntegerField('tempo de preparo', default=45)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['store', 'slug'], name='unique_product_slug_per_store')]
        ordering = ['-is_featured', 'name']

    def clean(self):
        if self.promotional_price and self.promotional_price >= self.price:
            raise ValidationError({'promotional_price': 'O preço promocional deve ser menor que o preço original.'})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:145] or uuid4().hex[:8]
            slug = base
            counter = 2
            while Product.objects.filter(store=self.store, slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def current_price(self):
        return self.promotional_price or self.price

    def __str__(self):
        return f'{self.name} — {self.store.name}'


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='products/gallery/', validators=IMAGE_VALIDATORS)
    alt_text = models.CharField('texto alternativo', max_length=180)
    display_order = models.PositiveSmallIntegerField('ordem', default=0)

    class Meta:
        ordering = ['display_order']


class CustomizationOption(models.Model):
    class Type(models.TextChoices):
        SELECT = 'select', 'Seleção'
        TEXT = 'text', 'Texto'
        BOOLEAN = 'boolean', 'Sim ou não'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='customizations')
    name = models.CharField('nome', max_length=100)
    option_type = models.CharField('tipo', max_length=10, choices=Type.choices, default=Type.SELECT)
    is_required = models.BooleanField('obrigatória', default=False)
    additional_price = models.DecimalField('valor adicional', max_digits=10, decimal_places=2, default=0)
    choices = models.JSONField('opções disponíveis', default=list, blank=True)

    def __str__(self):
        return f'{self.product.name}: {self.name}'


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def subtotal(self):
        return sum((item.subtotal for item in self.items.all()), Decimal('0.00'))

    @property
    def selected_subtotal(self):
        return sum((item.subtotal for item in self.items.all() if item.is_selected), Decimal('0.00'))

    @property
    def selected_count(self):
        return sum(item.quantity for item in self.items.all() if item.is_selected)

    def clear(self):
        self.items.all().delete()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField('quantidade', validators=[MinValueValidator(1)])
    selected_customizations = models.JSONField('personalizações', default=dict, blank=True)
    note = models.CharField('observação', max_length=300, blank=True)
    unit_price = models.DecimalField('preço unitário', max_digits=10, decimal_places=2)
    additional_value = models.DecimalField('valor adicional', max_digits=10, decimal_places=2, default=0)
    is_selected = models.BooleanField('selecionado para checkout', default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name='cart_item_positive_quantity')]

    @property
    def subtotal(self):
        return (self.unit_price + self.additional_value) * self.quantity

    def clean(self):
        if self.quantity > self.product.stock:
            raise ValidationError({'quantity': 'Quantidade superior ao estoque demonstrativo.'})


class Order(models.Model):
    class DeliveryPeriod(models.TextChoices):
        MORNING = 'morning', 'Manhã — 08h às 12h'
        AFTERNOON = 'afternoon', 'Tarde — 12h às 18h'
        EVENING = 'evening', 'Noite — 18h às 21h'

    class PaymentMethod(models.TextChoices):
        PIX = 'pix', 'Pix simulado'
        CARD = 'card', 'Cartão simulado'
        DELIVERY = 'delivery', 'Pagamento na entrega simulado'

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovado (simulado)'
        REFUNDED = 'refunded', 'Estornado (simulado)'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Aguardando confirmação'
        ACCEPTED = 'accepted', 'Pedido aceito'
        PREPARING = 'preparing', 'Em preparação'
        READY = 'ready', 'Pronto para entrega'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Saiu para entrega'
        DELIVERED = 'delivered', 'Entregue'
        REFUSED = 'refused', 'Recusado'
        CANCELLED = 'cancelled', 'Cancelado'

    NEXT_STATUS = {
        Status.PENDING: Status.ACCEPTED,
        Status.ACCEPTED: Status.PREPARING,
        Status.PREPARING: Status.READY,
        Status.READY: Status.OUT_FOR_DELIVERY,
        Status.OUT_FOR_DELIVERY: Status.DELIVERED,
    }

    public_code = models.CharField('código público', max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders')
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='orders')
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    address_snapshot = models.TextField('endereço utilizado')
    recipient_name = models.CharField('nome do destinatário', max_length=120)
    recipient_phone = models.CharField('telefone do destinatário', max_length=20)
    delivery_date = models.DateField('data da entrega')
    delivery_period = models.CharField('período', max_length=12, choices=DeliveryPeriod.choices)
    card_message = models.TextField('mensagem do cartão', max_length=500, blank=True)
    is_anonymous = models.BooleanField('pedido anônimo', default=False)
    notes = models.TextField('observações', max_length=500, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField('taxa de entrega', max_digits=10, decimal_places=2)
    discount = models.DecimalField('desconto simulado', max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField('valor total', max_digits=10, decimal_places=2)
    payment_method = models.CharField('forma de pagamento', max_length=12, choices=PaymentMethod.choices)
    payment_status = models.CharField('status do pagamento', max_length=12, choices=PaymentStatus.choices)
    status = models.CharField('status do pedido', max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.public_code:
            year = timezone.localdate().year
            last = Order.objects.filter(public_code__startswith=f'IFL-{year}-').order_by('-public_code').first()
            sequence = int(last.public_code.rsplit('-', 1)[-1]) + 1 if last else 1
            self.public_code = f'IFL-{year}-{sequence:06d}'
        super().save(*args, **kwargs)

    @property
    def can_advance(self):
        return self.status in self.NEXT_STATUS

    def __str__(self):
        return self.public_code


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField('nome do produto', max_length=140)
    image = models.CharField('imagem', max_length=255, blank=True)
    quantity = models.PositiveIntegerField('quantidade')
    unit_price = models.DecimalField('preço unitário', max_digits=10, decimal_places=2)
    customizations = models.JSONField('personalizações', default=dict, blank=True)
    notes = models.CharField('observações', max_length=300, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name='order_item_positive_quantity')]


class SimulatedPayment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    method = models.CharField('forma', max_length=12, choices=Order.PaymentMethod.choices)
    status = models.CharField(max_length=12, choices=Order.PaymentStatus.choices)
    fake_identifier = models.CharField('identificador fictício', max_length=36, unique=True, default=uuid4)
    amount = models.DecimalField('valor', max_digits=10, decimal_places=2)
    approved_at = models.DateTimeField('aprovação simulada', null=True, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)


class StatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    description = models.CharField('descrição', max_length=255)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField('data e hora', auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name_plural = 'históricos de status'

    def delete(self, *args, **kwargs):
        raise ValidationError('O histórico de status é imutável.')


class Review(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField('nota', validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField('comentário', max_length=800)
    created_at = models.DateTimeField('criada em', auto_now_add=True)
    is_approved = models.BooleanField('aprovada', default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'avaliação'
        verbose_name_plural = 'avaliações'

    def clean(self):
        if self.order_id:
            if self.order.status != Order.Status.DELIVERED:
                raise ValidationError('Apenas pedidos entregues podem ser avaliados.')
            if self.order.customer_id != self.customer_id or self.order.store_id != self.store_id:
                raise ValidationError('A avaliação deve corresponder ao cliente e à loja do pedido.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        ratings = self.store.reviews.filter(is_approved=True).aggregate(avg=models.Avg('rating'), count=models.Count('id'))
        self.store.average_rating = ratings['avg'] or 0
        self.store.review_count = ratings['count'] or 0
        self.store.save(update_fields=['average_rating', 'review_count'])
