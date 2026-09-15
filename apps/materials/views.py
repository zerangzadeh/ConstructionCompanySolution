from django.core.exceptions import PermissionDenied
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.materials.forms import MaterialCategoryForm, MaterialForm, UnitOfMeasureForm
from apps.materials.models import (
    Material,
    MaterialCategory,
    UnitCategory,
    UnitOfMeasure,
)
from apps.materials.services import (
    archive_material,
    archive_material_category,
    archive_unit_of_measure,
    create_material,
    create_material_category,
    create_unit_of_measure,
    get_organization_material_categories,
    get_organization_materials,
    get_organization_units,
    update_material,
    update_material_category,
)
from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.UNITS_VIEW)
def unit_list(request: HttpRequest) -> HttpResponse:
    units = get_organization_units(user=request.user, organization=request.organization)
    units = apply_table_filters(
        units,
        request,
        text_fields={"code": ("code",), "name": ("name", "symbol")},
        choice_fields={"category": ("category", UnitCategory.values)},
    )
    return render(
        request,
        "materials/unit_list.html",
        {
            "units": units,
            "filters": build_table_filters(
                request,
                [
                    {"name": "code", "kind": "text", "label": "کد"},
                    {"name": "name", "kind": "text", "label": "نام یا نماد"},
                    None,
                    {
                        "name": "category",
                        "kind": "select",
                        "label": "نوع",
                        "choices": UnitCategory.choices,
                    },
                    None,
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.UNITS_CREATE)
def unit_create(request: HttpRequest) -> HttpResponse:
    form = UnitOfMeasureForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_unit_of_measure(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("materials:unit_list")
    return render(request, "materials/unit_form.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.UNITS_ARCHIVE)
@require_POST
def unit_archive(request: HttpRequest, unit_id: str) -> HttpResponse:
    unit = UnitOfMeasure.objects.filter(
        pk=unit_id, organization=request.organization, archived_at__isnull=True
    ).first()
    if unit is None:
        return HttpResponseNotFound("واحد اندازه‌گیری یافت نشد.")
    try:
        archive_unit_of_measure(
            organization=request.organization, actor=request.user, unit=unit
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("materials:unit_list")


def _get_active_category(
    request: HttpRequest, category_id: str
) -> MaterialCategory | None:
    return MaterialCategory.objects.filter(
        pk=category_id, organization=request.organization, archived_at__isnull=True
    ).first()


def _get_active_material(request: HttpRequest, material_id: str) -> Material | None:
    return Material.objects.filter(
        pk=material_id, organization=request.organization, archived_at__isnull=True
    ).first()


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIAL_CATEGORIES_VIEW)
def category_list(request: HttpRequest) -> HttpResponse:
    categories = get_organization_material_categories(
        user=request.user, organization=request.organization
    ).select_related("parent")
    return render(request, "materials/category_list.html", {"categories": categories})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIAL_CATEGORIES_CREATE)
def category_create(request: HttpRequest) -> HttpResponse:
    form = MaterialCategoryForm(
        request.POST or None, organization_id=request.organization.id
    )
    if request.method == "POST" and form.is_valid():
        try:
            create_material_category(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("materials:category_list")
    return render(
        request, "materials/category_form.html", {"form": form, "category": None}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIAL_CATEGORIES_VIEW)
def category_detail(request: HttpRequest, category_id: str) -> HttpResponse:
    if request.method == "POST":
        require_organization_permission(
            request,
            BusinessPermissionCode.MATERIAL_CATEGORIES_CHANGE,
            "اجازه ویرایش دسته‌بندی مصالح را ندارید.",
        )
    category = _get_active_category(request, category_id)
    if category is None:
        return HttpResponseNotFound("دسته‌بندی مصالح یافت نشد.")
    form = MaterialCategoryForm(
        request.POST or None, instance=category, organization_id=request.organization.id
    )
    if request.method == "GET" and not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MATERIAL_CATEGORIES_CHANGE,
    ):
        for field in form.fields.values():
            field.disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            category = update_material_category(
                organization=request.organization,
                actor=request.user,
                category=category,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("materials:category_detail", category_id=category.pk)
    return render(
        request, "materials/category_form.html", {"form": form, "category": category}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIAL_CATEGORIES_ARCHIVE)
@require_POST
def category_archive(request: HttpRequest, category_id: str) -> HttpResponse:
    category = _get_active_category(request, category_id)
    if category is None:
        return HttpResponseNotFound("دسته‌بندی مصالح یافت نشد.")
    try:
        archive_material_category(
            organization=request.organization, actor=request.user, category=category
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("materials:category_list")


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIALS_VIEW)
def material_list(request: HttpRequest) -> HttpResponse:
    materials = get_organization_materials(
        user=request.user,
        organization=request.organization,
        search="",
    )
    materials = apply_table_filters(
        materials,
        request,
        text_fields={
            "code": ("code",),
            "name": ("name",),
            "category": ("category__name",),
        },
    )
    return render(
        request,
        "materials/material_list.html",
        {
            "materials": materials,
            "filters": build_table_filters(
                request,
                [
                    {"name": "code", "kind": "text", "label": "کد"},
                    {"name": "name", "kind": "text", "label": "نام مصالح"},
                    None,
                    {"name": "category", "kind": "text", "label": "دسته‌بندی"},
                    None,
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIALS_CREATE)
def material_create(request: HttpRequest) -> HttpResponse:
    form = MaterialForm(request.POST or None, organization_id=request.organization.id)
    if request.method == "POST" and form.is_valid():
        try:
            material = create_material(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("materials:material_detail", material_id=material.pk)
    return render(
        request, "materials/material_form.html", {"form": form, "material": None}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIALS_VIEW)
def material_detail(request: HttpRequest, material_id: str) -> HttpResponse:
    if request.method == "POST":
        require_organization_permission(
            request,
            BusinessPermissionCode.MATERIALS_CHANGE,
            "اجازه ویرایش مصالح را ندارید.",
        )
    material = _get_active_material(request, material_id)
    if material is None:
        return HttpResponseNotFound("مصالح یافت نشد.")
    form = MaterialForm(
        request.POST or None, instance=material, organization_id=request.organization.id
    )
    if request.method == "GET" and not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.MATERIALS_CHANGE,
    ):
        for field in form.fields.values():
            field.disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            material = update_material(
                organization=request.organization,
                actor=request.user,
                material=material,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("materials:material_detail", material_id=material.pk)
    return render(
        request, "materials/material_form.html", {"form": form, "material": material}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.MATERIALS_ARCHIVE)
@require_POST
def material_archive(request: HttpRequest, material_id: str) -> HttpResponse:
    material = _get_active_material(request, material_id)
    if material is None:
        return HttpResponseNotFound("مصالح یافت نشد.")
    try:
        archive_material(
            organization=request.organization, actor=request.user, material=material
        )
    except (PermissionDenied, ValueError) as exc:
        return HttpResponseForbidden(str(exc))
    return redirect("materials:material_list")
