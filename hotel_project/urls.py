"""
URL configuration for hotel_project project.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseServerError
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions


# Swagger/OpenAPI configuration
schema_view = get_schema_view(
    openapi.Info(
        title="HotelERP API",
        default_version='v1',
        description="API complète pour la gestion hôtelière",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@hotelmanager.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Admin Django (pour templates)
    path('admin/', admin.site.urls),
    
    # ========== Authentification (DOIT ÊTRE AVANT TOUT) ==========
    path('auth/', include(('apps.authentication.urls', 'authentication'), namespace='authentication')),
    
    # ========== API Documentation ==========
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/docs.json/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # ========== API REST ==========
    path('api/auth/', include(('apps.authentication.urls', 'authentication_api'), namespace='authentication_api')),
    path('api/clients/', include('apps.clients.api_urls')),
    path('api/fournisseurs/', include('apps.fournisseurs.api_urls')),
    path('api/restaurant/', include('apps.restaurant.api_urls')),
    path('api/factures/', include('apps.facturation.api_urls')),
    
    # ========== Interface Web ==========
    path('clients/', include('apps.clients.urls')),
    path('hotel/', include('apps.hotel.urls')),
    path('restaurant/', include('apps.restaurant.urls')),
    path('pos/', include('apps.pos.urls')),
    path('facturation/', include('apps.facturation.urls')),  # ← Changé de 'factures/' à 'facturation/'
    path('paiements/', include('apps.paiements.urls')),
    path('comptabilite/', include('apps.comptabilite.urls')),
    path('', include('apps.dashboard.urls')),
    path('rh/', include('apps.rh.urls')),
    path('paie/', include('apps.paie.urls')),
    path('stock/', include('apps.stock.urls')),
    path('fournisseurs/', include('apps.fournisseurs.urls')),
    path('catalogue/', include('apps.catalogue.urls')),
    path('tresorerie/', include('apps.tresorerie.urls')),
 
     
]

# Sert les fichiers media en production via FileResponse
def servir_media(request, path):
    import mimetypes, os, logging
    logger = logging.getLogger('servir_media')
    file_path = settings.MEDIA_ROOT / path
    safe_path = os.path.normpath(str(file_path))
    logger.info('servir_media: path=%s, file_path=%s, exists=%s', path, safe_path, file_path.exists())
    if not safe_path.startswith(str(settings.MEDIA_ROOT)):
        raise Http404("Chemin invalide")
    if not file_path.exists() or not file_path.is_file():
        logger.error('Fichier introuvable: %s', safe_path)
        raise Http404("Fichier introuvable")
    try:
        content_type, _ = mimetypes.guess_type(str(file_path))
        f = open(file_path, 'rb')
        resp = FileResponse(f, content_type=content_type or 'application/octet-stream')
        resp['Cache-Control'] = 'public, max-age=86400'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp
    except (PermissionError, OSError) as e:
        return HttpResponseServerError(f"Erreur de lecture: {e}")

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', servir_media),
]