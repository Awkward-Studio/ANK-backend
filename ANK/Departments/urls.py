from django.urls import path
from Departments.views import (
    DepartmentList,
    DepartmentDetail,
    EventDepartmentList,
    EventDepartmentDetail,
    EventDepartmentsByEventAPIView,
    EventDepartmentStaffAssignmentList,
    EventDepartmentStaffAssignmentDetail,
    StaffAssignmentsByEventDepartmentAPIView,
    BudgetLineItemList,
    BudgetLineItemDetail,
    BudgetItemsByEventDepartmentAPIView,
    BudgetFieldPermissionList,
    BudgetFieldPermissionDetail,
    FieldPermsByEventDepartmentAPIView,
    EventDepartmentUserFieldPermsAPIView,
    EventDepartmentUserFieldPermsSetAPIView,
    EventDepartmentUserFieldPermsAddAPIView,
    EventDepartmentUserFieldPermsRemoveAPIView,
    UserEventScopedDepartmentFieldAccessAPIView,
)

urlpatterns = [
    # ─── Departments (global) ────────────────────────────────────────────────
    path("departments/", DepartmentList.as_view(), name="departments-list"),
    path(
        "departments/<uuid:pk>/", DepartmentDetail.as_view(), name="departments-detail"
    ),
    # ─── Event Departments ──────────────────────────────────────────────────
    path(
        "event-departments/",
        EventDepartmentList.as_view(),
        name="eventdepartments-list",
    ),
    path(
        "event-departments/<uuid:pk>/",
        EventDepartmentDetail.as_view(),
        name="eventdepartments-detail",
    ),
    path(
        "events/<uuid:pk>/departments/",
        EventDepartmentsByEventAPIView.as_view(),
        name="events-departments-list",
    ),
    # ─── Event Department Staff Assignments ─────────────────────────────────
    path(
        "event-department-staff/",
        EventDepartmentStaffAssignmentList.as_view(),
        name="eventdepartmentstaff-list",
    ),
    path(
        "event-department-staff/<uuid:pk>/",
        EventDepartmentStaffAssignmentDetail.as_view(),
        name="eventdepartmentstaff-detail",
    ),
    path(
        "event-departments/<uuid:pk>/staff/",
        StaffAssignmentsByEventDepartmentAPIView.as_view(),
        name="eventdepartment-staff-list",
    ),
    # ─── Budget Line Items ──────────────────────────────────────────────────
    path("budget-items/", BudgetLineItemList.as_view(), name="budgetitems-list"),
    path(
        "budget-items/<uuid:pk>/",
        BudgetLineItemDetail.as_view(),
        name="budgetitems-detail",
    ),
    path(
        "event-departments/<uuid:pk>/budget-items/",
        BudgetItemsByEventDepartmentAPIView.as_view(),
        name="eventdepartment-budgetitems-list",
    ),
    # ─── Budget Field Permissions ───────────────────────────────────────────
    path(
        "budget-field-permissions/",
        BudgetFieldPermissionList.as_view(),
        name="budgetfieldpermissions-list",
    ),
    path(
        "budget-field-permissions/<uuid:pk>/",
        BudgetFieldPermissionDetail.as_view(),
        name="budgetfieldpermissions-detail",
    ),
    path(
        "event-departments/<uuid:pk>/field-permissions/",
        FieldPermsByEventDepartmentAPIView.as_view(),
        name="eventdepartment-fieldpermissions-list",
    ),
    # ─── User-Specific Field Permissions ────────────────────────────────────
    path(
        "event-departments/<uuid:event_dept_pk>/users/<uuid:user_pk>/field-permissions/",
        EventDepartmentUserFieldPermsAPIView.as_view(),
        name="eventdepartment-user-fieldpermissions-list",
    ),
    path(
        "event-departments/<uuid:event_dept_pk>/users/<uuid:user_pk>/field-permissions/set/",
        EventDepartmentUserFieldPermsSetAPIView.as_view(),
        name="eventdepartment-user-fieldpermissions-set",
    ),
    path(
        "event-departments/<uuid:event_dept_pk>/users/<uuid:user_pk>/field-permissions/add/",
        EventDepartmentUserFieldPermsAddAPIView.as_view(),
        name="eventdepartment-user-fieldpermissions-add",
    ),
    path(
        "event-departments/<uuid:event_dept_pk>/users/<uuid:user_pk>/field-permissions/remove/",
        EventDepartmentUserFieldPermsRemoveAPIView.as_view(),
        name="eventdepartment-user-fieldpermissions-remove",
    ),
    path(
        "users/<uuid:user_pk>/events/<uuid:event_pk>/departments/field-access/",
        UserEventScopedDepartmentFieldAccessAPIView.as_view(),
        name="user-eventdept-field-access-by-event",
    ),
]
