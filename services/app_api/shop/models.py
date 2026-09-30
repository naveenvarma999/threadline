from django.db import models


class Article(models.Model):
    article_id = models.IntegerField(primary_key=True)
    prod_name = models.CharField(max_length=200)
    product_type = models.CharField(max_length=80, db_index=True)
    product_group = models.CharField(max_length=80, db_index=True)
    colour = models.CharField(max_length=60, db_index=True)
    department = models.CharField(max_length=120)
    index_group = models.CharField(max_length=60, db_index=True)
    garment_group = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, help_text="Display price in GBP")
    sales_last_4w = models.IntegerField(default=0)

    class Meta:
        ordering = ["-sales_last_4w", "article_id"]

    def __str__(self) -> str:
        return f"{self.article_id} {self.prod_name}"


class Customer(models.Model):
    customer_id = models.CharField(max_length=64, primary_key=True)
    age = models.PositiveSmallIntegerField(null=True)
    club_member_status = models.CharField(max_length=20, blank=True)
    fashion_news_frequency = models.CharField(max_length=20, blank=True)
    n_purchases = models.IntegerField(default=0)

    def __str__(self) -> str:
        return self.customer_id


class Purchase(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="purchases")
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    purchased_at = models.DateTimeField(db_index=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    channel = models.PositiveSmallIntegerField(default=2, help_text="1 = store, 2 = online")

    class Meta:
        ordering = ["-purchased_at"]


class Event(models.Model):
    """Interaction log. Exported to S3 to evaluate and retrain the recommender."""

    class Type(models.TextChoices):
        IMPRESSION = "impression"
        CLICK = "click"
        ADD_TO_CART = "add_to_cart"
        PURCHASE = "purchase"

    session_id = models.CharField(max_length=64, db_index=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL)
    article = models.ForeignKey(Article, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    placement = models.CharField(max_length=40, blank=True, help_text="feed row or page the item was shown in")
    model_version = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["event_type", "placement"])]
