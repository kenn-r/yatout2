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
    



    def numero_bon_commande(self):
        """Génère le numéro sous la forme BC/26-07-0001 basé sur la date réelle"""
        date_ref = self.date_commande if self.date_commande else datetime.datetime.now()
        annee = date_ref.strftime('%y')
        mois = date_ref.strftime('%m')
        sequence = f"{self.id:04d}" if self.id else "0000"
        return f"BC/{annee}-{mois}-{sequence}"

    def numero_bon_livraison(self):
        """Génère le numéro sous la forme BL/26-07-0001 basé sur la date réelle"""
        date_ref = self.date_commande if self.date_commande else datetime.datetime.now()
        annee = date_ref.strftime('%y')
        mois = date_ref.strftime('%m')
        sequence = f"{self.id:04d}" if self.id else "0000"
        return f"BL/{annee}-{mois}-{sequence}"

    def __str__(self):
        # Utilise par défaut le numéro de commande pour l'affichage de l'administration
        return f"Commande #{self.numero_bon_commande()} - {self.nom_client}"

    


    




from django.db import models
from django.contrib.auth.models import User

class Devis(models.Model):
    STATUT_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('envoye', 'Envoyé au client'),
        ('valide', 'Validé par le client'),
        ('rejete', 'Rejeté'),
        ('converti_bl', 'Converti en BL'),
    ]

    # Informations Client
    nom_client = models.CharField(max_length=150, verbose_name="Nom complet du client")
    telephone = models.CharField(max_length=20, verbose_name="Numéro de téléphone / WhatsApp")
    email = models.EmailField(blank=True, null=True, verbose_name="Email (optionnel)")
    
    # Détails du Devis
    description_prestation = models.TextField(verbose_name="Détails des prestations demandées")
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant Total (FCFA)")
    
    # Suivi & Droits
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='brouillon')
    livre_par = models.CharField(max_length=150, default="Nous-mêmes", verbose_name="Mode de livraison")
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, limit_choices_to={'is_staff': True})
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # Référence vers le Bon de Livraison une fois converti
    numero_bl = models.CharField(max_length=50, blank=True, null=True, verbose_name="Numéro de BL associé")
    numero_devis_personnalise = models.CharField(max_length=20, unique=True, blank=True, null=True)
    # Suivi & Droits
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='brouillon')
    livre_par = models.CharField(max_length=150, default="Nous-mêmes", verbose_name="Mode de livraison")
    

    def __str__(self):
        return f"Devis #{self.id} - {self.nom_client} ({self.get_statut_display()})"

    class Meta:
        verbose_name = "Devis"
        ordering = ['-date_creation']



class DevisAuditLog(models.Model):
    ACTIONS_CHOICES = [
        ('SUPPRESSION', 'Suppression validée'),
        ('TENTATIVE', 'Tentative de suppression'),
    ]
    
    devis_ref = models.CharField("Référence Devis", max_length=20)
    client = models.CharField("Nom du Client", max_length=150)
    montant = models.DecimalField("Montant Total", max_digits=10, decimal_places=2)
    statut_devis = models.CharField("État du devis", max_length=50)
    action = models.CharField(max_length=20, choices=ACTIONS_CHOICES)
    resultat = models.CharField(max_length=255) # Ex: "Échec : Code secret incorrect saisi ('1234')"
    execute_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Opérateur")
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log d'Audit Devis"
        ordering = ['-date_action']

    def __str__(self):
        return f"{self.devis_ref} - {self.action} - {self.resultat}"

class Facture(models.Model):
    MODE_PAIEMENT_CHOICES = [
        ('WAVE', 'Wave 🌊'),
        ('OM', 'Orange Money 🍊'),
        ('MTN', 'MTN MoMo 💛'),
        ('CASH', 'Espèces 💵'),
        ('VIREMENT', 'Virement bancaire 🏦'),
    ]

    STATUT_CHOICES = [
        ('PAYEE', 'Soldée / Payée ✅'),
        ('PARTIEL', 'Partiellement payée ⚠️'),
    ]

    # ✅ Lié directement au Devis (qui fait office de BL via son numéro_bl)
    devis_associe = models.OneToOneField('Devis', on_delete=models.PROTECT, related_name='facture')
    
    # ✅ Chiffres décimaux corrigés (sans max_length)
    montant_total_bl = models.DecimalField(max_digits=12, decimal_places=2) 
    montant_recu = models.DecimalField(max_digits=12, decimal_places=2)     
    reste_a_payer = models.DecimalField(max_digits=12, decimal_places=2)    
    
    # Paramètres de règlement et légal
    numero_facture = models.CharField(max_length=50, unique=True)
    mode_paiement = models.CharField(max_length=20, choices=MODE_PAIEMENT_CHOICES)
    statut_paiement = models.CharField(max_length=20, choices=STATUT_CHOICES, default='PAYEE')
    date_paiement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Facture {self.numero_facture} - Devis/BL #{self.devis_associe.id}"



class Temoignage(models.Model):
    nom_client = models.CharField(max_length=100, verbose_name="Nom ou Entreprise")
    commentaire = models.TextField(verbose_name="Avis client")
    note = models.IntegerField(default=5, verbose_name="Note sur 5")
    date_publication = models.DateTimeField(auto_now_add=True)
    est_approuve = models.BooleanField(default=False, verbose_name="Afficher sur le site")

    def __str__(self):
        return f"Avis de {self.nom_client} - {'Validé' if self.est_approuve else 'En attente'}"


import datetime

from django.db import models


# =========================================================================
# 🖨️ MODULE 1 : FLYERS, DÉPLIANTS & CARTES DE VISITE
# =========================================================================
class SupportFlyer(models.Model):
    titre = models.CharField(
        max_length=200,
        verbose_name="Nom du support (Ex: Flyers Standard, Cartes de Visite)"
    )
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='prestations/flyers/',
        blank=True,
        null=True
    )
    remise_globale = models.IntegerField(
        default=0,
        verbose_name="Remise sur cet article (%)"
    )

    class Meta:
        db_table = 'print_flyer'

    def __str__(self):
        return self.titre

    def calculer_prix(self, format_papier, quantite):
        """Recherche le prix exact du lot selon le format et le volume."""
        try:
            tarif = self.tarifs_specifiques.get(
                format_papier=format_papier,
                quantite=quantite
            )

            prix_brut = float(tarif.prix_total_lot)
            remise = self.remise_globale
            montant_remise = int(prix_brut * (remise / 100.0))

            return {
                "prix_brut": prix_brut,
                "remise_pourcent": remise,
                "montant_remise": montant_remise,
                "prix_final": prix_brut - montant_remise
            }

        except Exception:
            return {
                "prix_brut": 0,
                "remise_pourcent": 0,
                "montant_remise": 0,
                "prix_final": 0,
                "erreur": "Tarif non configuré pour cette quantité/format."
            }

    def type_unite(self):
        return 'FLYER'


class TarifOptionFlyer(models.Model):
    flyer = models.ForeignKey(
        SupportFlyer,
        on_delete=models.CASCADE,
        related_name='tarifs_specifiques'
    )
    format_papier = models.CharField(
        max_length=50,
        help_text="Ex: A5, A6, 8.5x5.4cm"
    )
    quantite = models.IntegerField(
        help_text="Ex: 100, 500, 1000"
    )
    prix_total_lot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Prix brut global du lot"
    )


# =========================================================================
# 🖼️ MODULE 2 : BÂCHES, VINYLES & GRAND FORMAT
# =========================================================================
class SupportGrandFormat(models.Model):
    titre = models.CharField(
        max_length=200,
        verbose_name="Nom du produit (Ex: Bâche Publicitaire, Vinyle)"
    )
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='prestations/grand_format/',
        blank=True,
        null=True
    )
    prix_au_metre_carre = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Prix de base au M²"
    )
    remise_globale = models.IntegerField(
        default=0,
        verbose_name="Remise sur cet article (%)"
    )

    class Meta:
        db_table = 'print_grand_format'

    def __str__(self):
        return self.titre

    def calculer_prix(self, largeur_metres, longueur_metres):
        """Calcul direct du prix au M²."""
        surface_m2 = float(largeur_metres) * float(longueur_metres)
        prix_brut = surface_m2 * float(self.prix_au_metre_carre)

        montant_remise = int(
            prix_brut * (self.remise_globale / 100.0)
        )

        return {
            "prix_brut": prix_brut,
            "remise_pourcent": self.remise_globale,
            "montant_remise": montant_remise,
            "prix_final": prix_brut - montant_remise
        }

    def type_unite(self):
        return 'SURFACE'


# =========================================================================
# ☕ MODULE 3 : GOODIES & OBJETS PUBLICITAIRES
# =========================================================================
class SupportObjetPublicitaire(models.Model):
    titre = models.CharField(
        max_length=200,
        verbose_name="Nom de l'objet (Ex: Mug en Céramique, T-shirt)"
    )
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='prestations/goodies/',
        blank=True,
        null=True
    )
    remise_globale = models.IntegerField(
        default=0,
        verbose_name="Remise sur cet article (%)"
    )

    class Meta:
        db_table = 'print_objet'

    def __str__(self):
        return self.titre

    def calculer_prix(self, quantite):
        """Logique dégressive par paliers."""
        palier = (
            self.paliers_prix
            .filter(quantite_minimale__lte=quantite)
            .order_by('-quantite_minimale')
            .first()
        )

        if palier:
            prix_brut = float(palier.prix_unitaire) * quantite
        else:
            prix_brut = 0

        montant_remise = int(
            prix_brut * (self.remise_globale / 100.0)
        )

        return {
            "prix_brut": prix_brut,
            "remise_pourcent": self.remise_globale,
            "montant_remise": montant_remise,
            "prix_final": prix_brut - montant_remise
        }


class PalierPrixObjet(models.Model):
    objet = models.ForeignKey(
        SupportObjetPublicitaire,
        on_delete=models.CASCADE,
        related_name='paliers_prix'
    )
    quantite_minimale = models.IntegerField(
        help_text="Ex: 1, 10, 50, 100"
    )
    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix pour une seule pièce à ce palier"
    )


# =========================================================================
# 📚 MODULE 4 : SERVICES DE FAÇONNAGE
# =========================================================================
class ServiceFaconnage(models.Model):
    titre = models.CharField(
        max_length=200,
        verbose_name="Nom du service (Ex: Reliure Document, Photocopie A4)"
    )
    description = models.TextField(blank=True)
    prix_fixe_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Prix fixe à la page ou à l'acte"
    )
    remise_globale = models.IntegerField(
        default=0,
        verbose_name="Remise sur cet article (%)"
    )

    class Meta:
        db_table = 'print_faconnage'

    def __str__(self):
        return self.titre

    def calculer_prix(self, quantite):
        prix_brut = quantite * float(self.prix_fixe_unitaire)

        montant_remise = int(
            prix_brut * (self.remise_globale / 100.0)
        )

        return {
            "prix_brut": prix_brut,
            "remise_pourcent": self.remise_globale,
            "montant_remise": montant_remise,
            "prix_final": prix_brut - montant_remise
        }


# =========================================================================
# 🧾 MODULE 5 : COMMANDES IMPRESSION
# =========================================================================
class CommandeImpression(models.Model):

    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Bon validé / En cours'),
        ('TERMINE', 'Terminé'),
    ]

    nom_client = models.CharField(max_length=100)
    email_client = models.EmailField()
    telephone = models.CharField(max_length=20)

    details_json = models.TextField(
        verbose_name="Détails de la commande (JSON)"
    )

    total_brut = models.IntegerField(default=0)
    montant_remise = models.IntegerField(default=0)
    total_final = models.IntegerField(default=0)

    date_commande = models.DateTimeField(auto_now_add=True)

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='EN_ATTENTE'
    )

    validee_par_client = models.BooleanField(
        default=False,
        verbose_name="Validé par le client"
    )

    bl_genere = models.BooleanField(
        default=False,
        verbose_name="Transféré en Bon de Livraison"
    )

    livre_par = models.CharField(
        max_length=100,
        default="Nous-mêmes",
        verbose_name="Livré par"
    )

    # =====================================================================
    # 🎟️ TOMBOLA
    # =====================================================================
    numero_tombola = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Numéro de tombola"
    )

    def save(self, *args, **kwargs):
        """
        Attribution automatique du numéro de tombola.

        Le numéro est attribué uniquement lorsque la commande
        passe au statut VALIDE.

        Exemple :
        YT-IMP-0025
        """

        # Première sauvegarde de la commande
        super().save(*args, **kwargs)

        # Si la commande est validée et n'a pas encore de numéro
        if self.statut == 'VALIDE' and not self.numero_tombola:

            self.numero_tombola = f"YT-IMP-{self.id:04d}"

            # Mise à jour uniquement du numéro de tombola
            super().save(
                update_fields=['numero_tombola']
            )

    def numero_bon_commande(self):
        """
        Génère le numéro sous la forme :
        BC/26-09-0001
        """

        date_ref = (
            self.date_commande
            if self.date_commande
            else datetime.datetime.now()
        )

        annee = date_ref.strftime('%y')
        mois = date_ref.strftime('%m')

        sequence = (
            f"{self.id:04d}"
            if self.id
            else "0000"
        )

        return f"BC/{annee}-{mois}-{sequence}"

    def numero_bon_livraison(self):
        """
        Génère le numéro sous la forme :
        BL/26-09-0001
        """

        date_ref = (
            self.date_commande
            if self.date_commande
            else datetime.datetime.now()
        )

        annee = date_ref.strftime('%y')
        mois = date_ref.strftime('%m')

        sequence = (
            f"{self.id:04d}"
            if self.id
            else "0000"
        )

        return f"BL/{annee}-{mois}-{sequence}"

    def __str__(self):
        return (
            f"Commande #{self.numero_bon_commande()} "
            f"- {self.nom_client}"
        )


# =========================================================================
# 🎰 MODULE 6 : TIRAGE MENSUEL DE LA TOMBOLA
# =========================================================================
class TirageTombola(models.Model):

    # Exemple : 2026-09-01 représente septembre 2026
    mois = models.DateField(
        unique=True,
        verbose_name="Mois du tirage"
    )

    commande_gagnante = models.ForeignKey(
        CommandeImpression,
        on_delete=models.PROTECT,
        related_name='tirages_gagnes',
        verbose_name="Commande gagnante"
    )

    date_tirage = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date du tirage"
    )

    def __str__(self):
        return (
            f"Tombola {self.mois.strftime('%m/%Y')} - "
            f"{self.commande_gagnante.numero_tombola}"
        )


# =========================================================================
# 🖼️ MODULE 7 : RÉALISATIONS
# =========================================================================
class Realisation(models.Model):
    titre = models.CharField(
        max_length=200,
        verbose_name="Nom de la réalisation"
    )

    commentaire = models.CharField(
        max_length=255,
        verbose_name="Texte accrocheur"
    )

    image = models.ImageField(
        upload_to='realisations/',
        verbose_name="Photo du rendu réel"
    )

    date_ajout = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.titre