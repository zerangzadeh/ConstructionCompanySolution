from django.urls import path

from apps.materials import governance_views, views

app_name = "materials"

urlpatterns = [
    path("governance/", governance_views.index, name="governance"),
    path("governance/actions/<str:action>/", governance_views.action, name="governance_action"),
    path("", views.material_list, name="material_list"),
    path("create/", views.material_create, name="material_create"),
    path("<uuid:material_id>/", views.material_detail, name="material_detail"),
    path(
        "<uuid:material_id>/archive/", views.material_archive, name="material_archive"
    ),
    path("categories/", views.category_list, name="category_list"),
    path("categories/create/", views.category_create, name="category_create"),
    path(
        "categories/<uuid:category_id>/", views.category_detail, name="category_detail"
    ),
    path(
        "categories/<uuid:category_id>/archive/",
        views.category_archive,
        name="category_archive",
    ),
    path("units/", views.unit_list, name="unit_list"),
    path("units/create/", views.unit_create, name="unit_create"),
    path("units/<uuid:unit_id>/archive/", views.unit_archive, name="unit_archive"),
]
