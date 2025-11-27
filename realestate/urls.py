from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apartments.urls')),  # Apartments is now the homepage
    path('users/', include('users.urls')),
    path('accounts/', include('allauth.urls')),

    path('buildings/', include('buildings.urls')),
    path('apartments/', include('apartments.urls')),  # Keep apartments also accessible at /apartments/
    path('applications/', include('applications.urls')),
    path('applicants/', include('applicants.urls')),
    path("doc_analysis/", include("doc_analysis.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
