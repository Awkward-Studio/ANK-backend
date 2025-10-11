from django.contrib import admin
from Departments.models import (
    Department,
    EventDepartment,
    EventDepartmentStaffAssignment,
    BudgetFieldPermission,
)


admin.register(Department)
admin.register(EventDepartmentStaffAssignment)
admin.register(EventDepartment)
