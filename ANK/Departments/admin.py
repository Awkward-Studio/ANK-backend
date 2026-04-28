from django.contrib import admin
from Departments.models import (
    Department,
    EventDepartment,
    EventDepartmentStaffAssignment,
    EventHeadAssignment,
    BudgetFieldPermission,
)


admin.site.register(Department)
admin.site.register(EventDepartmentStaffAssignment)
admin.site.register(EventHeadAssignment)
admin.site.register(EventDepartment)
admin.site.register(BudgetFieldPermission)
