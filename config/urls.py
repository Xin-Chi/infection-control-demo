from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls', namespace='accounts')),
    path('infection/', include('infection.urls', namespace='infection')),
    path('research/', include('research.urls', namespace='research')),
]
