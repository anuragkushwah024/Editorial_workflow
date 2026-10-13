from django.contrib import admin

from .models import Section, SectionAssignment


class SectionAssignmentInline(admin.TabularInline):
    model = SectionAssignment
    fk_name = "section"
    extra = 0


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_archived"]
    list_filter = ["is_archived"]
    inlines = [SectionAssignmentInline]
