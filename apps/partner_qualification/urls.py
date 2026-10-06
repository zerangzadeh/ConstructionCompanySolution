from django.urls import path

from apps.partner_qualification import views

app_name = "partner_qualification"
urlpatterns = [path("", views.workbench, name="workbench")]
