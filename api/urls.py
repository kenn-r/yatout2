from django.urls import path
from .views import LoginMobileView, RegisterMobileView, RecevoirImpressionView, VerifierBonCommandeView, TransfererEnBLView, liste_commandes_en_attente_view
from . import views

urlpatterns = [
    path('login/', LoginMobileView.as_view(), name='api_login'),
    path('register/', RegisterMobileView.as_view(), name='api_register'),
    path('produits/', views.liste_produits_api, name='api_produits'),
    path('commandes/', views.gestion_commandes_api, name='api_commandes'),
    path('produits/<int:pk>/', views.liste_produits_api, name='api_details_produit'),
    path('vendeur/produits/', views.liste_produits_api, name='api_produits_vendeur'),
    path('impressions/', views.gestion_impressions_api, name='api_impressions'),
    path('vendeur/recevoir-impression/', RecevoirImpressionView.as_view(), name='recevoir_impression'),
    path('vendeur/impression/<int:pk>/verifier/', VerifierBonCommandeView.as_view(), name='api_verifier_bc'),
    path('vendeur/impression/<int:pk>/transferer-bl/', TransfererEnBLView.as_view(), name='api_transferer_bl'),
    path('prestations/', views.liste_prestations_api, name='api_liste_prestations'),
    path('impressions/en-attente/', liste_commandes_en_attente_view, name='commandes-en-attente'),
    path('vendeur/impressions/termines/', views.liste_bons_termines_view, name='bons-termines'),
]