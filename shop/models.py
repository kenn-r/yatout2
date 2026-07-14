from django.db import models
from django.contrib.auth.models import User
import datetime


class Vendeur(models.Model):
    CHOIX_DEVISES = [
        ('EUR', 'Euro (€)'),
        ('USD', 'Dollar US ($)'),
        ('MAD', 'Dirham Marocain (DH)'),
        ('XOF', 'F cfa '),
        ('CAD', 'Dollar Canadien ($CA)'),
    ]
    
    # Relation unique avec l'utilisateur Django
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom_boutique = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    devise = models.CharField(max_length=3, choices=CHOIX_DEVISES, default='EUR')
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom_boutique

    # 💡 RACCOURCI : Permet d'appeler directement 'vendeur.email' dans votre code
    @property
    def email(self):
        return self.user.email




class Produit(models.Model):
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE, related_name='produits')
    nom = models.CharField(max_length=255)
    description = models.TextField()
    
    # Le prix actuel (le vrai prix que le client paie)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    
    # 🛠️ NOUVEAU CHAMP : L'ancien prix qui sera affiché en barré
    # blank=True et null=True signifient qu'il n'est pas obligatoire
    ancien_prix = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    image = models.ImageField(upload_to='produits/', blank=True, null=True)
    stock = models.PositiveIntegerField(default=10)
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom

    # 💡 BONUS AUTO : Calcule automatiquement le pourcentage de réduction (-X%)
    @property
    def reduction_pourcentage(self):
        if self.ancien_prix and self.ancien_prix > self.prix:
            rabais = ((self.ancien_prix - self.prix) / self.ancien_prix) * 100
            return int(round(rabais))
        return 0
    

class Commande(models.Model):
    STATUT_CHOICES = [
        ('RECU', 'Commande reçue'),
        ('PREP', 'En cours de préparation'),
        ('EXPE', 'Expédiée'),
        ('LIVR', 'Livrée'),
    ]

    nom_client = models.CharField(max_length=255)
    email_client = models.EmailField()
    telephone = models.CharField(max_length=20, default="")
    adresse = models.TextField()
    date_commande = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=4, choices=STATUT_CHOICES, default='RECU')

    def __str__(self):
        return f"Commande #{self.id} par {self.nom_client}"

    def get_total_cost(self):
        """Calcule le prix total de tous les articles de cette commande."""
        return sum(item.get_cost() for item in self.items.all())


class LigneCommande(models.Model):
    """Table intermédiaire reliant chaque produit à une commande globale."""
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name='items')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    prix = models.DecimalField(max_digits=10, decimal_places=2)  # Sauvegarde le prix au moment de l'achat
    quantite = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantite}x {self.produit.nom} (Commande #{self.commande.id})"

    def get_cost(self):
        """Calcule le coût total de cette ligne."""
        return self.prix * self.quantite
    



class MessageAssistant(models.Model):
    # Null=True permet aux clients non connectés (visiteurs) de discuter aussi
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=255, null=True, blank=True)
    message = models.TextField()
    est_assistant = models.BooleanField(default=False) # True = Bot, False = Client
    date_envoi = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        expediteur = "Assistant" if self.est_assistant else "Client"
        return f"{expediteur} : {self.message[:30]}"
    

import datetime
from django.db import models

class Prestation(models.Model):
    CHOIX_UNITE = [
        ('SURFACE', 'Au mètre carré (Bâche, Vinyle, Affiche)'),
        ('FLYER', 'Lots & Paliers par Format (Flyer, Dépliant, Carte)'),
        ('UNITE', 'À l\'unité simple (Roll-up, Goodies, Reliure)'),
        ('PAGES', 'Au document multipage (Brochure, Catalogue)'),
    ]

    titre = models.CharField(max_length=200, verbose_name="Nom de la prestation")
    description = models.TextField(blank=True, verbose_name="Description")
    type_unite = models.CharField(max_length=10, choices=CHOIX_UNITE, default='UNITE', verbose_name="Type de calcul")
    image = models.ImageField(upload_to='prestations/', blank=True, null=True, verbose_name="Image du produit")

    class Meta:
        db_table = 'shop_prestation'

    def __str__(self):
        return self.titre

# 1. POUR LES PRODUITS 'SURFACE' (Bâche, Vinyle, Affiche)
class GrilleTarifaireSurface(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='grilles_surface')
    dimensions = models.CharField(max_length=50, help_text="Ex: 1x1m, 2x3m, A0")
    surface_m2 = models.FloatField(verbose_name="Surface en m²")
    prix_total = models.IntegerField(verbose_name="Prix total pour cette dimension (FCFA)")
    # NOUVEAU : Image spécifique à cette dimension
    image = models.ImageField(upload_to='surfaces/', blank=True, null=True, verbose_name="Image de démonstration")

    def __str__(self):
        return f"{self.prestation.titre} - {self.dimensions} ({self.prix_total} FCFA)"


# 2. POUR LES FLYERS / DÉPLIANTS
class FormatFlyer(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='formats_flyer')
    nom_format = models.CharField(max_length=50, help_text="Ex: Format A5, Format A6, Standard (Carte)")
    prix_unitaire = models.IntegerField(verbose_name="Prix unitaire de base (FCFA)")
    # NOUVEAU : Image spécifique à ce format
    image = models.ImageField(upload_to='flyers/', blank=True, null=True, verbose_name="Image du format")

    def __str__(self):
        return f"{self.prestation.titre} - {self.nom_format} ({self.prix_unitaire} FCFA/unité)"
    

# 3. NOUVEAU - POUR LES QUANTITÉS ET LOTS (100 ex, 200 ex...)
class OptionQuantite(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='options_quantite')
    quantite = models.IntegerField(verbose_name="Quantité (exemples)", help_text="Ex: 100, 200, 500")
    remise_pourcentage = models.IntegerField(default=0, verbose_name="Remise en %")

    def __str__(self):
        return f"{self.prestation.titre} - Lot {self.quantite} ex. (-{self.remise_pourcentage}%)"


# 4. POUR LES PRODUITS À L'UNITÉ (T-shirts, Objets) AVEC TARIFS DÉGRESSIFS
class PalierPrixUnitaire(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='paliers_unite')
    quantite_minimale = models.IntegerField(verbose_name="Quantité minimale", help_text="Ex: 1, 10, 50, 100")
    prix_unitaire = models.IntegerField(verbose_name="Prix unitaire pour ce palier (FCFA)")
    image = models.ImageField(upload_to='paliers/', blank=True, null=True, verbose_name="Image du palier")

    class Meta:
        ordering = ['quantite_minimale']  # Trie automatiquement du plus petit au plus grand lot

    def __str__(self):
        return f"{self.prestation.titre} - Dès {self.quantite_minimale} ex. ({self.prix_unitaire} FCFA/u)"
    

    
# 3. STRUCTURE DE COMMANDE UNIVERSELLE
class CommandeImpression(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Bon validé / En cours'),
        ('TERMINE', 'Terminé'),
    ]
    
    nom_client = models.CharField(max_length=100)
    email_client = models.EmailField()
    telephone = models.CharField(max_length=20)
    
    details_json = models.TextField(verbose_name="Détails de la commande (JSON)")
    
    total_brut = models.IntegerField(default=0)
    montant_remise = models.IntegerField(default=0)
    total_final = models.IntegerField(default=0)
    
    date_commande = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    
    validee_par_client = models.BooleanField(default=False, verbose_name="Validé par le client")
    bl_genere = models.BooleanField(default=False, verbose_name="Transféré en Bon de Livraison")

    def numero_bon(self):
        annee = self.date_commande.year if self.date_commande else datetime.datetime.now().year
        return f"BON-{annee}-{self.id:03d}" if self.id else f"BON-{annee}-000"

    def __str__(self):
        return f"Commande #{self.numero_bon()} - {self.nom_client}"




class Realisation(models.Model):
    # LIGNE À RAJOUTER ABSOLUMENT : Lie la réalisation à un produit spécifique
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='realisations', null=True, blank=True)
    
    titre = models.CharField(max_length=200, verbose_name="Nom de la réalisation (ex: Bâche Pro)")
    commentaire = models.CharField(max_length=255, verbose_name="Texte accrocheur (ex: Qualité Premium YaTout)")
    image = models.ImageField(upload_to='realisations/', verbose_name="Photo du rendu réel")
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre
    


