from django.contrib import admin

from .models import Profile, SectionPermission, TopicPermission


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'organization', 'de_identification')


admin.site.register([SectionPermission, TopicPermission])
