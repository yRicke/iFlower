from django.contrib import admin

from .models import (
    Address,
    Cart,
    CartItem,
    Category,
    CustomizationOption,
    Order,
    OrderItem,
    Product,
    ProductImage,
    Profile,
    Review,
    ServiceArea,
    SimulatedPayment,
    StatusHistory,
    Store,
)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'city', 'average_rating', 'auto_accept_orders', 'is_active', 'is_featured')
    list_filter = ('auto_accept_orders', 'is_active', 'is_featured', 'state')
    search_fields = ('name', 'owner__username', 'city')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'category', 'price', 'stock', 'is_available', 'is_featured')
    list_filter = ('store', 'category', 'is_available', 'is_featured')
    search_fields = ('name', 'store__name')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('public_code', 'customer', 'store', 'status', 'payment_status', 'total', 'created_at')
    list_filter = ('status', 'payment_status', 'store')
    search_fields = ('public_code', 'customer__username', 'recipient_name')
    readonly_fields = ('public_code', 'subtotal', 'delivery_fee', 'discount', 'total', 'created_at', 'updated_at')


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'responsible', 'created_at')
    readonly_fields = ('order', 'status', 'description', 'responsible', 'created_at')

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register([Profile, Address, ServiceArea, Category, ProductImage, CustomizationOption, Cart, CartItem, OrderItem, SimulatedPayment, Review])
admin.site.site_header = 'iFlower — Administração'
admin.site.site_title = 'iFlower Admin'
