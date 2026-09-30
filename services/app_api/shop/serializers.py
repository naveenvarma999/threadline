from django.conf import settings
from rest_framework import serializers

from shop.models import Article, Customer, Event


class ArticleSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = ["article_id", "prod_name", "product_type", "product_group", "colour", "department",
                  "index_group", "garment_group", "description", "price", "image_url"]

    def get_image_url(self, obj: Article) -> str | None:
        if not settings.IMAGE_BASE_URL:
            return None
        aid = f"{obj.article_id:010d}"
        return f"{settings.IMAGE_BASE_URL.rstrip('/')}/{aid[:3]}/{aid}.jpg"


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["customer_id", "age", "club_member_status", "n_purchases"]


class FeedRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    session_article_ids = serializers.ListField(child=serializers.IntegerField(), required=False, max_length=50)
    age = serializers.IntegerField(required=False, allow_null=True, min_value=10, max_value=100)


class EventSerializer(serializers.ModelSerializer):
    customer_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    article_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Event
        fields = ["session_id", "customer_id", "article_id", "event_type", "placement", "model_version"]

    def validate(self, data):
        cid = data.pop("customer_id", None)
        aid = data.pop("article_id", None)
        data["customer"] = Customer.objects.filter(pk=cid).first() if cid else None
        data["article"] = Article.objects.filter(pk=aid).first() if aid else None
        return data


class CheckoutSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=64)
    customer_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    article_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=50)
