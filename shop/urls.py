from django.urls import path
from . import views

urlpatterns = [
    # 🔮 --- POINT D'ENTRÉE DU SITE (ÉCRAN DE BIENVENUE) ---
    # Désormais, l'adresse principale lance d'abord l'écran de sélection.
    path('', views.bienvenue, name='racine_bienvenue'),

    # 🛍️ --- ACCUEIL DE LA BOUTIQUE MULTI-VENDEUR ---
    # Vos articles migrent vers l'adresse '/boutique/' pour libérer la racine.
    path('boutique/', views.accueil, name='accueil'),
    path('produit/<int:pk>/', views.detail_produit, name='detail_produit'),
    
    # 🖨️ --- ESPACE SERVICES D'IMPRESSION ---
    path('impressions/', views.page_impressions, name='page_impressions'),
    path('impressions/admin/commandes/', views.liste_commandes_admin, name='liste_commandes_admin'),
    path('impressions/admin/basculer-remise/<int:commande_id>/', views.basculer_remise, name='basculer_remise'),
    path('impressions/admin/generer-bon/<int:commande_id>/', views.generer_bon_pdf, name='generer_bon_pdf'),
    
    # 👥 --- ESPACE VENDEUR (COMPTES & VITRINE) ---
    path('vendeur/inscription/', views.inscription_vendeur, name='inscription_vendeur'),
    path('vendeur/connexion/', views.connexion_vendeur, name='connexion'),  # Utile pour le décorateur @login_required
    path('vendeur/deconnexion/', views.deconnexion_vendeur, name='deconnexion_vendeur'),
    path('vendeur/dashboard/', views.dashboard_vendeur, name='dashboard_vendeur'),
    path('vendeur/produit/ajouter/', views.ajouter_produit, name='ajouter_produit'),
    path('vendeur/produit/supprimer/<int:pk>/', views.supprimer_produit, name='supprimer_produit'),
    
    # 🛒 --- GESTION DU PANIER CLIENT ---
    path('panier/', views.panier_detail, name='panier_detail'),
    path('panier/ajouter/<int:produit_id>/', views.panier_ajouter, name='panier_ajouter'),
    path('panier/supprimer/<int:produit_id>/', views.panier_supprimer, name='panier_supprimer'),
    
    # 📦 --- COMMANDES ET LIVRAISONS ---
    path('commande/directe/<int:pk>/', views.passer_commande, name='passer_commande'),  # Article unique
    path('commande/panier/', views.passer_commande_panier, name='passer_commande_panier'),  # Multi-articles
    path('commande/suivi/<int:pk>/', views.suivi_commande, name='suivi_commande'),
    path('commande/statut/<int:pk>/<str:nouveau_statut>/', views.modifier_statut_commande, name='modifier_statut_commande'),
    
    # 🤖 --- ASSISTANT VIRTUEL (IA CHATBOT) ---
    path('api/assistant/chat/', views.assistant_chatbot_api, name='assistant_chat_api'),
    path('impressions/admin/commandes/', views.liste_commandes_admin, name='liste_commandes_admin'),
    path('impressions/admin/valider/<int:commande_id>/', views.valider_commande_impression, name='valider_commande_impression'),
    path('impressions/admin/livraison/<int:commande_id>/', views.voir_bon_livraison, name='voir_bon_livraison_admin'),
    path('impressions/admin/pdf/<int:commande_id>/', views.generer_bon_pdf, name='generer_bon_pdf'),
    path('impressions/', views.page_impressions, name='page_impressions'),
    path('impressions/api/panier/', views.modifier_panier_print_api, name='modifier_panier_print_api'),
    path('impression/conseiller/', views.page_conseiller, name='page_conseiller'),
    path('impression/prestations/', views.page_prestations, name='page_prestations'),
    path('impression/prestations/<int:prestation_id>/', views.detail_prestation, name='detail_prestation'),
    path('impression/bon-commande/<int:commande_id>/', views.voir_bon_commande, name='voir_bon_commande'),
    path('impression/bon-livraison/<int:commande_id>/', views.voir_bon_livraison, name='voir_bon_livraison'),
    path('impressions/commande/<int:commande_id>/public/', views.voir_bon_commande_public, name='voir_bon_commande_public'),
    path('impressions/admin/check-code/', views.verifier_code_admin, name='verifier_code_admin'),
    path('commande/confirmer/', views.confirmer_commande_client, name='confirmer_commande_client'),
    path('impression/prestations/<int:prestation_id>/calcul/', views.calculer_tarif_ajax, name='calculer_tarif_ajax'),
]