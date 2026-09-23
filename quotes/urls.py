from django.urls import path

from . import views


urlpatterns = [
    path("health", views.health, name="health"),
    path(
        "import",
        views.import_snapshot,
        name="import-snapshot",
    ),
    
    path(
        "catalog/source",
        views.set_catalog_source,
        name="set-catalog-source",
    ),

    path(
        "quotes/<str:quote_id>",
        views.get_quote,
        name="get-quote",
    ),
    path(
        "catalog/<str:quote_id>",
        views.update_quote,
        name="update-quote",
    ),
    path(
        "catalog/<str:quote_id>",
        views.delete_quote,
        name="delete-quote",
    ),
    path("stats", views.stats, name="stats"),
]