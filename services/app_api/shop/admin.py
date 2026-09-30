from django.contrib import admin

from shop.models import Article, Customer, Event, Purchase


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("article_id", "prod_name", "product_type", "colour", "index_group", "price", "sales_last_4w")
    list_filter = ("product_group", "index_group", "colour")
    search_fields = ("prod_name", "product_type", "article_id")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_id", "age", "club_member_status", "n_purchases")
    search_fields = ("customer_id",)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("customer", "article", "purchased_at", "price", "channel")
    raw_id_fields = ("customer", "article")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "placement", "article", "customer", "model_version")
    list_filter = ("event_type", "placement", "model_version")
    raw_id_fields = ("customer", "article")
