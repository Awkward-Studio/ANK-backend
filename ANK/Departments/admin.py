from django.contrib import admin
from Departments.models import (
    Department,
    EventDepartment,
    EventDepartmentStaffAssignment,
    BudgetFieldPermission,
)


admin.site.register(Department)
admin.site.register(EventDepartmentStaffAssignment)
admin.site.register(EventDepartment)
