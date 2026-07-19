from django.contrib import admin
from django.shortcuts import render
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin
from django.contrib import admin
from django.shortcuts import render
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from .models import (
    # --- BOUTIQUE E-COMMERCE ---
    Vendeur,
    Produit,
    LigneCommande,
    Commande,
    
    # --- IMPRIMERIE / PRESTATIONS ---
    Prestation, 
    GrilleTarifaireSurface, 
    FormatFlyer, 
    OptionQuantiteFlyer, 
    PalierPrixUnitaire, 
    GrilleCataloguePages, 
    Realisation,
    CommandeImpression  # 🟢 AJOUTÉ ICI POUR CORRIGER LE CRASH
)
from django.utils.html import format_html

# ✅ VÉRIFIEZ BIEN CETTE LIGNE : ajoutez les modèles manquants à la fin

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



# 1. Gestion des réalisations (Conservé et sécurisé)
class RealisationInline(admin.TabularInline):
    model = Realisation
    extra = 3
    fields = ('titre', 'commentaire', 'image', 'aperçu_miniature')
    readonly_fields = ('aperçu_miniature',)

    def aperçu_miniature(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: auto; border-radius: 4px;" />', obj.image.url)
        return "Pas d'image"
    aperçu_miniature.short_description = "Aperçu"


# 2. SURFACE : Prix au m² (Bâches, Vinyles) + Remise Catalogue
class GrilleTarifaireSurfaceInline(admin.TabularInline):
    model = GrilleTarifaireSurface
    extra = 1
    fields = ('dimensions', 'surface_m2', 'prix_total', 'remise_pourcentage', 'image')


# 3. UNITÉ : Tarifs dégressifs à l'unité
class PalierPrixUnitaireInline(admin.TabularInline):
    model = PalierPrixUnitaire
    extra = 3
    fields = ('quantite_minimale', 'prix_unitaire', 'image')


# 4. PAGES : Documents multipages (Brochures, Catalogues)
class GrilleCataloguePagesInline(admin.TabularInline):
    model = GrilleCataloguePages
    extra = 3
    fields = ('nombre_pages', 'quantite', 'prix_total')


# 5. FLYERS : Gestion imbriquée (Les lots de quantité vont ICI désormais)
class OptionQuantiteFlyerInline(admin.TabularInline):
    model = OptionQuantiteFlyer
    extra = 3
    fields = ('quantite', 'prix_total', 'remise_pourcentage')

@admin.register(FormatFlyer)
class FormatFlyerAdmin(admin.ModelAdmin):
    """
    🔥 SUPER ASTUCE SÉCURITÉ : Comme OptionQuantiteFlyer est lié à FormatFlyer,
    on gère les lots de quantité directement depuis la fiche de chaque format !
    """
    list_display = ('prestation', 'nom_format')
    list_filter = ('prestation',)
    fields = ('prestation', 'nom_format', 'image')
    inlines = [OptionQuantiteFlyerInline]


# =========================================================================
# 6. ADMINISTRATION PRINCIPALE : PRESTATION (VERSION FUSIONNÉE & PROPRE)
# =========================================================================

@admin.register(Prestation)
class PrestationAdmin(admin.ModelAdmin):
    # 🟢 Fusion : On affiche l'ID, le titre, le type, la remise et la miniature !
    list_display = ('id', 'titre', 'type_unite', 'remise_custom', 'aperçu_image')
    
    # 🟢 Modification rapide depuis la liste pour la remise et le type de calcul
    list_editable = ('remise_custom', 'type_unite')
    
    list_filter = ('type_unite',)
    search_fields = ('titre',)
    
    # Organisation visuelle propre du formulaire de modification
    fieldsets = (
        (None, {
            'fields': ('titre', 'description', 'image', 'type_unite')
        }),
        ('Configuration Commerciale', {
            'fields': ('remise_custom',),
            'description': 'Cette remise pilote le pourcentage appliqué sur les calculs sur-mesure ou libres.'
        }),
    )
    
    # Tous vos formulaires imbriqués apparaissent ensemble sur la même page, dans le bon ordre
    inlines = [
        RealisationInline,
        GrilleTarifaireSurfaceInline,
        PalierPrixUnitaireInline,
        GrilleCataloguePagesInline
    ]

    # 🟢 Conservé : La méthode pour afficher la miniature dans le tableau de liste
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