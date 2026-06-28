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
    


class Prestation(models.Model):
    CHOIX_UNITE = [
        ('M2', 'Au mètre carré (m²)'),
        ('UNITE', 'À l\'unité (Quantité × Prix)'), # <--- Plus simple pour Flutter et le Web
        ('LOT_100', 'Par lot de 100 flyers'),
        ('LETTRE', 'À la lettre / Autocollant'),
    ]

    titre = models.CharField(max_length=200, verbose_name="Nom de la prestation")
    description = models.TextField(blank=True, verbose_name="Description")
    type_unite = models.CharField(max_length=10, choices=CHOIX_UNITE, default='M2', verbose_name="Type de calcul")
    prix_unitaire = models.IntegerField(verbose_name="Prix unitaire (FCFA)")
    image = models.ImageField(upload_to='prestations/', blank=True, null=True, verbose_name="Image du produit")

    class Meta:
        db_table = 'shop_prestation'

    def __str__(self):
        return self.titre
    
    

class CommandeImpression(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Bon validé / En cours'),
        ('TERMINE', 'Terminé'),
    ]
    
    nom_client = models.CharField(max_length=100)
    email_client = models.EmailField()
    telephone = models.CharField(max_length=20)
    
    # Contient le récapitulatif JSON complet de la commande pour l'historique
    details_json = models.TextField(verbose_name="Détails de la commande (JSON)")
    
    total_brut = models.IntegerField(default=0)
    montant_remise = models.IntegerField(default=0)
    total_final = models.IntegerField(default=0)
    
    date_commande = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    remise_active = models.BooleanField(default=True, verbose_name="Remise de 5% appliquée")

    # 🛠️ NOUVEAUX CHAMPS POUR VOTRE LOGIQUE DE VALIDATION ET TRANSFERT EN BL
    validee_par_client = models.BooleanField(default=False, verbose_name="Validé par le client")
    bl_genere = models.BooleanField(default=False, verbose_name="Transféré en Bon de Livraison")

    def numero_bon(self):
        # Utilisation sécurisée de l'année pour éviter les bugs avant la première sauvegarde
        annee = self.date_commande.year if self.date_commande else datetime.datetime.now().year
        return f"BON-{annee}-{self.id:03d}" if self.id else f"BON-{annee}-000"

    def __str__(self):
        return f"Commande #{self.numero_bon()} - {self.nom_client}"
    


class Realisation(models.Model):
    titre = models.CharField(max_length=200, verbose_name="Nom de la réalisation (ex: Bâche Pro)")
    commentaire = models.CharField(max_length=255, verbose_name="Texte accrocheur (ex: Qualité Premium YaTout)")
    image = models.ImageField(upload_to='realisations/', verbose_name="Photo du rendu réel")
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre