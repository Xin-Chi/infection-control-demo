from django.contrib import admin

from .models import (
    CategoryPoolEntry, ConversionCategory, ConversionEntry, InfectionCategory, Token,
)


@admin.register(CategoryPoolEntry)
class CategoryPoolEntryAdmin(admin.ModelAdmin):
    list_display = ('category', 'token', 'status', 'categorized_count')
    list_filter = ('status', 'category')


admin.site.register([Token, InfectionCategory, ConversionCategory, ConversionEntry])
