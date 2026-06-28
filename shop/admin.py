from django.contrib import admin
from django.shortcuts import render
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from .models import (
    Vendeur, Produit, Commande, LigneCommande, 
    Prestation, CommandeImpression, Realisation
)

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


# =========================================================================
# 3. GESTION DES SUPPORTS D'IMPRESSION (PRESTATIONS)
# =========================================================================
@admin.register(Prestation)
class PrestationAdmin(admin.ModelAdmin):
    # Ajout de l'aperçu de l'image directement dans la liste
    list_display = ('id', 'titre', 'type_unite', 'prix_unitaire', 'aperçu_image')
    search_fields = ('titre',)
    list_filter = ('type_unite',)
    list_editable = ('prix_unitaire',)

    @admin.display(description='Miniature')
    def aperçu_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: auto; border-radius: 4px;" />', obj.image.url)
        return "Pas d'image"




# =========================================================================
# 5. HISTORIQUE DES RÉALISATIONS (PORTFOLIO CLIENTS)
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