from django.urls import path

from shop import views

urlpatterns = [
    path("health/", views.health),
    path("articles/", views.ArticleList.as_view()),
    path("articles/facets/", views.facets),
    path("articles/<int:pk>/", views.ArticleDetail.as_view()),
    path("articles/<int:pk>/similar/", views.article_similar),
    path("articles/<int:pk>/complete-the-look/", views.article_complete_the_look),
    path("customers/demo/", views.demo_customers),
    path("customers/<str:pk>/", views.customer_detail),
    path("feed/", views.feed),
    path("events/", views.events),
    path("checkout/", views.checkout),
    path("ops/overview/", views.ops_overview),
    path("ops/models/", views.ops_models),
    path("ops/models/<str:version>/promote/", views.ops_promote),
]
