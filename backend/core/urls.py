from django.urls import path

from .views import AccountDataDeleteView, AccountExportView, health_check

urlpatterns = [
    path("health/", health_check, name="health"),
    path("account/export/", AccountExportView.as_view(), name="account-export"),
    path("account/data/", AccountDataDeleteView.as_view(), name="account-data-delete"),
]
