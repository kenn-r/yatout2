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
    
from django.db import models

# =========================================================================
# 🖨️ MODULE 1 : FLYERS, DÉPLIANTS & CARTES DE VISITE
# =========================================================================
class SupportFlyer(models.Model):
    titre = models.CharField(max_length=200, verbose_name="Nom du support (Ex: Flyers Standard, Cartes de Visite)")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='prestations/flyers/', blank=True, null=True)
    remise_globale = models.IntegerField(default=0, verbose_name="Remise sur cet article (%)")

    class Meta:
        db_table = 'print_flyer'

    def __str__(self):
        return self.titre

    def calculer_prix(self, format_papier, quantite):
        """Recherche le prix exact du lot selon le format et le volume."""
        try:
            tarif = self.tarifs_specifiques.get(format_papier=format_papier, quantite=quantite)
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
            return {"prix_brut": 0, "remise_pourcent": 0, "montant_remise": 0, "prix_final": 0, "erreur": "Tarif non configuré pour cette quantité/format."}
    def type_unite(self):
        return 'FLYER'
    
class TarifOptionFlyer(models.Model):
    flyer = models.ForeignKey(SupportFlyer, on_delete=models.CASCADE, related_name='tarifs_specifiques')
    format_papier = models.CharField(max_length=50, help_text="Ex: A5, A6, 8.5x5.4cm")
    quantite = models.IntegerField(help_text="Ex: 100, 500, 1000")
    prix_total_lot = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Prix brut global du lot")


# =========================================================================
# 🖼️ MODULE 2 : BÂCHES, VINYLES & GRAND FORMAT
# =========================================================================
class SupportGrandFormat(models.Model):
    titre = models.CharField(max_length=200, verbose_name="Nom du produit (Ex: Bâche Publicitaire, Vinyle)")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='prestations/grand_format/', blank=True, null=True)
    prix_au_metre_carre = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix de base au M²")
    remise_globale = models.IntegerField(default=0, verbose_name="Remise sur cet article (%)")

    class Meta:
        db_table = 'print_grand_format'

    def __str__(self):
        return self.titre

    def calculer_prix(self, largeur_metres, longueur_metres):
        """Calcul direct et mathématique au M² basé sur les dimensions saisies par le client."""
        surface_m2 = float(largeur_metres) * float(longueur_metres)
        prix_brut = surface_m2 * float(self.prix_au_metre_carre)
        montant_remise = int(prix_brut * (self.remise_globale / 100.0))
        return {
            "prix_brut": prix_brut,
            "remise_pourcent": self.remise_globale,
            "montant_remise": montant_remise,
            "prix_final": prix_brut - montant_remise
        }

    def type_unite(self):
            return 'SURFACE'


# =========================================================================
# ☕ MODULE 3 : GOODIES & OBJETS (MUGS, TASSES, T-SHIRTS, CHAPEAUX, KÉPIS)
# =========================================================================
class SupportObjetPublicitaire(models.Model):
    titre = models.CharField(max_length=200, verbose_name="Nom de l'objet (Ex: Mug en Céramique, T-shirt)")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='prestations/goodies/', blank=True, null=True)
    remise_globale = models.IntegerField(default=0, verbose_name="Remise sur cet article (%)")

    class Meta:
        db_table = 'print_objet'

    def __str__(self):
        return self.titre

    def calculer_prix(self, quantite):
        """Logique dégressive par paliers : plus on commande d'objets, moins l'unité est chère."""
        palier = self.paliers_prix.filter(quantite_minimale__lte=quantite).order_by('-quantite_minimale').first()
        if palier:
            prix_brut = float(palier.prix_unitaire) * quantite
        else:
            prix_brut = 0
            
        montant_remise = int(prix_brut * (self.remise_globale / 100.0))
        return {
            "prix_brut": prix_brut,
            "remise_pourcent": self.remise_globale,
            "montant_remise": montant_remise,
            "prix_final": prix_brut - montant_remise
        }

class PalierPrixObjet(models.Model):
    objet = models.ForeignKey(SupportObjetPublicitaire, on_delete=models.CASCADE, related_name='paliers_prix')
    quantite_minimale = models.IntegerField(help_text="Ex: 1, 10, 50, 100 (S'applique à partir de ce volume)")
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2, help_text="Prix pour une seule pièce à ce palier")


# =========================================================================
# 📚 MODULE 4 : SERVICES DE FACONNAGE (PHOTOCOPIES, RELIURES)
# =========================================================================
class ServiceFaconnage(models.Model):
    titre = models.CharField(max_length=200, verbose_name="Nom du service (Ex: Reliure Document, Photocopie A4)")
    description = models.TextField(blank=True)
    prix_fixe_unitaire = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix fixe à la page ou à l'acte")
    remise_globale = models.IntegerField(default=0, verbose_name="Remise sur cet article (%)")

    class Meta:
        db_table = 'print_faconnage'

    def __str__(self):
        return self.titre

    def calculer_prix(self, quantite):
        """Multiplication simple du prix unitaire par la quantité demandée."""
        prix_brut = quantite * float(self.prix_fixe_unitaire)
        montant_remise = int(prix_brut * (self.remise_globale / 100.0))
        return {
            "prix_brut": prix_brut,
            "remise_pourcent": self.remise_globale,
            "montant_remise": montant_remise,
            "prix_final": prix_brut - montant_remise
        }


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
    remise_custom = models.IntegerField(default=0, verbose_name="Remise sur-mesure (%)")

    class Meta:
        db_table = 'shop_prestation'

    def __str__(self):
        return self.titre

    # 🟢 AJOUTEZ CETTE MÉTHODE ICI, BIEN ALIGNÉE :
    def calculer_prix(self, quantite=1, format_id=None, surface_id=None, nb_pages=None):
        """
        Calcule le prix brut, la remise et le prix final selon le type de prestation.
        """
        prix_brut = 0
        remise_pourcentage = 0

        try:
            # 1. LOGIQUE SURFACE
            if self.type_unite == 'SURFACE' or self.type_unite == 'M2':
                if surface_id and surface_id != 'custom':
                    grille = self.grilles_surface.get(id=surface_id)
                    prix_brut = grille.prix_total * quantite
                    remise_pourcentage = grille.remise_pourcentage
                else:
                    # Fallback au cas où
                    prix_brut = 0

            # 2. LOGIQUE FLYER
            elif self.type_unite == 'FLYER':
                from .models import OptionQuantiteFlyer
                option = OptionQuantiteFlyer.objects.get(
                    format_flyer_id=format_id, 
                    quantite=quantite
                )
                prix_brut = option.prix_total
                remise_pourcentage = option.remise_pourcentage

            # 3. LOGIQUE UNITÉ SIMPLE (Dégressif par palier)
            elif self.type_unite == 'UNITE':
                palier = self.paliers_unite.filter(quantite_minimale__lte=quantite).order_by('-quantite_minimale').first()
                if palier:
                    prix_brut = palier.prix_unitaire * quantite
                else:
                    prix_brut = 0 
                remise_pourcentage = self.remise_custom

            # 4. LOGIQUE MULTIPAGE (Catalogue)
            elif self.type_unite == 'PAGES':
                grille_page = self.paliers_pages.get(nombre_pages=nb_pages, quantite=quantite)
                prix_brut = grille_page.prix_total
                remise_pourcentage = self.remise_custom

        except Exception:
            # 🎯 CORRECTION : Utilise le prix de base par défaut du modèle au lieu de 0
            prix_base = getattr(self, 'prix_unitaire', 0)
            brut_secours = prix_base * quantite
            return {
                "prix_brut": brut_secours,
                "remise_appliquee_pourcent": 0,
                "montant_remise": 0,
                "prix_final": brut_secours,
                "erreur": "Tarif spécifique non trouvé, application du tarif de base."
            }

        montant_remise = int(prix_brut * (remise_pourcentage / 100.0))
        prix_final = prix_brut - montant_remise

        return {
            "prix_brut": prix_brut,
            "remise_appliquee_pourcent": remise_pourcentage,
            "montant_remise": montant_remise,
            "prix_final": prix_final
        }

    

# 1. SURFACE (Invariable)
class GrilleTarifaireSurface(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='grilles_surface')
    dimensions = models.CharField(max_length=50, help_text="Ex: 1x1m, 2x3m, A0")
    surface_m2 = models.FloatField(verbose_name="Surface en m²")
    prix_total = models.IntegerField(verbose_name="Prix total (FCFA)")
    remise_pourcentage = models.IntegerField(default=0, verbose_name="Remise catalogue (%)")
    image = models.ImageField(upload_to='surfaces/', blank=True, null=True)

    def __str__(self):
        return f"{self.prestation.titre} - {self.dimensions} ({self.prix_total} FCFA)"


# 2. FLYERS & DÉPLIANTS (Correction : Liaison Quantité -> Format)
class FormatFlyer(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='formats_flyer')
    nom_format = models.CharField(max_length=50, help_text="Ex: Format A5, Format A6")
    image = models.ImageField(upload_to='flyers/', blank=True, null=True)

    def __str__(self):
        return f"{self.prestation.titre} - {self.nom_format}"

class OptionQuantiteFlyer(models.Model):
    # Lié au format directement pour des tarifs précis par taille
    format_flyer = models.ForeignKey(FormatFlyer, on_delete=models.CASCADE, related_name='options_quantite')
    quantite = models.IntegerField(verbose_name="Quantité (ex: 100, 500)")
    prix_total = models.IntegerField(verbose_name="Prix total pour ce lot (FCFA)", help_text="Plus simple pour intégrer directement la dégressivité sans calcul complexe")
    remise_pourcentage = models.IntegerField(default=0, verbose_name="Remise en %")

    def __str__(self):
        return f"{self.format_flyer} - Lot {self.quantite} ex. ({self.prix_total} FCFA)"


# 3. À L'UNITÉ (Dégressif global)
class PalierPrixUnitaire(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='paliers_unite')
    quantite_minimale = models.IntegerField(verbose_name="Quantité minimale")
    prix_unitaire = models.IntegerField(verbose_name="Prix unitaire (FCFA)")
    image = models.ImageField(upload_to='paliers/', blank=True, null=True, verbose_name="Image du palier")

    class Meta:
        ordering = ['quantite_minimale']

    def __str__(self):
        return f"{self.prestation.titre} - Dès {self.quantite_minimale} ex. ({self.prix_unitaire} FCFA/u)"


# 4. NOUVEAU : MULTIPAGE (Brochure, Catalogue)
class GrilleCataloguePages(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='paliers_pages')
    nombre_pages = models.IntegerField(verbose_name="Nombre de pages (Ex: 8, 12, 16)")
    quantite = models.IntegerField(verbose_name="Quantité d'exemplaires")
    prix_total = models.IntegerField(verbose_name="Prix total (FCFA)")

    class Meta:
        ordering = ['nombre_pages', 'quantite']

    def __str__(self):
        return f"{self.prestation.titre} - {self.nombre_pages} p. - X{self.quantite} ({self.prix_total} FCFA)"


# 4. NOUVEAU : MULTIPAGE (Brochure, Catalogue)
class GrilleCataloguePages(models.Model):
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='paliers_pages')
    nombre_pages = models.IntegerField(verbose_name="Nombre de pages (Ex: 8, 12, 16)")
    quantite = models.IntegerField(verbose_name="Quantité d'exemplaires")
    prix_total = models.IntegerField(verbose_name="Prix total (FCFA)")

    class Meta:
        ordering = ['nombre_pages', 'quantite']

    def __str__(self):
        return f"{self.prestation.titre} - {self.nombre_pages} p. - X{self.quantite} ({self.prix_total} FCFA)"

import datetime
from django.db import models

import datetime  # 🟢 FIX : Importation requise pour la génération des numéros BC et BL
from django.db import models

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
    
    # 🟢 AJOUT : Nouveau champ pour éditer dynamiquement le transporteur/livreur depuis l'admin
    livre_par = models.CharField(
        max_length=100, 
        default="Nous-mêmes", 
        verbose_name="Livré par"
    )

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


class Realisation(models.Model):
    # LIGNE À RAJOUTER ABSOLUMENT : Lie la réalisation à un produit spécifique
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name='realisations', null=True, blank=True)
    
    titre = models.CharField(max_length=200, verbose_name="Nom de la réalisation (ex: Bâche Pro)")
    commentaire = models.CharField(max_length=255, verbose_name="Texte accrocheur (ex: Qualité Premium YaTout)")
    image = models.ImageField(upload_to='realisations/', verbose_name="Photo du rendu réel")
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre
    


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