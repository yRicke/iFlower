from django.db.models import Sum

from .models import CartItem


def cart_summary(request):
    """Expose the selected cart quantity without creating a cart as a side effect."""
    if not request.user.is_authenticated:
        return {'cart_selected_count': 0}
    count = CartItem.objects.filter(
        cart__user=request.user,
        is_selected=True,
    ).aggregate(total=Sum('quantity'))['total']
    return {'cart_selected_count': count or 0}
