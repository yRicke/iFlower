from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Cart, Order, OrderItem, ServiceArea, SimulatedPayment, StatusHistory


@transaction.atomic
def checkout_cart(*, cart: Cart, customer, cleaned_data: dict) -> Order:
    """Validate prices and stock under locks, then snapshot a complete order."""
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    items = list(
        cart.items.filter(is_selected=True).select_related('product', 'product__store').select_for_update()
    )
    if not items:
        raise ValidationError('Seu carrinho está vazio.')
    store_ids = {item.product.store_id for item in items}
    if len(store_ids) != 1:
        raise ValidationError('Selecione itens de apenas uma loja por checkout.')
    store = items[0].product.store

    address = cleaned_data['address']
    if address.user_id != customer.id:
        raise PermissionDenied('Endereço inválido.')
    if cleaned_data['delivery_date'] < timezone.localdate():
        raise ValidationError('A data de entrega não pode estar no passado.')

    subtotal = Decimal('0.00')
    for item in items:
        product = item.product
        if item.quantity < 1:
            raise ValidationError(f'Quantidade inválida para {product.name}.')
        if not product.is_available or not product.store.is_active:
            raise ValidationError(f'{product.name} não está mais disponível.')
        if item.quantity > product.stock:
            raise ValidationError(f'Estoque insuficiente para {product.name}.')
        item.unit_price = product.current_price
        subtotal += item.subtotal

    area = ServiceArea.objects.filter(
        store=store,
        city__iexact=address.city,
        neighborhood__iexact=address.neighborhood,
        is_active=True,
    ).first()
    delivery_fee = store.default_delivery_fee + (area.additional_fee if area else Decimal('0.00'))
    total = subtotal + delivery_fee
    payment_status = (
        Order.PaymentStatus.PENDING
        if cleaned_data['payment_method'] == Order.PaymentMethod.DELIVERY
        else Order.PaymentStatus.APPROVED
    )
    snapshot = (
        f'{address.street}, {address.number}'
        f'{f" — {address.complement}" if address.complement else ""}; '
        f'{address.neighborhood}, {address.city}/{address.state}; CEP {address.postal_code}'
    )
    order = Order.objects.create(
        customer=customer,
        store=store,
        address=address,
        address_snapshot=snapshot,
        recipient_name=cleaned_data['recipient_name'],
        recipient_phone=cleaned_data['recipient_phone'],
        delivery_date=cleaned_data['delivery_date'],
        delivery_period=cleaned_data['delivery_period'],
        card_message=cleaned_data['card_message'],
        is_anonymous=cleaned_data['is_anonymous'],
        notes=cleaned_data['notes'],
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total,
        payment_method=cleaned_data['payment_method'],
        payment_status=payment_status,
        status=Order.Status.ACCEPTED if store.auto_accept_orders else Order.Status.PENDING,
    )
    for item in items:
        product = item.product
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            image=product.image.name if product.image else '',
            quantity=item.quantity,
            unit_price=item.unit_price,
            customizations=item.selected_customizations,
            notes=item.note,
            subtotal=item.subtotal,
        )
        product.stock -= item.quantity
        product.save(update_fields=['stock'])

    SimulatedPayment.objects.create(
        order=order,
        method=order.payment_method,
        status=payment_status,
        amount=total,
        approved_at=timezone.now() if payment_status == Order.PaymentStatus.APPROVED else None,
    )
    StatusHistory.objects.create(
        order=order,
        status=Order.Status.PENDING,
        description='Pedido criado e enviado à loja para confirmação.',
        responsible=customer,
    )
    if store.auto_accept_orders:
        # Nesta versão, a confirmação imediata vem habilitada. Em versões futuras,
        # a loja deve revisar o pedido antes de aceitá-lo ou habilitar esta opção.
        StatusHistory.objects.create(
            order=order,
            status=Order.Status.ACCEPTED,
            description='Pedido confirmado automaticamente pela loja.',
            responsible=store.owner,
        )
    cart.items.filter(pk__in=[item.pk for item in items]).delete()
    cart.save(update_fields=['updated_at'])
    return order


STATUS_DESCRIPTIONS = {
    Order.Status.ACCEPTED: 'A loja aceitou o pedido.',
    Order.Status.PREPARING: 'Seu presente está sendo preparado com carinho.',
    Order.Status.READY: 'Pedido pronto e aguardando a entrega simulada.',
    Order.Status.OUT_FOR_DELIVERY: 'O pedido saiu para entrega simulada.',
    Order.Status.DELIVERED: 'Entrega simulada concluída.',
    Order.Status.REFUSED: 'A loja recusou o pedido.',
    Order.Status.CANCELLED: 'O pedido foi cancelado.',
}


@transaction.atomic
def transition_order(*, order: Order, actor, target_status: str | None = None) -> Order:
    """Apply only coherent transitions and preserve an immutable audit trail."""
    order = Order.objects.select_for_update().select_related('store').get(pk=order.pk)
    if not actor.is_staff and order.store.owner_id != actor.id:
        raise PermissionDenied('Você não pode alterar este pedido.')
    expected = Order.NEXT_STATUS.get(order.status)
    target_status = target_status or expected
    if target_status is None:
        raise ValidationError('Este pedido está em um status terminal e não pode avançar.')
    if target_status == Order.Status.REFUSED and order.status != Order.Status.PENDING:
        raise ValidationError('Apenas pedidos aguardando confirmação podem ser recusados.')
    if target_status not in {expected, Order.Status.REFUSED}:
        raise ValidationError('Transição de status inválida.')
    order.status = target_status
    order.save(update_fields=['status', 'updated_at'])
    StatusHistory.objects.create(
        order=order,
        status=target_status,
        description=STATUS_DESCRIPTIONS[target_status],
        responsible=actor,
    )
    return order
