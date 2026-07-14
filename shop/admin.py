from django.contrib import admin
from django.shortcuts import render
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from .models import (
    Vendeur, Produit, Commande, LigneCommande, 
    Prestation, CommandeImpression, Realisation
)
from django.utils.html import format_html

# ✅ VÉRIFIEZ BIEN CETTE LIGNE : ajoutez les modèles manquants à la fin
from .models import Prestation, GrilleTarifaireSurface, FormatFlyer, Realisation, OptionQuantite, PalierPrixUnitaire
from .models import Prestation, Realisation  # Cet import donne accès aux modèles de votre application
# =========================================================================
# 1. GESTION DES BOUTIQUES & PRODUITS
# =========================================================================
@admin.register(Vendeur)
class VendeurAdmin(admin.ModelAdmin):
    list_display = ('nom_boutique', 'user', 'devise')
    search_fields = ('nom_boutique', 'user__username')
    list_filter = ('devise',)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ('nom', 'vendeur', 'prix', 'stock', 'date_ajout')
    search_fields = ('nom', 'vendeur__nom_boutique')
    list_filter = ('vendeur', 'date_ajout')
    list_editable = ('stock', 'prix')


# =========================================================================
# 2. GESTION DES COMMANDES STANDARD (E-COMMERCE)
# =========================================================================
class LigneCommandeInline(admin.TabularInline):
    model = LigneCommande
    extra = 0


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_vendeur', 'nom_client', 'telephone', 'statut', 'date_commande')
    search_fields = ('nom_client', 'telephone', 'items__produit__nom', 'items__produit__vendeur__nom_boutique')
    list_filter = ('statut', 'date_commande')
    list_editable = ('statut',)
    inlines = [LigneCommandeInline]

    @admin.display(ordering='items__produit__vendeur', description='Vendeur')
    def get_vendeur(self, obj):
        # Sécurise la récupération si la commande n'a pas encore de lignes
        premiere_ligne = obj.items.first()
        if premiere_ligne and premiere_ligne.produit and premiere_ligne.produit.vendeur:
            return premiere_ligne.produit.vendeur.nom_boutique
        return "Non spécifié"


from django.contrib import admin
from django.utils.html import format_html
from .models import Prestation, GrilleTarifaireSurface, FormatFlyer
from django.contrib import admin
from django.utils.html import format_html
# Importation de tous vos modèles nécessaires
from .models import Prestation, GrilleTarifaireSurface, FormatFlyer, Realisation, OptionQuantite, PalierPrixUnitaire

# =========================================================================
# 1. DÉCLARATION DES INLINES (FORMULAIRES IMBRIQUÉS)
# =========================================================================

# Permet d'ajouter les prix au m² (Bâches, Vinyles) + Image
class GrilleTarifaireSurfaceInline(admin.TabularInline):
    model = GrilleTarifaireSurface
    extra = 1
    fields = ('dimensions', 'surface_m2', 'prix_total', 'image')

# Permet d'ajouter les prix par formats (A5, A6...) + Image
class FormatFlyerInline(admin.TabularInline):
    model = FormatFlyer
    extra = 1
    fields = ('nom_format', 'prix_unitaire', 'image')

# ✅ CONFIGURATION MANQUANTE : Gestion des lots de quantités (100 ex, 200 ex...)
class OptionQuantiteInline(admin.TabularInline):
    model = OptionQuantite
    extra = 3

# ✅ CONFIGURATION MANQUANTE : Tarifs dégressifs pour les produits vendus à l'unité
# ✅ CONFIGURATION MANUELLE DES CHAMPS VISIBLES DANS L'ADMIN
class PalierPrixUnitaireInline(admin.TabularInline):
    model = PalierPrixUnitaire
    extra = 3
    # LIGNE CRITIQUE À RAJOUTER POUR SÉCURISER L'AFFICHAGE DE L'IMAGE
    fields = ['quantite_minimale', 'prix_unitaire', 'image']


# admin.py

class RealisationInline(admin.TabularInline):
    model = Realisation
    extra = 3
    # On ajoute un aperçu de l'image directement dans la ligne pour l'admin
    fields = ('titre', 'commentaire', 'image', 'aperçu_miniature')
    readonly_fields = ('aperçu_miniature',)

    def aperçu_miniature(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: auto; border-radius: 4px;" />', obj.image.url)
        return "Pas d'image"
    aperçu_miniature.short_description = "Aperçu"

# =========================================================================
# 2. CONFIGURATION DE L'ADMINISTRATION PRINCIPALE
# =========================================================================

@admin.register(Prestation)
class PrestationAdmin(admin.ModelAdmin):
    list_display = ('id', 'titre', 'type_unite', 'aperçu_image')
    search_fields = ('titre',)
    list_filter = ('type_unite',)
    list_editable = ('type_unite',)

    # Tous vos formulaires imbriqués apparaissent ensemble sur la même page, dans le bon ordre !
    inlines = [
        GrilleTarifaireSurfaceInline, 
        FormatFlyerInline, 
        OptionQuantiteInline, 
        PalierPrixUnitaireInline, 
        RealisationInline
    ]

    @admin.display(description='Miniature')
    def aperçu_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: auto; border-radius: 4px;" />', obj.image.url)
        return "Pas d'image"


# =========================================================================
# 3. HISTORIQUE DES RÉALISATIONS (PORTFOLIO CLIENTS)
# =========================================================================
@admin.register(Realisation)
class RealisationAdmin(admin.ModelAdmin):
    list_display = ('titre', 'commentaire', 'aperçu_image', 'date_ajout')
    search_fields = ('titre', 'commentaire')

    @admin.display(description='Rendu Réel')
    def aperçu_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 60px; height: auto; border-radius: 4px;" />', obj.image.url)
        return "Pas d'image"


# =========================================================================
# 6. VUE PERSONNALISÉE : DASHBOARD ADMIN YATOUT
# =========================================================================
@staff_member_required
def liste_commandes_admin(request):
    """ Récupère toutes les commandes d'impression pour l'admin YaTout """
    commandes = CommandeImpression.objects.all().order_by('-date_commande')
    return render(request, 'shop/admin_commandes.html', {'commandes': commandes})



@admin.register(CommandeImpression)
class CommandeImpressionAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom_client', 'telephone', 'total_final', 'statut', 'validee_par_client', 'bl_genere', 'date_commande')
    list_filter = ('statut', 'bl_genere', 'validee_par_client')
    search_fields = ('nom_client', 'telephone')
    list_editable = ('statut',)

    actions = ['creer_bon_livraison_depuis_commande']

    @admin.action(description="Transférer les commandes sélectionnées en Bon de Livraison (BL)")
    def creer_bon_livraison_depuis_commande(self, request, queryset):
        lignes_affectees = queryset.update(
            statut='VALIDE',
            validee_par_client=True,
            bl_genere=True
        )
        self.message_user(
            request, 
            f"✨ Succès : {lignes_affectees} commande(s) transférée(s) avec succès en Bon de Livraison (BL)."
        )




admin.site.site_title = "yatout"

# Changez le grand titre sur la page de connexion et le tableau de bord
admin.site.site_header = "Boutique/Print YaTouT"

# Changez le texte d'accueil au milieu de la page
admin.site.index_title = "Bienvenue dans YaTouT"