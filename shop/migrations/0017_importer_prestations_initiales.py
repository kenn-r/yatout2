from django.db import migrations

def ajouter_prestations(apps, schema_editor):
    # On récupère dynamiquement le modèle Prestation de l'application shop
    Prestation = apps.get_model('shop', 'Prestation')
    
    # Votre liste complète
    prestations_initiales = [
        {"titre": "Bâche Publicitaire", "type_unite": "M2"},
        {"titre": "Vinyle / Autocollant", "type_unite": "M2"},
        {"titre": "Roll-up / Kakemono", "type_unite": "M2"},
        {"titre": "Affiche Grand Format", "type_unite": "M2"},
        {"titre": "Impression Document", "type_unite": "LOT_100"},
        {"titre": "Flyers / Dépliants", "type_unite": "LOT_100"},
        {"titre": "Cartes de Visite", "type_unite": "LOT_100"},
        {"titre": "T-shirt Personnalisé", "type_unite": "LETTRE"},
        {"titre": "Casquette Logotée", "type_unite": "LETTRE"},
        {"titre": "Tasse / Mug", "type_unite": "LETTRE"},
        {"titre": "Stylos Personnalisés", "type_unite": "LETTRE"},
        {"titre": "Reliure de Dossier", "type_unite": "LETTRE"},
        {"titre": "Plastification", "type_unite": "LOT_100"},
        {"titre": "Brochures / Catalogues", "type_unite": "LETTRE"},
        {"titre": "Sacs Cabas", "type_unite": "LETTRE"},
    ]

    for p in prestations_initiales:
        # get_or_create évite les doublons si vous lancez la commande plusieurs fois
        Prestation.objects.get_or_create(
            titre=p["titre"],
            defaults={
                "type_unite": p["type_unite"],
                "prix_unitaire": 0,
                "description": "Prestation créée automatiquement."
            }
        )

def supprimer_prestations(apps, schema_editor):
    # Optionnel : permet d'annuler la migration si besoin
    Prestation = apps.get_model('shop', 'Prestation')
    Prestation.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        # Django liera automatiquement cette migration à la précédente de votre app 'shop'
        ('shop', '0016_realisation'), 
    ]

    operations = [
        migrations.RunPython(ajouter_prestations, supprimer_prestations),
    ]