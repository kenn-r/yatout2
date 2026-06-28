from django.db import models

# Create your models here.
class Prestation(models.Model):
    CHOIX_UNITE = [
        ('M2', 'Au mètre carré (m²)'),
        ('LOT_100', 'Par lot de 100 flyers'),
        ('LETTRE', 'À la lettre / Autocollant'),
    ]

    titre = models.CharField(max_length=200, verbose_name="Nom de la prestation")
    description = models.TextField(blank=True, verbose_name="Description")
    type_unite = models.CharField(max_length=10, choices=CHOIX_UNITE, default='M2', verbose_name="Type de calcul")
    prix_unitaire = models.IntegerField(verbose_name="Prix unitaire (FCFA)")
    image = models.ImageField(upload_to='prestations/', blank=True, null=True, verbose_name="Image du produit")

    def __str__(self):
        return self.titre