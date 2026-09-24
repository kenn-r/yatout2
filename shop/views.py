from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.core.mail import send_mail
from django.db.models import Q
from .cart import Cart
from .models import Produit, Vendeur, Commande
from .forms import InscriptionVendeurForm, ProduitForm
from .models import Commande, LigneCommande
from .cart import Cart
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.timezone import now
from django.db.models import Q
import json
try:
    from google import genai
    from google.genai import types
    GOOGLE_SDK_DISPO = True
except ImportError:
    GOOGLE_SDK_DISPO = False

import requests
from .models import MessageAssistant, Produit
import os
import urllib.parse
from django.conf import settings
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from .models import Produit, CommandeImpression
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from django.db import connection
from shop.models import Facture

# Script de secours pour forcer la création de la table manquante
try:
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(Facture)
    print("✅ Succès : La table shop_facture a été créée physiquement !")
except Exception as e:
    # Si la table finit par se créer ou existe déjà, Django ignore l'erreur
    pass




# --- VUES EXISTANTES (CONSERVÉES ET CORRIGÉES) ---

def accueil(request):
    """Affiche la page d'accueil avec la barre de recherche globale."""
    recherche = request.GET.get('q', '')
    if recherche:
        produits = Produit.objects.filter(
            Q(nom__icontains=recherche) | Q(description__icontains=recherche)
        ).order_by('-date_ajout')
    else:
        produits = Produit.objects.all().order_by('-date_ajout')
        
    context = {
        'produits': produits,
        'recherche': recherche,
    }
    return render(request, 'shop/accueil.html', context)

def inscription_vendeur(request):
    """Gère la création d'un compte utilisateur et son profil vendeur."""
    if request.method == 'POST':
        form = InscriptionVendeurForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password']
                )
                vendeur = form.save(commit=False)
                vendeur.user = user
                vendeur.save()
                messages.success(request, "Votre compte vendeur a bien été créé ! Connectez-vous.")
                return redirect('connexion')
            except IntegrityError:
                messages.error(request, "Ce nom d'utilisateur est déjà pris. Veuillez en choisir un autre.")
    else:
        form = InscriptionVendeurForm()
    return render(request, 'shop/inscription_vendeur.html', {'form': form})

def connexion_vendeur(request):
    """Connecte l'utilisateur au site."""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, f"Bienvenue, {username} !")
                return redirect('dashboard_vendeur')
    else:
        form = AuthenticationForm()
    return render(request, 'shop/connexion.html', {'form': form})

def deconnexion_vendeur(request):
    """Déconnecte l'utilisateur."""
    auth_logout(request)
    messages.success(request, "Vous avez été déconnecté.")
    return redirect('accueil')

@login_required(login_url='connexion')
def ajouter_produit(request):
    """Permet à un vendeur connecté d'ajouter un produit à sa vitrine."""
    try:
        # 💡 SOLUTION : On interroge directement la table Vendeur avec l'utilisateur connecté
        vendeur = Vendeur.objects.get(user=request.user)
    except Vendeur.DoesNotExist:
        messages.error(request, "Vous devez posséder un compte vendeur pour effectuer cette action.")
        return redirect('inscription_vendeur')

    if request.method == 'POST':
        form = ProduitForm(request.POST, request.FILES)
        if form.is_valid():
            produit = form.save(commit=False)
            produit.vendeur = vendeur
            produit.save()
            messages.success(request, "Votre produit a été ajouté avec succès !")
            return redirect('accueil')
    else:
        form = ProduitForm()
        
    return render(request, 'shop/ajouter_produit.html', {'form': form})

def detail_produit(request, pk):
    """Affiche la fiche détaillée d'un article."""
    produit = get_object_or_404(Produit, pk=pk)
    return render(request, 'shop/detail_produit.html', {'produit': produit})


# --- NOUVELLES VUES POUR LE PANIER MULTI-ARTICLES ---

def ajouter_au_panier(request, pk):
    """Ajoute un produit au panier dans la session de l'utilisateur."""
    produit = get_object_or_404(Produit, pk=pk)
    
    if produit.stock <= 0:
        messages.error(request, "Ce produit est en rupture de stock.")
        return redirect('detail_produit', pk=produit.pk)
        
    # Récupérer le panier existant ou en créer un vide
    panier = request.session.get('panier', {})
    
    # Ajouter le produit ou augmenter la quantité
    id_produit = str(pk)
    if id_produit in panier:
        panier[id_produit] += 1
    else:
        panier[id_produit] = 1
        
    request.session['panier'] = panier
    messages.success(request, f"{produit.nom} a été ajouté à votre panier.")
    return redirect('voir_panier')


def voir_panier(request):
    """Affiche le contenu actuel du panier."""
    panier = request.session.get('panier', {})
    articles_panier = []
    total = 0
    
    for id_produit, quantite in panier.items():
        produit = get_object_or_404(Produit, pk=id_produit)
        total_article = produit.prix * quantite
        total += total_article
        articles_panier.append({
            'produit': produit,
            'quantite': quantite,
            'total_article': total_article
        })
        
    return render(request, 'shop/panier.html', {'articles_panier': articles_panier, 'total': total})


def supprimer_du_panier(request, pk):
    """Supprime un article du panier."""
    panier = request.session.get('panier', {})
    id_produit = str(pk)
    
    if id_produit in panier:
        del panier[id_produit]
        request.session['panier'] = panier
        messages.success(request, "L'article a été retiré du panier.")
        
    return redirect('voir_panier')


def valider_panier(request):
    """Gère la commande globale de tous les articles du panier."""
    panier = request.session.get('panier', {})
    
    if not panier:
        messages.error(request, "Votre panier est vide.")
        return redirect('accueil')
        
    if request.method == 'POST':
        nom = request.POST.get('nom')
        email = request.POST.get('email')
        adresse = request.POST.get('adresse')
        telephone = request.POST.get('telephone')
        
        # Créer une commande pour chaque type d'article dans le panier
        for id_produit, quantite in panier.items():
            produit = get_object_or_404(Produit, pk=id_produit)
            
            if produit.stock >= quantite:
                commande = Commande.objects.create(
                    produit=produit,
                    nom_client=nom,
                    email_client=email,
                    adresse=adresse,
                    telephone=telephone,
                    quantite=quantite
                )
                
                produit.stock -= quantite
                produit.save()
                
                # Notification Email Client
                send_mail(
                    subject=f"Confirmation de votre commande #{commande.id}",
                    message=f"Bonjour {nom},\n\nVotre commande pour {quantite}x {produit.nom} est validée !",
                    from_email="yatoutci2@gmail.com",
                    recipient_list=[email],
                    fail_silently=True,
                )
                
                # Notification Email Vendeur
                email_vendeur = produit.vendeur.user.email
                if email_vendeur:
                    send_mail(
                        subject="Nouvelle commande reçue !",
                        message=f"Le client {nom} a commandé {quantite}x {produit.nom}.",
                        from_email="yatoutci2@gmail.com",
                        recipient_list=[email_vendeur],
                        fail_silently=True,
                    )
            else:
                messages.error(request, f"Le produit {produit.nom} n'a plus assez de stock.")
                return redirect('voir_panier')
                
        # Vider le panier après achat réussi
        request.session['panier'] = {}
        messages.success(request, "Votre commande groupée a été validée avec succès !")
        return redirect('accueil')
        
    return render(request, 'shop/valider_panier.html')

# 🔴 REMPLACEZ LE BLOC DE LA LIGNE 266 À 268 PAR CELUI-CI :
def boutique_personnelle_vendeur(request, username):
    """Affiche uniquement les articles appartenant au vendeur spécifié dans l'URL"""
    # 1. On va chercher l'instance du modèle Vendeur en passant par la liaison user (ou username selon votre modèle)
    vendeur_profil = get_object_or_404(Vendeur, user__username=username)
    
    # 2. Maintenant le filtre fonctionne car vendeur_profil est bien une instance de "Vendeur"
    produits_vendeur = Produit.objects.filter(vendeur=vendeur_profil)
    
    return render(request, 'shop/boutique_privee.html', {
        'vendeur_vitrine': vendeur_profil,
        'produits': produits_vendeur
    })


# --- VUES EXISTANTES (CONSERVÉES ET RESTRUCTURÉES) ---

def passer_commande(request, pk):
    """GÈRE L'ACHAT DIRECT : Achat immédiat d'un seul article depuis sa fiche."""
    produit = get_object_or_404(Produit, pk=pk)
    
    # 1. Vérification des stocks
    if produit.stock <= 0:
        messages.error(request, "Désolé, ce produit est en rupture de stock !")
        return redirect('detail_produit', pk=produit.pk)
    
    # 2. Traitement du formulaire d'achat
    if request.method == 'POST':
        nom = request.POST.get('nom')
        email = request.POST.get('email')
        adresse = request.POST.get('adresse')
        telephone = request.POST.get('telephone')
        
        # ÉTAPE 1 : Création de la commande globale (champs valides de votre modèle Commande)
        commande = Commande.objects.create(
            nom_client=nom,
            email_client=email,
            adresse=adresse,
            telephone=telephone,
            statut='RECU'
        )
        
        # ÉTAPE 2 : Création de la ligne de commande (fait le lien avec le produit et le prix)
        LigneCommande.objects.create(
            commande=commande,
            produit=produit,
            prix=produit.prix,  # On fige le prix actuel du produit
            quantite=1
        )
        
        # Mise à jour du stock du produit
        produit.stock -= 1
        produit.save()
        
        # Envoi de l'e-mail de confirmation au client
        # /!\ Remplacer temporairement True par False pour forcer Django à afficher l'erreur s'il y en a une
        send_mail(
            subject=f"Confirmation de votre commande #{commande.id}",
            message=f"Bonjour {nom},\n\nMerci pour votre achat ! L'article '{produit.nom}' a bien été réservé.",
            from_email="yatoutci2@gmail.com",
            recipient_list=[email],
            fail_silently=False,  
        )
        
        # Envoi de l'e-mail de notification au vendeur
        email_vendeur = produit.vendeur.user.email
        if email_vendeur:
            send_mail(
                subject="Nouveauté ! Un client a commandé votre produit",
                message=f"Félicitations !\n\nL'article '{produit.nom}' a été commandé par {nom}.",
                from_email="yatoutci2@gmail.com",
                recipient_list=[email_vendeur],
                fail_silently=False,  
            )
            
        # Message de confirmation à l'écran et redirection vers le reçu
        messages.success(request, "Votre commande en achat direct a été validée avec succès !")
        return redirect('suivi_commande', pk=commande.id)
        
    # Si la méthode est GET, on affiche simplement le formulaire de commande
    return render(request, 'shop/passer_commande.html', {'produit': produit})



# --- GESTION DU DASHBOARD ET DES PRODUITS ---

@login_required
def dashboard_vendeur(request):
    """Affiche le tableau de bord du vendeur avec les statistiques globales et le top 3 des commandes."""
    try:
        vendeur = request.user.vendeur
    except Vendeur.DoesNotExist:
        return redirect('inscription_vendeur')

    # Catalogue complet du vendeur
    mes_produits = Produit.objects.filter(vendeur=vendeur)
    
    # 📊 1. TOUTES les ventes (Requis pour la jauge "Commandes reçues" et le calcul financier)
    toutes_les_ventes = Commande.objects.filter(
        items__produit__vendeur=vendeur
    ).distinct()

    # Calcul global des revenus (sur l'ensemble des ventes, pas seulement les 3 affichées)
    total_revenus = 0
    for vente in toutes_les_ventes:
        for item in vente.items.filter(produit__vendeur=vendeur):
            total_revenus += item.get_cost()

    nombre_ventes = toutes_les_ventes.count()
    articles_en_vente = mes_produits.count()

    # 🚚 2. LE TOP 3 DES COMMANDES (Uniquement pour l'affichage visuel du tableau HTML)
    mes_ventes_affichees = toutes_les_ventes.order_by('-date_commande')[:3]

    context = {
        'vendeur': vendeur,
        'produits': mes_produits,
        'ventes': mes_ventes_affichees,  # 👈 Ce tableau HTML contiendra exactement 3 lignes maximum
        'total_revenus': total_revenus,   # 👈 Reste juste (494500,00 XOF)
        'nombre_ventes': nombre_ventes,   # 👈 Reste juste (7)
        'articles_en_vente': articles_en_vente,
    }
    return render(request, 'shop/dashboard.html', context)


def suivi_commande(request, pk):
    """Affiche le reçu officiel ou l'état de livraison."""
    commande = get_object_or_404(Commande, pk=pk)
    return render(request, 'shop/suivi_commande.html', {'commande': commande})



@login_required(login_url='connexion')
def modifier_statut_commande(request, pk, nouveau_statut):
    """Permet au vendeur de faire progresser les étapes logistiques."""
    try:
        vendeur = request.user.vendeur
    except Vendeur.DoesNotExist:
        return redirect('inscription_vendeur')

    # CORRECTION : On passe par 'items__' pour valider la commande du vendeur
    commande = get_object_or_404(Commande.objects.filter(items__produit__vendeur=vendeur).distinct(), pk=pk)
    
    commande.statut = nouveau_statut
    commande.save()
    
    messages.success(request, "Le statut de la commande a bien été mis à jour.")
    return redirect('dashboard_vendeur')



def supprimer_produit(request, pk):
    """Supprime un produit en vérifiant la sécurité."""
    if not request.user.is_authenticated:
        messages.error(request, "Vous devez être connecté pour effectuer cette action.")
        return redirect('connexion')
    
    produit = get_object_or_404(Produit, pk=pk)
    
    try:
        if produit.vendeur != request.user.vendeur:
            messages.error(request, "Vous n'avez pas l'autorisation de supprimer ce produit.")
            return redirect('dashboard_vendeur')
    except Vendeur.DoesNotExist:
        messages.error(request, "Accès refusé.")
        return redirect('accueil')

    nom_produit = produit.nom
    produit.delete()
    messages.success(request, f"Le produit '{nom_produit}' a été supprimé avec succès.")
    return redirect('dashboard_vendeur') # Correction de la redirection


# --- GESTION DU PANIER (VOTRE CLASSE CART) ---

def panier_detail(request):
    """Affiche le contenu complet du panier."""
    cart = Cart(request)
    return render(request, 'shop/panier_detail.html', {'cart': cart})


def panier_ajouter(request, produit_id):
    """Ajoute un produit au panier."""
    cart = Cart(request)
    produit = get_object_or_404(Produit, id=produit_id)
    
    if produit.stock <= 0:
        messages.error(request, "Désolé, ce produit est en rupture de stock.")
        return redirect('accueil')
        
    cart.add(produit=produit, quantity=1)
    messages.success(request, f"{produit.nom} a été ajouté à votre panier.")
    return redirect('panier_detail')


def panier_supprimer(request, produit_id):
    """Supprime un produit spécifique du panier."""
    cart = Cart(request)
    produit = get_object_or_404(Produit, id=produit_id)
    cart.remove(produit)
    messages.success(request, f"{produit.nom} a été retiré de votre panier.")
    return redirect('panier_detail')





def passer_commande_panier(request):
    cart = Cart(request)
    
    if request.method == 'POST':
        # 1. Sécurité : On vérifie d'abord les stocks pour TOUS les articles du panier
        for item in cart:
            if item['produit'].stock < item['quantity']:
                messages.error(
                    request, 
                    f"Désolé, le produit '{item['produit'].nom}' n'a plus assez de stock disponible "
                    f"({item['produit'].stock} restants). Veuillez modifier votre panier."
                )
                return redirect('panier_detail')  # Redirige vers le panier si le stock est insuffisant

        # 2. Récupération des données du formulaire de livraison
        nom = request.POST.get('nom')
        email = request.POST.get('email')
        telephone = request.POST.get('telephone')
        adresse = request.POST.get('adresse')
        
        # 3. Création de la commande globale
        commande = Commande.objects.create(
            nom_client=nom,
            email_client=email,
            telephone=telephone,
            adresse=adresse
        )
        
        # Structure pour regrouper les articles par vendeur afin de ne pas leur envoyer 10 mails
        articles_par_vendeur = {}
        
        # 4. Enregistrement des articles du panier + Mise à jour des stocks
        for item in cart:
            produit = item['produit']
            quantite_commandee = item['quantity']
            
            # Enregistrement de la ligne de commande en BDD
            LigneCommande.objects.create(
                commande=commande,
                produit=produit,
                prix=item['price'],
                quantite=quantite_commandee
            )
            
            # 🛠️ CORRECTION : Diminuer le stock du produit et sauvegarder la modification en BDD
            if produit.stock >= quantite_commandee:
                produit.stock -= quantite_commandee
            else:
                produit.stock = 0
            produit.save()  # Sauvegarde obligatoire du nouveau stock en base de données
            
            # Récupération du vendeur du produit (via la propriété .email que nous avons créée)
            vendeur = produit.vendeur 
            vendeur_email = vendeur.email  
            
            if vendeur_email:
                if vendeur_email not in articles_par_vendeur:
                    articles_par_vendeur[vendeur_email] = []
                articles_par_vendeur[vendeur_email].append(f"- {produit.nom} (Qté: {quantite_commandee})")

        # 5. ENVOI DE L'E-MAIL AU CLIENT
        if email:
            sujet_client = f"Confirmation de votre commande #{commande.id}"
            message_client = f"Bonjour {nom},\n\nMerci pour votre commande ! Elle a bien été enregistrée sous le numéro #{commande.id}.\nNous préparons vos articles."
            
            send_mail(
                sujet_client,
                message_client,
                'yatoutci2@gmail.com',  # Votre EMAIL_HOST_USER
                [email],               # Email du client
                fail_silently=False    
            )

        # 6. ENVOI DES E-MAILS AUX VENDEURS
        for email_vendeur, liste_produits in articles_par_vendeur.items():
            sujet_vendeur = f"Nouvelle commande reçue ! #{commande.id}"
            details_produits = "\n".join(liste_produits)
            message_vendeur = f"Bonjour,\n\nUn client a commandé les articles suivants dans votre boutique :\n\n{details_produits}\n\nVeuillez préparer l'expédition."
            
            send_mail(
                sujet_vendeur,
                message_vendeur,
                'yatoutci2@gmail.com',
                [email_vendeur],   # Email du vendeur concerné
                fail_silently=False
            )
        
        # 7. On vide le panier et on redirige vers le suivi
        cart.clear()
        return redirect('suivi_commande', pk=commande.id)
        
    return render(request, 'shop/passer_commande_panier.html', {'cart': cart})

import os  # Vérifiez que cet import est bien présent tout en haut du fichier

@csrf_exempt
def assistant_chatbot_api(request):
    # Récupération invisible et sécurisée de la clé d'environnement
    api_key = os.environ.get("CLE_API_GEMINI")
    
    reponse_bot = "Désolé, je rencontre des difficultés techniques à me connecter."
    session_key = ''

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_client = data.get('message', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données invalides'}, status=400)

        if not message_client:
            return JsonResponse({'error': 'Message vide'}, status=400)

        # 1. Sauvegarde du message envoyé par le client en BDD
        try:
            session_key = request.session.session_key or ''
            if not request.session.exists(session_key):
                request.session.create()
                session_key = request.session.session_key

            MessageAssistant.objects.create(
                user=request.user if request.user.is_authenticated else None,
                session_key=session_key,
                message=message_client,
                est_assistant=False
            )
        except Exception as e:
            print(f"Erreur BDD Client: {e}")

        # =====================================================================
        # 2. 🔍 RECHERCHE EN BDD : BOUTIQUE (PRODUITS) + IMPRIMERIE (PRESTATIONS)
        # =====================================================================
        contexte_produits = "Aucun produit spécifique trouvé pour cette recherche."
        contexte_impressions = "Aucun support d'impression spécifique trouvé pour cette demande."
        
        # --- A. RECHERCHE CÔTÉ BOUTIQUE ---
        mots_cles_catalogue = ['produit', 'article', 'vendre', 'acheter', 'catalogue', 'dispo', 'boutique', 'promotion', 'promo', 'solde', 'rabais']
        un_mot_cle_trouve = any(mot in message_client.lower() for mot in mots_cles_catalogue)
        
        if un_mot_cle_trouve or len(message_client) > 2:
            produits_trouves = Produit.objects.filter(
                Q(nom__icontains=message_client) | Q(description__icontains=message_client),
                stock__gt=0
            ).select_related('vendeur').distinct()[:5]
            
            if 'promo' in message_client.lower() or 'solde' in message_client.lower() or 'rabais' in message_client.lower():
                produits_trouves = Produit.objects.filter(ancien_prix__gt=F('prix'), stock__gt=0).select_related('vendeur')[:5]

            if produits_trouves.exists():
                liste_p = []
                for p in produits_trouves:
                    devise = p.vendeur.get_devise_display() if hasattr(p.vendeur, 'get_devise_display') else p.vendeur.devise
                    info_p = f"- {p.nom} : {p.prix} {devise} (Boutique : {p.vendeur.nom_boutique})"
                    if p.ancien_prix and p.ancien_prix > p.prix:
                        info_p += f" [En PROMO ! Prix d'origine: {p.ancien_prix} {devise} - Remise immédiate de {p.reduction_pourcentage}%]"
                    liste_p.append(info_p)
                contexte_produits = "Voici les articles réels trouvés sur notre catalogue :\n" + "\n".join(liste_p)

        # --- B. RECHERCHE CÔTÉ ATELIER D'IMPRESSION ---
        mots_cles_impression = ['impression', 'imprimer', 'affiche', 'bache', 'bâche', 'flyer', 'support', 'autocollant', 'lettre', 'f cfa', 'fcfa']
        besoin_impression = any(mot in message_client.lower() for mot in mots_cles_impression)

        if besoin_impression or len(message_client) > 2:
            prestations_trouvees = Prestation.objects.filter(
                Q(titre__icontains=message_client) | Q(description__icontains=message_client)
            ).distinct()[:4]
            
            if 'support' in message_client.lower() or 'tarifs' in message_client.lower() or 'prix' in message_client.lower() or not prestations_trouvees.exists():
                prestations_trouvees = Prestation.objects.all()[:4]

            if prestations_trouvees.exists():
                liste_i = []
                for prest in prestations_trouvees:
                    unite = prest.get_type_unite_display() if hasattr(prest, 'get_type_unite_display') else prest.type_unite
                    liste_i.append(f"- {prest.titre} : {prest.prix_unitaire} FCFA ({unite})")
                contexte_impressions = "Supports d'imprimerie disponibles à l'atelier YaTout :\n" + "\n".join(liste_i)

        # 3. CONSTITUTION DE L'HISTORIQUE CHRONOLOGIQUE
        try:
            anciens_messages = MessageAssistant.objects.filter(session_key=session_key).order_by('-id')[:10]
            anciens_messages = reversed(anciens_messages)
        except Exception as e:
            print(f"Erreur historique : {e}")
            anciens_messages = []

        historique_payload = []
        for msg in anciens_messages:
            role = "model" if msg.est_assistant else "user"
            historique_payload.append({
                "role": role,
                "parts": [{"text": msg.message}]
            })

        # 4. REQUÊTE SÉCURISÉE VERS L'API GOOGLE GEMINI
        try:
            url_api = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            date_aujourdhui = now().strftime("%A %d %B %Y")
            
            instructions_systeme = (
    "Tu es l'assistant virtuel officiel du site d'e-commerce multi-vendeur 'YaTout' (ou YaTout Ci) et de son atelier 'YaTout Impression'. "
    "Ton rôle est d'aider les acheteurs, les vendeurs et les clients de l'atelier avec politesse, enthousiasme et de manière concise. "
    f"Information temporelle importante : Nous sommes aujourd'hui le {date_aujourdhui}. "
    "Règles strictes du site à connaître : "
    "1. Pour commander en boutique : ajouter au panier, aller dans 'Mon Panier' en haut à droite, valider la livraison. Le paiement se fait en liquide à la livraison. "
    "2. Pour l'atelier d'impression : le client sélectionne son support à gauche, ajuste ses options (finitions, délais) et remplit le formulaire à droite pour simuler son devis en direct. "
    "3. La remise commerciale standard de l'atelier est de 5% incluse sur le Net à payer. Finitions dispo : Standard, Mate (+10%), Vernis sélectif. "
    "4. Le site gère plusieurs devises (FCFA, MAD, EUR...) selon le choix du vendeur. "
    
    "\n--- RÈGLES COMPTABLES ET DE REMISE DE L'ATELIER ---\n"
    "- Utilise TOUJOURS le terme 'Remise' ou 'Remise commerciale', n'utilise JAMAIS le mot 'Réduction' ni 'Rabais'. "
    "- La remise doit obligatoirement être calculée automatiquement et détaillée sur chaque article individuellement d'abord (colonne Rem. % ou Remise / Art.). "
    "- À la fin du document, le total affiche une 'Remise globale de la marchandise' qui cumule automatiquement toutes les remises. "
    "- RÈGLE CRUCIALE POUR LE FCFA : Le FCFA n'utilise AUCUNE décimale. Arrondis toujours les calculs financiers à l'entier strict (Ex: 45.000 FCFA et non 45.000,00 FCFA). Utilise des points pour séparer les milliers. "
    
    "\n--- EXEMPLES DE DIALOGUES TYPES POUR LE CALCUL DES REMISES ---\n"
    "Exemple 1 (Demande de prix standard) :\n"
    "Client : 'Quel est le prix pour 1 Bâche à 25.000 FCFA et 2 tasses à 2.200 FCFA l'unité ?'\n"
    "IA : 'Voici le détail de votre simulation avec notre remise standard de 5% intégrée : \n"
    "• 1 Bâche : 25.000 FCFA | Remise : 5% (-1.250 FCFA) | Total Net : 23.750 FCFA\n"
    "• 2 Tasses : 4.400 FCFA | Remise : 5% (-220 FCFA) | Total Net : 4.180 FCFA\n"
    "-------------------------\n"
    "• Montant Brut total : 29.400 FCFA\n"
    "• Remise globale de la marchandise : -1.470 FCFA\n"
    "• Net à payer : 27.930 FCFA 🎯'\n\n"
    
    "Exemple 2 (Vérification de format monétaire) :\n"
    "Client : 'Est-ce que j'ai une réduction ?'\n"
    "IA : 'Nous n'appliquons pas de réduction, mais vous bénéficiez automatiquement d'une remise commerciale de 5% sur chaque article ! Par exemple, pour un support à 10.000 FCFA, la remise par article est de 500 FCFA, ce qui vous fait un total net par ligne de 9.500 FCFA. ✨'\n"
    
    "\n--- SUPPORTS D'IMPRESSION EN DIRECT ---\n"
    f"{contexte_impressions}\n"
    "\n--- STOCKS ET PRODUITS DE LA BOUTIQUE ---\n"
    f"{contexte_produits}\n"
    "Règle d'or : Ne vends et n'invente jamais de produits ou de supports imaginaires. Utilise strictement les listes ci-dessus. "
    "Réponds toujours en français, utilise des émojis appropriés et reste amical."
)

            payload = {
                "contents": historique_payload,
                "systemInstruction": {"parts": [{"text": instructions_systeme}]},
                "generationConfig": {
                    "maxOutputTokens": 300,
                    "temperature": 0.7
                }
            }

            headers = {
                'Content-Type': 'application/json',
                'x-goog-api-key': api_key
            }
            
            response = requests.post(url_api, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                resultat = response.json()
                reponse_bot = resultat['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 503:
                reponse_bot = "Oups ! Je suis un peu surchargé par les demandes en ce moment. 🤖 Pouvez-vous répéter votre question dans quelques secondes ?"
            elif response.status_code == 429:
                reponse_bot = "Vous allez un peu trop vite pour moi ! ⚡ Laissez-moi respirer quelques instants avant de poser votre prochaine question."
            else:
                reponse_bot = "Je rencontre une petite difficulté à joindre mes serveurs centraux. Réessayez d'ici un instant !"

        except Exception as e:
            reponse_bot = f"Une erreur technique est survenue lors de la communication avec l'IA : {e}"

        # 5. Sauvegarde de la réponse finale de l'IA en BDD
        try:
            MessageAssistant.objects.create(
                user=request.user if request.user.is_authenticated else None,
                session_key=session_key,
                message=reponse_bot,
                est_assistant=True
            )
        except Exception as e:
            print(f"Erreur BDD Assistant: {e}")

        return JsonResponse({'reponse': reponse_bot})

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


def bienvenue(request):
    return render(request, 'shop/bienvenue.html')






def generer_bon_pdf(request, commande_id):
    # Récupération de la commande principale
    commande = get_object_or_404(CommandeImpression, id=commande_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{commande.numero_bon_commande()}.pdf"'

    # Marges définies à 40 points
    marge_gauche = 40
    marge_droite = 40
    
    doc = SimpleDocTemplate(
        response, 
        pagesize=letter, 
        rightMargin=marge_droite, 
        leftMargin=marge_gauche, topMargin=40, 
        bottomMargin=40
    )
    story = []
    
    # --- CALCUL DE LA LARGEUR MAXIMALE DISPONIBLE SUR LA FEUILLE ---
    largeur_page = letter[0]  
    largeur_utile = largeur_page - (marge_gauche + marge_droite) 
    
    styles = getSampleStyleSheet()
    normal_style = styles['Normal']
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontName='Helvetica-Bold')
    
    # Styles d'alignement pour les prix et remises dans le tableau
    style_prix_entete = ParagraphStyle('PrixEntete', parent=bold_style, alignment=2) 
    style_prix_cellule = ParagraphStyle('PrixCellule', parent=normal_style, alignment=2) 
    style_remise_cellule = ParagraphStyle('RemiseCellule', parent=normal_style, alignment=2, textColor=colors.HexColor("#CC0000"))

    # --- 1. CONFIGURATION DU BLOC GAUCHE (ENTREPRISE + INFOS BON) ---
    bloc_gauche = []
    titre_document = "BON DE LIVRAISON" if getattr(commande, 'bl_genere', False) else "BON DE COMMANDE"
    
    chemin_logo = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    if os.path.exists(chemin_logo):
        logo = Image(chemin_logo, width=110, height=45)
        logo.hAlign = 'LEFT'
        bloc_gauche.append(logo)
        bloc_gauche.append(Spacer(1, 5))
        
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#2E0854"), spaceAfter=3)
    bloc_gauche.append(Paragraph(f"<b>{titre_document}</b>", title_style))
    bloc_gauche.append(Paragraph("<font size=9 color='#7b6f93'>YaTout Print — Atelier d'Impression</font>", normal_style))
    
    bloc_gauche.append(Spacer(1, 10))
    bloc_gauche.append(Paragraph(f"<b>Numéro :</b> {commande.numero_bon_commande()}", normal_style))
    bloc_gauche.append(Paragraph(f"<b>Date :</b> {commande.date_commande.strftime('%d/%m/%Y à %H:%M')}", normal_style))

    # --- 2. CONFIGURATION DU BLOC DROITE (COORDONNÉES CLIENT) ---
    bloc_droite = []
    client_title_style = ParagraphStyle('ClientTitle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor("#2E0854"), spaceAfter=8)
    bloc_droite.append(Paragraph("<b>FACTURE & DESTINATAIRE</b>", client_title_style))
    bloc_droite.append(Paragraph(f"<b>Client :</b> {commande.nom_client}", normal_style))
    
    tel_affiche = commande.telephone if commande.telephone.startswith(('+', '00')) else f"+225 {commande.telephone}"
    bloc_droite.append(Paragraph(f"<b>Contact :</b> {tel_affiche}", normal_style))
    bloc_droite.append(Paragraph(f"<b>Email :</b> {commande.email_client}", normal_style))

    # --- 3. ALIGNEMENT FACE À FACE ---
    largeur_bloc_entete = largeur_utile / 2
    table_en_tete = Table([[bloc_gauche, bloc_droite]], colWidths=[largeur_bloc_entete, largeur_bloc_entete])
    table_en_tete.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(table_en_tete)
    
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#C8BED6"), spaceAfter=20, spaceBefore=0))

    # --- 4. TABLEAU DES ARTICLES ---
    col_prix = 80
    col_qte = 45
    col_remise = 85   
    col_total = 95
    col_designation = largeur_utile - (col_prix + col_qte + col_remise + col_total)

    data = [
        [Paragraph("<b>Désignation Prestation</b>", bold_style), 
         Paragraph("<b>Prix Unit.</b>", style_prix_entete), 
         Paragraph("<b>Qté</b>", bold_style), 
         Paragraph("<b>Remise / Art.</b>", style_prix_entete), 
         Paragraph("<b>Total Net</b>", style_prix_entete)]
    ]
    
    articles = json.loads(commande.details_json)
    
    for art in articles:
        qte_valeur = int(art.get('qte', art.get('quantite', 1)))
        prix_unit = int(float(art.get('prix', 0)))
        total_net = int(float(art.get('total', 0)))
        
        # Calcul du brut de la ligne pour trouver le pourcentage
        brut_ligne = qte_valeur * prix_unit
        
        # 1. Récupération du pourcentage ou calcul depuis le montant brut
        taux_remise = int(float(art.get('remise_pourcent', 0)))
        
        if taux_remise == 0:
            remise_art_valeur = int(art.get('remise', 0))
            if remise_art_valeur == 0 and getattr(commande, 'montant_remise', 0) > 0:
                remise_art_valeur = int(commande.montant_remise)
            
            # Déduction du pourcentage exact basé sur le montant de la remise
            if remise_art_valeur > 0 and brut_ligne > 0:
                taux_remise = int(round((remise_art_valeur / brut_ligne) * 100))

        # 2. Construction du texte à afficher (ex: "5 %" ou "0 %")
        texte_remise = f"{taux_remise} %" if taux_remise > 0 else "0 %"
    
        # 3. Ajout de la ligne dans le tableau
        data.append([
            Paragraph(f"<b>{art.get('titre', 'Impression')}</b>", normal_style),
            Paragraph(f"{prix_unit:,}".replace(',', '.') + " FCFA", style_prix_cellule),
            Paragraph(f"x{qte_valeur}", normal_style),  
            Paragraph(texte_remise, style_remise_cellule if taux_remise > 0 else style_prix_cellule),
            Paragraph(f"{total_net:,}".replace(',', '.') + " FCFA", style_prix_cellule)
        ])

    # Formatage des totaux du bas
    total_brut_int = int(commande.total_brut)
    montant_remise_int = int(commande.montant_remise)
    total_final_int = int(commande.total_final)

    data.append(["", "", "", Paragraph("<b>Total Brut :</b>", bold_style), Paragraph(f"<b>{total_brut_int:,} FCFA</b>".replace(',', '.'), style_prix_cellule)])
    data.append(["", "", "", Paragraph("<font color='red'><b>Remise globale :</b></font>", bold_style), Paragraph(f"<font color='red'><b>-{montant_remise_int:,} FCFA</b></font>".replace(',', '.'), style_prix_cellule)])
    data.append(["", "", "", Paragraph("<b>NET A PAYER :</b>", bold_style), Paragraph(f"<b>{total_final_int:,} FCFA</b>".replace(',', '.'), style_prix_cellule)])

    # Application de la structure à 5 colonnes
    tableau = Table(data, colWidths=[col_designation, col_prix, col_qte, col_remise, col_total])
    tableau.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3E8FF")),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),      
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),     
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),    
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),     
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),     
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, len(articles)), 0.5, colors.HexColor("#E8E3F0")),
        ('LINEABOVE', (3, -1), (4, -1), 1.5, colors.HexColor("#2E0854")),
        ('TOPPADDING', (0, 0), (-1, -1), 7),     
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))

    story.append(tableau)
    
    # --- 5. BLOC DE SIGNATURE ET DOCUMENTATION LOGISTIQUE ---
    story.append(Spacer(1, 35))
    
    style_visa = ParagraphStyle('VisaStyle', parent=bold_style, fontSize=10, textColor=colors.HexColor("#555555"))
    cell_livreur = [Paragraph("<b>Visa Livreur / Cachet</b>", style_visa), Spacer(1, 40)]
    cell_client = [Paragraph("<b>Visa Client (Lu et approuvé)</b>", style_visa), Spacer(1, 40)]
    
    table_visa = Table([[cell_livreur, cell_client]], colWidths=[largeur_utile/2, largeur_utile/2])
    table_visa.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor("#CCCCCC")), 
        ('LINEBELOW', (1, 0), (1, 0), 0.5, colors.HexColor("#CCCCCC")),
        ('RIGHTPADDING', (0, 0), (0, 0), 30), 
        ('LEFTPADDING', (1, 0), (1, 0), 30),
    ]))
    story.append(table_visa)

    doc.build(story)
    return response





@staff_member_required
def liste_commandes_admin(request):
    """
    Tableau de bord administrateur qui calcule les totaux et extrait 
    la liste des achats pour le template HTML.
    """
    # 1. On récupère toutes les commandes triées par nouveauté
    commandes = CommandeImpression.objects.all().order_by('-date_commande')
    
    # 2. On parcourt chaque commande pour injecter les données requises par le template
    for cmd in commandes:
        # A. Votre méthode existante pour les calculs financiers
        cmd.totaux = cmd.calcul_total() 
        
        # B. 💡 L'AJUSTEMENT : Extraction du JSON pour alimenter la colonne "Liste des achats"
        try:
            cmd.articles_liste = json.loads(cmd.details_json)
        except (json.JSONDecodeError, TypeError):
            cmd.articles_liste = [] # Sécurité si le champ est vide ou mal formé
        
    # On retourne le template 'shop/liste_commandes_admin.html' que vous venez de créer
    return render(request, 'shop/liste_commandes_admin.html', {'commandes': commandes})


@staff_member_required
def valider_commande_impression(request, commande_id):
    """Action du bouton vert pour passer le statut à validé et activer le BL."""
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    commande.statut = 'VALIDE'
    commande.bl_genere = True
    commande.save()
    
    messages.success(request, f"La commande {commande.numero_bon()} a été validée avec succès !")
    return redirect('liste_commandes_admin')



@staff_member_required
def basculer_remise(request, commande_id):
    """ Active ou désactive la remise de 5% et rafraîchit la page """
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    # Si c'était Vrai, ça devient Faux, et inversement
    commande.remise_appliquee = not commande.remise_appliquee
    commande.save()
    # On redirige vers le tableau de bord
    return redirect('liste_commandes_admin')


@staff_member_required
def liste_commandes_admin(request):
    """ Affiche toutes les commandes d'impression reçues sur le site """
    commandes = CommandeImpression.objects.all().order_by('-date_commande')
    
    # On décode le JSON de chaque commande pour l'afficher sous forme de liste dans le tableau HTML
    for cmd in commandes:
        cmd.articles_liste = json.loads(cmd.details_json)
        
    return render(request, 'shop/admin_commandes.html', {'commandes': commandes})




@staff_member_required
def valider_commande_impression(request, commande_id):
    """ Change le statut de la commande en VALIDE lors du clic sur le bouton """
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    commande.statut = 'VALIDE'
    commande.save()
    
    # ENVOI D'UN EMAIL DE CONFIRMATION DE VALIDATION AU CLIENT
    sujet = f"✅ Votre bon d'impression #{commande.numero_bon_commande()} a été validé !"
    message = f"Bonjour {commande.nom_client},\n\nBonne nouvelle ! L'administrateur de YaTout vient de valider votre bon de commande.\n\nNous lançons la fabrication de vos impressions. Nous vous contacterons très vite au {commande.telephone} dès que vos supports seront prêts.\n\nMerci pour votre confiance !"
    
    try:
        send_mail(sujet, message, 'noreply@yatout.com', [commande.email_client], fail_silently=True)
    except Exception:
        pass
        
    return redirect('liste_commandes_admin')








# API AJAX : Ajoute ou modifie la quantité sans recharger la page
def modifier_panier_print_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            # 🟢 CORRECTION : On extrait 'prestation_id' pour correspondre au JavaScript
            prest_id = str(data.get('prestation_id'))
            action = data.get('action') # 'ajouter', 'modifier' ou 'supprimer'
            qte = int(data.get('quantite', 1))
        except (json.JSONDecodeError, ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Données invalides'}, status=400)

        if not prest_id or prest_id == 'None':
            return JsonResponse({'status': 'error', 'message': 'ID de prestation manquant'}, status=400)

        if 'panier_print' not in request.session:
            request.session['panier_print'] = {}
        panier = request.session['panier_print']

        if action == 'ajouter':
            panier[prest_id] = panier.get(prest_id, 0) + 1
        elif action == 'modifier':
            if qte > 0:
                panier[prest_id] = qte
            else:
                panier.pop(prest_id, None)
        elif action == 'supprimer':
            panier.pop(prest_id, None)

        request.session['panier_print'] = panier
        request.session.modified = True
        return JsonResponse({'status': 'success'})
        
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)

    




# 1. Vue pour la page du conseiller (Faux chat en pur HTML)
def page_conseiller(request):
    # Numéro WhatsApp de Côte d'Ivoire (à modifier par le vôtre sans le +)
    numero_whatsapp = "2250574702092" 
    texte_message = "Bonjour YaTout, je souhaite échanger avec un conseiller concernant vos prestations d'impression."
    
    # Formatage du lien pour WhatsApp
    lien_whatsapp = f"https://wa.me/{numero_whatsapp}?text={texte_message.replace(' ', '%20')}"
    
    return render(request, 'shop/conseiller.html', {'lien_whatsapp': lien_whatsapp})

from django.shortcuts import render, get_object_or_404

from django.shortcuts import render, get_object_or_404
from itertools import groupby
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import (
    SupportFlyer, TarifOptionFlyer,
    SupportGrandFormat,
    SupportObjetPublicitaire, PalierPrixObjet,
    ServiceFaconnage
)

@staff_member_required
def backoffice_print_manager(request):
    """
    Contrôleur d'administration individualisé de l'atelier d'impression.
    Gère l'ajout, l'édition des remises et la suppression pour chaque type d'article.
    """
    
    # 📋 CHARGEMENT DES COMPOSANTS PAR MODULE DE SÉCURITÉ
    flyers = SupportFlyer.objects.all().prefetch_related('tarifs_specifiques')
    grands_formats = SupportGrandFormat.objects.all()
    goodies = SupportObjetPublicitaire.objects.all().prefetch_related('paliers_prix')
    faconnages = ServiceFaconnage.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        # =====================================================================
        # 🖨️ TRAITEMENT INDIVIDUEL : MODULE 1 (FLYERS, CARTES, DÉPLIANTS)
        # =====================================================================
        if action == 'creer_flyer':
            SupportFlyer.objects.create(
                titre=request.POST.get('titre'),
                description=request.POST.get('description', ''),
                remise_globale=int(request.POST.get('remise', 0)),
                image=request.FILES.get('image')
            )
            messages.success(request, "Nouveau support de type Flyer/Carte activé.")

        elif action == 'prix_flyer':
            flyer_obj = get_object_or_404(SupportFlyer, id=request.POST.get('article_id'))
            TarifOptionFlyer.objects.create(
                flyer=flyer_obj,
                format_papier=request.POST.get('format_papier'),
                quantite=int(request.POST.get('quantite')),
                prix_total_lot=float(request.POST.get('prix_total_lot'))
            )
            messages.success(request, f"Nouveau lot de tarifs ajouté sur {flyer_obj.titre}.")

        elif action == 'supprimer_option_flyer':
            tarif = get_object_or_404(TarifOptionFlyer, id=request.POST.get('option_id'))
            tarif.delete()
            messages.success(request, "Ligne tarifaire du flyer supprimée.")

        elif action == 'supprimer_flyer_total':
            support = get_object_or_404(SupportFlyer, id=request.POST.get('article_id'))
            support.delete()
            messages.success(request, f"Le catalogue '{support.titre}' et ses tarifs ont été supprimés.")


        # =====================================================================
        # 🖼️ TRAITEMENT INDIVIDUEL : MODULE 2 (BÂCHES, VINYLES, AFFICHES)
        # =====================================================================
        elif action == 'creer_grand_format':
            SupportGrandFormat.objects.create(
                titre=request.POST.get('titre'),
                description=request.POST.get('description', ''),
                prix_au_metre_carre=float(request.POST.get('prix_m2')),
                remise_globale=int(request.POST.get('remise', 0)),
                image=request.FILES.get('image')
            )
            messages.success(request, "Nouveau support Grand Format (Bâche/Vinyle) configuré.")

        elif action == 'maj_prix_grand_format':
            gf_obj = get_object_or_404(SupportGrandFormat, id=request.POST.get('article_id'))
            gf_obj.prix_au_metre_carre = float(request.POST.get('prix_m2'))
            gf_obj.remise_globale = int(request.POST.get('remise', 0))
            gf_obj.save()
            messages.success(request, f"Tarif au M² et remises mis à jour pour {gf_obj.titre}.")

        elif action == 'supprimer_grand_format':
            support = get_object_or_404(SupportGrandFormat, id=request.POST.get('article_id'))
            support.delete()
            messages.success(request, f"Le support '{support.titre}' a été retiré de la boutique.")


        # =====================================================================
        # ☕ TRAITEMENT INDIVIDUEL : MODULE 3 (MUGS, T-SHIRTS, KÉPIS, CHAPEAUX)
        # =====================================================================
        elif action == 'creer_goodies':
            SupportObjetPublicitaire.objects.create(
                titre=request.POST.get('titre'),
                description=request.POST.get('description', ''),
                remise_globale=int(request.POST.get('remise', 0)),
                image=request.FILES.get('image')
            )
            messages.success(request, "Nouvel objet publicitaire (Mug/T-shirt/Képi) initialisé.")

        elif action == 'palier_goodies':
            objet_obj = get_object_or_404(SupportObjetPublicitaire, id=request.POST.get('article_id'))
            PalierPrixObjet.objects.create(
                objet=objet_obj,
                quantite_minimale=int(request.POST.get('quantite_minimale')),
                prix_unitaire=float(request.POST.get('prix_unitaire'))
            )
            messages.success(request, f"Palier dégressif enregistré sur l'objet {objet_obj.titre}.")

        elif action == 'supprimer_palier_goodies':
            palier = get_object_or_404(PalierPrixObjet, id=request.POST.get('palier_id'))
            palier.delete()
            messages.success(request, "Palier volumétrique supprimé.")

        elif action == 'supprimer_goodies_total':
            support = get_object_or_404(SupportObjetPublicitaire, id=request.POST.get('article_id'))
            support.delete()
            messages.success(request, f"L'objet '{support.titre}' a été entièrement retiré.")


        # =====================================================================
        # 📚 TRAITEMENT INDIVIDUEL : MODULE 4 (PHOTOCOPIES, RELIURES)
        # =====================================================================
        elif action == 'creer_faconnage':
            ServiceFaconnage.objects.create(
                titre=request.POST.get('titre'),
                description=request.POST.get('description', ''),
                prix_fixe_unitaire=float(request.POST.get('prix_unitaire')),
                remise_globale=int(request.POST.get('remise', 0))
            )
            messages.success(request, "Nouveau service de façonnage/reprographie ajouté.")

        elif action == 'maj_faconnage':
            service = get_object_or_404(ServiceFaconnage, id=request.POST.get('article_id'))
            service.prix_fixe_unitaire = float(request.POST.get('prix_unitaire'))
            service.remise_globale = int(request.POST.get('remise', 0))
            service.save()
            messages.success(request, f"Tarification mise à jour pour le façonnage : {service.titre}.")

        elif action == 'supprimer_faconnage':
            service = get_object_or_404(ServiceFaconnage, id=request.POST.get('article_id'))
            service.delete()
            messages.success(request, f"Le service '{service.titre}' a été supprimé.")

        # Rechargement propre de la page pour vider les formulaires soumis
        return redirect('backoffice_print_manager')

    context = {
        'flyers': flyers,
        'grands_formats': grands_formats,
        'goodies': goodies,
        'faconnages': faconnages,
    }
    return render(request, 'shop/print_manager.html', context)



def page_prestations(request):
    """ Vue catalogue gérant l'arborescence dynamique par type d'unité """
    
    # 1. Récupération des filtres dans l'URL
    type_unite_clique = request.GET.get('type_unite')
    id_prestation = request.GET.get('prestation_id')
    
    prestation_selectionnee = None
    formats_disponibles = []
    prestations_a_afficher = []
    nom_categorie_active = ""
    
    # ÉTAPE A : Détail des tarifs d'un modèle précis (ex: Flyer A5)
    if id_prestation:
        prestation_selectionnee = get_object_or_404(Prestation, id=id_prestation)
        formats_disponibles = prestation_selectionnee.formats_flyer.all()
        
    # ÉTAPE B : L'utilisateur a cliqué sur une catégorie (Flyer, Surface, Unité, Pages...)
    elif type_unite_clique:
        prestations_a_afficher = Prestation.objects.filter(type_unite=type_unite_clique)
        
        # On récupère le nom propre de la catégorie pour l'afficher dans le titre h1
        dict_choix = dict(Prestation.CHOIX_UNITE)
        nom_categorie_active = dict_choix.get(type_unite_clique, "Supports")

    # 🟢 DYNAMIQUE : On extrait la liste des types actuellement configurés en base
    # pour ne pas afficher de catégories vides sur l'écran d'accueil
    types_utilises = Prestation.objects.values_list('type_unite', flat=True).distinct()
    
    categories_accueil = []
    for code, nom in Prestation.CHOIX_UNITE:
        if code in types_utilises:
            # Pour chaque catégorie, on récupère le premier produit pour illustrer la carte
            premier_produit = Prestation.objects.filter(type_unite=code).first()
            categories_accueil.append({
                'code': code,
                'nom': nom.split('(')[0].strip(), # Nettoie le nom (ex: "Lots & Paliers par Format")
                'details': nom,
                'image': premier_produit.image if premier_produit else None
            })

    # Galerie photo automatique
    exemples_realisations = ProduitRealise.objects.all() if 'ProduitRealise' in globals() else []

    return render(request, 'shop/prestations.html', {
        'type_unite_clique': type_unite_clique,
        'nom_categorie_active': nom_categorie_active,
        'prestations_a_afficher': prestations_a_afficher,
        'categories_accueil': categories_accueil, # 🟢 Liste dynamique pour l'accueil
        'prestation_selectionnee': prestation_selectionnee,
        'formats_disponibles': formats_disponibles,
        'exemples_realisations': exemples_realisations,
    })

from django.shortcuts import render, get_object_or_404

from .models import (
    SupportFlyer,
    SupportGrandFormat,
    SupportObjetPublicitaire,
    ServiceFaconnage,
)

from django.shortcuts import render, get_object_or_404, redirect

def detail_prestation(request, type_unite, prestation_id):

    prestation = None
    offres = []
    offre_selectionnee = None

    # ============================
    # RÉCUPÉRATION DU PRODUIT
    # ============================

    if type_unite == 'FLYER':

        prestation = get_object_or_404(
            SupportFlyer,
            id=prestation_id
        )

        offres = prestation.tarifs_specifiques.all()

    elif type_unite == 'SURFACE':

        prestation = get_object_or_404(
            SupportGrandFormat,
            id=prestation_id
        )

    elif type_unite == 'GOODIES':

        prestation = get_object_or_404(
            SupportObjetPublicitaire,
            id=prestation_id
        )

        offres = prestation.paliers_prix.all()

    elif type_unite == 'FACONNAGE':

        prestation = get_object_or_404(
            ServiceFaconnage,
            id=prestation_id
        )

    else:
        return redirect('/impression/prestations/')


    # ============================
    # OFFRE FLYER PRÉSÉLECTIONNÉE
    # ============================

    if type_unite == 'FLYER':

        offre_id = request.GET.get('offre_id')

        if offre_id:
            offre_selectionnee = prestation.tarifs_specifiques.filter(
                id=offre_id
            ).first()


    # ============================
    # TRAITEMENT DU FORMULAIRE
    # ============================

    if request.method == 'POST':

        type_demande = request.POST.get(
            'type_demande',
            ''
        )


        # ==================================================
        # COMMANDE FLYER
        # ==================================================

        if type_unite == 'FLYER' and type_demande == 'commande_flyer':

            offre_id = request.POST.get('offre_id')

            if not offre_id:
                return redirect(
                    request.path + '?erreur=offre'
                )

            offre = prestation.tarifs_specifiques.filter(
                id=offre_id
            ).first()

            if not offre:
                return redirect(
                    request.path + '?erreur=offre'
                )


            # Prix brut du lot
            prix_brut = float(offre.prix_total_lot)


            # Remise
            remise = prestation.remise_globale or 0

            montant_remise = int(
                prix_brut * (remise / 100)
            )


            # Prix final
            prix_final = prix_brut - montant_remise


            demande = {

                'type_unite': 'FLYER',

                'prestation_id': prestation.id,

                'titre': prestation.titre,

                'offre_id': offre.id,

                'format': offre.format_papier,

                'quantite': offre.quantite,

                'prix_brut': prix_brut,

                'remise_pourcent': remise,

                'montant_remise': montant_remise,

                'prix_final': prix_final,

                'message': request.POST.get(
                    'demande_personnalisee',
                    ''
                ),

                'type_demande': 'commande_flyer',
            }


            request.session['demande_prestation'] = demande

            request.session.modified = True


            return redirect('resume_demande')


        # ==================================================
        # DEMANDE DE DEVIS FLYER PERSONNALISÉ
        # ==================================================

        if type_unite == 'FLYER' and type_demande == 'devis':

            demande = {

                'type_unite': 'FLYER',

                'prestation_id': prestation.id,

                'titre': prestation.titre,

                'format': request.POST.get(
                    'format_personnalise',
                    ''
                ),

                'quantite': request.POST.get(
                    'quantite_personnalisee'
                ),

                'prix_brut': 0,

                'remise_pourcent': 0,

                'montant_remise': 0,

                'prix_final': 0,

                'message': request.POST.get(
                    'demande_personnalisee',
                    ''
                ),

                'type_demande': 'devis',
            }


            request.session['demande_prestation'] = demande

            request.session.modified = True


            return redirect('resume_demande')


        # ==================================================
        # GRAND FORMAT
        # ==================================================

        if type_unite == 'SURFACE' and type_demande == 'commande_surface':

            largeur = request.POST.get('largeur')
            longueur = request.POST.get('longueur')

            try:

                largeur_float = float(largeur)
                longueur_float = float(longueur)

                calcul = prestation.calculer_prix(
                    largeur_float,
                    longueur_float
                )

            except (TypeError, ValueError):

                calcul = {
                    'prix_brut': 0,
                    'remise_pourcent': 0,
                    'montant_remise': 0,
                    'prix_final': 0,
                }


            demande = {

                'type_unite': 'SURFACE',

                'prestation_id': prestation.id,

                'titre': prestation.titre,

                'largeur': largeur,

                'longueur': longueur,

                'prix_brut': calcul['prix_brut'],

                'remise_pourcent': calcul['remise_pourcent'],

                'montant_remise': calcul['montant_remise'],

                'prix_final': calcul['prix_final'],

                'message': request.POST.get(
                    'demande_personnalisee',
                    ''
                ),

                'type_demande': 'commande_surface',
            }


            request.session['demande_prestation'] = demande

            request.session.modified = True


            return redirect('resume_demande')


        # ==================================================
        # GOODIES
        # ==================================================

        if type_unite == 'GOODIES' and type_demande == 'commande_goodie':

            quantite = request.POST.get('quantite')

            try:
                quantite_int = int(quantite)
            except (TypeError, ValueError):
                quantite_int = 0


            calcul = prestation.calculer_prix(
                quantite_int
            )


            demande = {

                'type_unite': 'GOODIES',

                'prestation_id': prestation.id,

                'titre': prestation.titre,

                'quantite': quantite_int,

                'prix_brut': calcul['prix_brut'],

                'remise_pourcent': calcul['remise_pourcent'],

                'montant_remise': calcul['montant_remise'],

                'prix_final': calcul['prix_final'],

                'message': request.POST.get(
                    'demande_personnalisee',
                    ''
                ),

                'type_demande': 'commande_goodie',
            }


            request.session['demande_prestation'] = demande

            request.session.modified = True


            return redirect('resume_demande')


        # ==================================================
        # FAÇONNAGE
        # ==================================================

        if type_unite == 'FACONNAGE' and type_demande == 'commande_faconnage':

            quantite = request.POST.get('quantite')

            try:
                quantite_int = int(quantite)
            except (TypeError, ValueError):
                quantite_int = 0


            calcul = prestation.calculer_prix(
                quantite_int
            )


            demande = {

                'type_unite': 'FACONNAGE',

                'prestation_id': prestation.id,

                'titre': prestation.titre,

                'quantite': quantite_int,

                'prix_brut': calcul['prix_brut'],

                'remise_pourcent': calcul['remise_pourcent'],

                'montant_remise': calcul['montant_remise'],

                'prix_final': calcul['prix_final'],

                'message': request.POST.get(
                    'demande_personnalisee',
                    ''
                ),

                'type_demande': 'commande_faconnage',
            }


            request.session['demande_prestation'] = demande

            request.session.modified = True


            return redirect('resume_demande')


    # ============================
    # AFFICHAGE NORMAL
    # ============================

    context = {

        'prestation': prestation,

        'type_unite': type_unite,

        'offres': offres,

        'formats_disponibles': offres,

        'offre_selectionnee': offre_selectionnee,

    }


    return render(
        request,
        'shop/detail_prestation.html',
        context
    )


from .models import (
    Realisation,
    Temoignage,
    SupportFlyer,
    SupportGrandFormat,
    SupportObjetPublicitaire,
    ServiceFaconnage,
    TarifOptionFlyer,
)
from django.shortcuts import render, redirect

from .models import (
    SupportFlyer,
    SupportGrandFormat,
    SupportObjetPublicitaire,
    ServiceFaconnage,
    TarifOptionFlyer,
    Realisation,
    Temoignage,
)

from .forms import TemoignageForm


def page_public_prestations(request):
    """
    Page publique de l'atelier d'impression.

    Gère :
    - les catégories
    - les prestations
    - les tarifs
    - les réalisations
    - les témoignages clients
    - l'envoi de nouveaux témoignages
    """

    flyers = SupportFlyer.objects.all()

    grands_formats = SupportGrandFormat.objects.all()

    goodies = SupportObjetPublicitaire.objects.all()

    faconnages = ServiceFaconnage.objects.all()

    # ==========================================
    # RÉALISATIONS
    # ==========================================

    # ==========================================
# RÉALISATIONS
# ==========================================

    realisations = (
    Realisation.objects
    .all()
    .order_by('-date_ajout')
)

    # ==========================================
    # AVIS CLIENTS VALIDÉS
    # ==========================================

    temoignages = (
        Temoignage.objects
        .filter(est_approuve=True)
        .order_by('-date_publication')
    )

    # ==========================================
    # FORMULAIRE AVIS
    # ==========================================

    if request.method == "POST":

        form_temoignage = TemoignageForm(request.POST)

        if form_temoignage.is_valid():

            temoignage = form_temoignage.save(
                commit=False
            )

            # Toujours attendre la validation
            # avant d'afficher l'avis publiquement.
            temoignage.est_approuve = False

            temoignage.save()

            return redirect(
                request.path + "?temoignage=envoye#temoignage"
            )

    else:

        form_temoignage = TemoignageForm()

    # ==========================================
    # MESSAGE APRÈS ENVOI
    # ==========================================

    temoignage_envoye = (
        request.GET.get("temoignage") == "envoye"
    )

    # ==========================================
    # PARAMÈTRES
    # ==========================================

    type_unite = request.GET.get(
        'type_unite'
    )

    prestation_id = request.GET.get(
        'prestation_id'
    )

    prestations_a_afficher = []

    tarifs_a_afficher = []

    prestation_selectionnee = None

    formats_disponibles = []

    nom_categorie_active = ""

    # ==========================================
    # CATÉGORIES
    # ==========================================

    if type_unite:

        if type_unite == 'FLYER':

            nom_categorie_active = (
                "Flyers, Dépliants & Cartes"
            )

            tarifs_a_afficher = (
                TarifOptionFlyer.objects
                .all()
                .select_related('flyer')
            )

        elif type_unite == 'SURFACE':

            nom_categorie_active = (
                "Grands Formats (Bâches, Vinyles)"
            )

            tarifs_a_afficher = grands_formats

        elif type_unite == 'GOODIES':

            nom_categorie_active = (
                "Objets Publicitaires"
            )

            tarifs_a_afficher = goodies

        elif type_unite == 'FACONNAGE':

            nom_categorie_active = (
                "Façonnage & Reprographie"
            )

            tarifs_a_afficher = faconnages

    # ==========================================
    # PRESTATION SÉLECTIONNÉE
    # ==========================================

    if prestation_id:

        if type_unite == 'FLYER':

            prestation_selectionnee = (
                SupportFlyer.objects
                .filter(id=prestation_id)
                .first()
            )

            if prestation_selectionnee:

                formats_disponibles = (
                    prestation_selectionnee
                    .tarifs_specifiques
                    .all()
                )

        elif type_unite == 'SURFACE':

            prestation_selectionnee = (
                SupportGrandFormat.objects
                .filter(id=prestation_id)
                .first()
            )

            if prestation_selectionnee:

                formats_disponibles = [
                    prestation_selectionnee
                ]

    # ==========================================
    # CONTEXT
    # ==========================================

    context = {

        'flyers':
            flyers,

        'grands_formats':
            grands_formats,

        'goodies':
            goodies,

        'faconnages':
            faconnages,

        'type_unite_clique':
            type_unite,

        'tarifs_a_afficher':
            tarifs_a_afficher,

        'prestation_selectionnee':
            prestation_selectionnee,

        'formats_disponibles':
            formats_disponibles,

        'nom_categorie_active':
            nom_categorie_active,

        # Réalisations
        'realisations':
            realisations,

        # Avis validés uniquement
        'temoignages':
            temoignages,

        # Formulaire
        'form_temoignage':
            form_temoignage,

        # Message de confirmation
        'temoignage_envoye':
            temoignage_envoye,
    }

    return render(
        request,
        'shop/atelier_client.html',
        context
    )


def resume_demande(request):

    demande = request.session.get('demande_prestation')

    if not demande:
        return redirect('/impression/prestations/')

    type_unite = demande.get('type_unite')
    prestation_id = demande.get('prestation_id')

    prestation = None

    prix_brut = 0
    remise_pourcent = 0
    montant_remise = 0
    net_a_payer = 0
    sur_devis = False

    # =====================================================
    # 1. FLYERS
    # =====================================================

    if type_unite == 'FLYER':

        prestation = get_object_or_404(
            SupportFlyer,
            id=prestation_id
        )

        if demande.get('offre_id'):

            offre = get_object_or_404(
                TarifOptionFlyer,
                id=demande['offre_id']
            )

            prix_brut = float(offre.prix_total_lot)

        else:
            sur_devis = True

        remise_pourcent = prestation.remise_globale


    # =====================================================
    # 2. GRAND FORMAT
    # =====================================================

    elif type_unite == 'SURFACE':

        prestation = get_object_or_404(
            SupportGrandFormat,
            id=prestation_id
        )

        largeur = demande.get('largeur')
        longueur = demande.get('longueur')

        if largeur and longueur:

            largeur = float(largeur)
            longueur = float(longueur)

            surface = largeur * longueur

            prix_brut = (
                surface *
                float(prestation.prix_au_metre_carre)
            )

            remise_pourcent = prestation.remise_globale

            # On garde la surface dans la demande
            demande['surface'] = surface

        else:
            sur_devis = True


    # =====================================================
    # 3. GOODIES
    # =====================================================

    elif type_unite == 'GOODIES':

        prestation = get_object_or_404(
            SupportObjetPublicitaire,
            id=prestation_id
        )

        quantite = demande.get('quantite')

        if quantite:

            quantite = int(quantite)

            palier = (
                prestation.paliers_prix
                .filter(
                    quantite_minimale__lte=quantite
                )
                .order_by('-quantite_minimale')
                .first()
            )

            if palier:

                prix_brut = (
                    float(palier.prix_unitaire)
                    * quantite
                )

            else:
                sur_devis = True

            remise_pourcent = prestation.remise_globale

        else:
            sur_devis = True


    # =====================================================
    # 4. FAÇONNAGE
    # =====================================================

    elif type_unite == 'FACONNAGE':

        prestation = get_object_or_404(
            ServiceFaconnage,
            id=prestation_id
        )

        quantite = demande.get('quantite')

        if quantite:

            quantite = int(quantite)

            prix_brut = (
                quantite *
                float(prestation.prix_fixe_unitaire)
            )

            remise_pourcent = prestation.remise_globale

        else:
            sur_devis = True


    # =====================================================
    # 5. CALCUL DE LA REMISE
    # =====================================================

    if not sur_devis:

        montant_remise = int(
            prix_brut *
            (remise_pourcent / 100)
        )

        net_a_payer = (
            prix_brut -
            montant_remise
        )


    # =====================================================
    # 6. MISE À JOUR DE LA SESSION
    # =====================================================

    request.session['demande_prestation'] = demande


    # =====================================================
    # 7. CONFIRMATION DE LA COMMANDE
    # =====================================================
    # IMPORTANT :
    # Ce bloc vient APRÈS les calculs ci-dessus.

    if (
        request.method == 'POST'
        and request.POST.get('confirmer') == '1'
    ):

        commande_confirmee = {
            **demande,

            'titre': prestation.titre
                if prestation else '',

            'prix_brut': prix_brut,

            'remise_pourcent': remise_pourcent,

            'montant_remise': montant_remise,

            'net_a_payer': net_a_payer,

            'sur_devis': sur_devis,
        }

        request.session['commande_confirmee'] = (
            commande_confirmee
        )

        request.session.modified = True

        return redirect('confirmation_commande')


    # =====================================================
    # 8. AFFICHAGE DU RÉCAPITULATIF
    # =====================================================

    context = {

        'demande': demande,

        'prestation': prestation,

        'prix_brut': prix_brut,

        'remise_pourcent': remise_pourcent,

        'montant_remise': montant_remise,

        'net_a_payer': net_a_payer,

        'sur_devis': sur_devis,
    }

    return render(
        request,
        'shop/resume_demande.html',
        context
    )



def confirmation_commande(request):

    commande = request.session.get(
        'commande_confirmee'
    )

    if not commande:
        return redirect('/impression/prestations/')

    return render(
        request,
        'shop/confirmation_commande.html',
        {
            'commande': commande
        }
    )

def calculer_tarif_ajax(request, prestation_id):
    prestation = get_object_or_404(Prestation, id=prestation_id)
    
    # Récupération sécurisée des données envoyées par le JavaScript
    try:
        quantite = int(request.GET.get('quantite', 1))
    except ValueError:
        quantite = 1
        
    format_id = request.GET.get('format_id') or None
    surface_id = request.GET.get('surface_id') or None
    
    try:
        nb_pages = int(request.GET.get('nb_pages')) if request.GET.get('nb_pages') else None
    except ValueError:
        nb_pages = None

    # Exécution du calcul centralisé du modèle
    resultat = prestation.calculer_prix(
        quantite=quantite,
        format_id=format_id,
        surface_id=surface_id,
        nb_pages=nb_pages
    )

    return JsonResponse(resultat)


import json
import re
import urllib.parse
from django.shortcuts import render, get_object_or_404, redirect
from .models import  CommandeImpression

def confirmer_commande_client(request):
    """ ÉTAPE Final : Formulaire de coordonnées, insertion BDD et routage WhatsApp """
    
    # 1. Récupération de la session temporaire initialisée à l'étape précédente
    commande_session = request.session.get('commande_temporaire')
    
    # 2. Sécurité anti-page blanche : si aucune session, retour à la liste des prestations
    if not commande_session:
        return redirect('page_prestations')

    # Récupération de l'objet prestation courant
    prestation = get_object_or_404(Prestation, id=commande_session['prestation_id'])

    # 3. SÉCURISATION DE LA TRANSMISSION DU FORMULAIRE DE COORDONNÉES CLIENT
    if request.method == "POST" and 'nom_client' in request.POST:
        nom = request.POST.get('nom_client', '').strip()
        tel = request.POST.get('telephone_client', '').strip()
        email = request.POST.get('email_client', 'client@yatout.ci').strip()
        
        # Structuration de la ligne pour l'historique JSON en base de données
        structure_tableau_json = [commande_session['item_panier']]

        try:
            # Enregistrement propre dans la table CommandeImpression
            commande = CommandeImpression.objects.create(
                nom_client=nom,
                email_client=email,
                telephone=tel,
                details_json=json.dumps(structure_tableau_json, ensure_ascii=False),
                total_brut=commande_session['total_brut'],
                montant_remise=commande_session['montant_remise'],
                total_final=commande_session['total_final'],
                statut='EN_ATTENTE'
            )
            
            # 🟢 CORRECTION INDISPENSABLE : Appel de la vraie méthode de votre modèle
            numero_bon = commande.numero_bon_commande()
            
            # Extraction directe du texte de remise sauvegardé à l'étape 1
            texte_remise = commande_session.get('remise_texte_whatsapp', 'Aucune')

            # 4. CONSTRUCTION ET ENCODAGE DU MESSAGE DESTINATION WHATSAPP
            message_brut = (
                f"🛍️ *NOUVELLE COMMANDE - YATOUT*\n\n"
                f"📦 *Bon N° :* #{numero_bon}\n"
                f"👤 *Client :* {nom}\n"
                f"📞 *Contact :* {tel}\n"
                f"🎯 *Impression :* {commande_session['prestation_titre']}\n"
                f"📏 *Spécifications :* {commande_session['unite_texte']}\n"
                f"🎁 *Remise appliquée :* {texte_remise}\n\n"
                f"💵 *Net à payer :* *{commande_session['total_final_formate']} FCFA*\n\n"
                f"Bonjour YaTout, je viens de vérifier mon récapitulatif et je confirme ma commande !"
            )

            texte_url = urllib.parse.quote(message_brut)
            numero_entreprise = "2250574702092"
            lien_whatsapp_final = f"https://api.whatsapp.com/send?phone={numero_entreprise}&text={texte_url}"
            
            # Préparation des variables formatées pour l'affichage immédiat du template
            commande.total_brut_formate = f"{int(commande.total_brut):,}".replace(',', '.')
            commande.montant_remise_formate = f"{int(commande.montant_remise):,}".replace(',', '.')
            commande.total_final_formate = f"{int(commande.total_final):,}".replace(',', '.')

            # Nettoyage de la session de commande temporaire après succès
            if 'commande_temporaire' in request.session:
                del request.session['commande_temporaire']
            
            # 🟢 RENDU : Affichage direct de l'écran avec le bouton WhatsApp vert opérationnel
            return render(request, 'shop/bon_impression_pret.html', {
                'commande': commande,
                'articles_liste': structure_tableau_json,  # Requis pour boucler sur les produits dans le HTML
                'lien_whatsapp': lien_whatsapp_final,
                'prestation': prestation
            })
            
        except Exception as e:
            # Affiche l'erreur réelle dans votre console système en cas d'autre problème de BDD
            print(f"Erreur création commande : {e}")
            return redirect('page_prestations')

    # Affichage normal du formulaire de saisie des coordonnées (Nom, Prénom, Téléphone)
    return render(request, 'shop/validation_coordonnees.html', {
        'commande_session': commande_session,
        'prestation': prestation
    })


import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from .models import CommandeImpression

import json
import urllib.parse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def voir_bon_commande(request, commande_id):
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    articles_liste = json.loads(commande.details_json)
    
    # 1. Préparation initiale des variables entières et formatées pour l'affichage (GET)
    for art in articles_liste:
        quantite_securisee = int(art.get('qte', art.get('quantite', 1)))
        prix_unitaire = int(float(art.get('prix', 0)))
        brut_ligne = quantite_securisee * prix_unitaire
        
        # Lecture du pourcentage de remise stocké (ex: 5)
        taux_remise = int(float(art.get('remise_pourcent', 0)))
        montant_remise_ligne = round(brut_ligne * (taux_remise / 100.0))
        total_net_ligne = max(0, brut_ligne - montant_remise_ligne)
        
        # Clés lues par le template HTML du Bon de Commande avec séparateur par points
        art['qte_entier'] = quantite_securisee
        art['prix_entier'] = f"{prix_unitaire:,}".replace(',', '.')
        art['remise_pourcent_entier'] = f"{taux_remise} %" if taux_remise > 0 else "0 %"
        art['total_net_entier'] = f"{total_net_ligne:,}".replace(',', '.')

    # Récupération et formatage des totaux généraux pour le bloc du bas
    commande.total_brut_formate = f"{int(commande.total_brut):,}".replace(',', '.')
    commande.montant_remise_formate = f"{int(commande.montant_remise):,}".replace(',', '.')
    commande.total_final_formate = f"{int(commande.total_final):,}".replace(',', '.')
    
    # Conservation des entiers bruts pour les fallbacks de calculs
    commande.total_brut_entier = int(commande.total_brut)
    commande.montant_remise_global_entier = int(commande.montant_remise)
    commande.total_final_entier = int(commande.total_final)
    commande.montant_remise_global = int(commande.montant_remise)

    # Récupération ou initialisation du pourcentage de remise globale actuel
    pourcentage_actuel = int((commande.montant_remise / commande.total_brut) * 100) if commande.total_brut > 0 else 0

    if request.method == "POST":
        # ACTION 1 : MISE A JOUR DES REMISES PAR ARTICLE INDIVIDUEL
        if 'appliquer_remises_articles' in request.POST:
            nouveau_total_brut_global = 0
            total_remise_cumulee = 0
            
            for index, art in enumerate(articles_liste):
                cle_remise = f"remise_{index}"
                taux_remise = int(float(request.POST.get(cle_remise, 0)))
                
                quantite_securisee = int(art.get('qte', art.get('quantite', 1)))
                prix_unitaire = int(float(art.get('prix', 0)))
                total_brut_ligne = quantite_securisee * prix_unitaire
                
                montant_reduction_ligne = round(total_brut_ligne * (taux_remise / 100.0))
                total_net_ligne = max(0, total_brut_ligne - montant_reduction_ligne)
                
                art['remise_pourcent'] = taux_remise
                art['remise'] = montant_reduction_ligne
                art['total'] = total_net_ligne
                
                nouveau_total_brut_global += total_brut_ligne
                total_remise_cumulee += montant_reduction_ligne
            
            commande.details_json = json.dumps(articles_liste)
            commande.total_brut = int(nouveau_total_brut_global)
            commande.montant_remise = int(total_remise_cumulee)
            commande.total_final = int(nouveau_total_brut_global - total_remise_cumulee)
            commande.save()
            
            messages.success(request, "Les remises par article ont été appliquées avec succès !")
            return redirect('voir_bon_commande', commande_id=commande.id)

        # ACTION 2 : REPERCUTER LA REMISE GLOBALE SUR CHAQUE ARTICLE
        elif 'changer_remise' in request.POST:
            nouvelle_remise_pourcent = int(float(request.POST.get('pourcentage_remise', request.POST.get('remise_globale', 5))))
            
            nouveau_total_brut_global = 0
            total_remise_cumulee = 0
            
            for art in articles_liste:
                quantite_securisee = int(art.get('qte', art.get('quantite', 1)))
                prix_unitaire = int(float(art.get('prix', 0)))
                total_brut_ligne = quantite_securisee * prix_unitaire
                
                montant_reduction_ligne = round(total_brut_ligne * (nouvelle_remise_pourcent / 100.0))
                total_net_ligne = max(0, total_brut_ligne - montant_reduction_ligne)
                
                art['remise_pourcent'] = nouvelle_remise_pourcent
                art['remise'] = montant_reduction_ligne
                art['total'] = total_net_ligne
                
                nouveau_total_brut_global += total_brut_ligne
                total_remise_cumulee += montant_reduction_ligne
            
            commande.details_json = json.dumps(articles_liste)
            commande.total_brut = int(nouveau_total_brut_global)
            commande.montant_remise = int(total_remise_cumulee)
            commande.total_final = int(nouveau_total_brut_global - total_remise_cumulee)
            commande.save()
            
            messages.success(request, f"Remise globale de {nouvelle_remise_pourcent}% appliquée à l'ensemble des articles !")
            return redirect('voir_bon_commande', commande_id=commande.id)
            
        # ACTION 3 : GENERATION DU BON DE LIVRAISON + ENVOI MAIL
        elif 'generer_bl' in request.POST:
            commande.bl_genere = True
            commande.statut = 'VALIDE'
            commande.save()
            
            sujet = f"✅ Votre bon d'impression #{commande.numero_bon_commande()} a été validé !"
            message = (
                f"Bonjour {commande.nom_client},\n\n"
                f"Bonne nouvelle ! L'administrateur de YaTout vient de valider votre bon de commande.\n\n"
                f"Nous lançons la fabrication de vos impressions. Nous vous contacterons très vite au "
                f"{commande.telephone} dès que vos supports seront prêts pour la livraison.\n\n"
                f"YaTout Impression — Votre image mérite la perfection.\n" # 🟢 AJOUT : Votre nouveau slogan officiel
                f"Merci pour votre confiance !"
            )
            try:
                send_mail(sujet, message, 'noreply@yatout.com', [commande.email_client], fail_silently=True)
            except Exception:
                pass

            messages.success(request, "Bon de Livraison généré et validé avec succès ! 🎉")
            return redirect(f"/impression/bon-livraison/{commande.id}/")

    return render(request, 'shop/bon_commande.html', {
        'commande': commande,
        'articles_liste': articles_liste,
        'pourcentage_actuel': pourcentage_actuel
    })

def voir_bon_livraison(request, commande_id):
    """ Génère la page du Bon de Livraison officiel sans centimes """
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    articles_liste = json.loads(commande.details_json)
    
    # Injection des données entières formatées pour le template du BL avec séparateur par points
    for art in articles_liste:
        # 🔑 SÉCURITÉ CRITIQUE : Si l'élément est une chaîne de caractères, on la convertit en dictionnaire
        if isinstance(art, str):
            try:
                art = json.loads(art)
            except json.JSONDecodeError:
                art = {}

        quantite_securisee = int(art.get('qte', art.get('quantite', 1)))
        prix_unitaire = int(float(art.get('prix', 0)))
        brut_ligne = quantite_securisee * prix_unitaire
        
        taux_remise = int(float(art.get('remise_pourcent', 0)))
        montant_remise_ligne = round(brut_ligne * (taux_remise / 100.0))
        total_net_ligne = max(0, brut_ligne - montant_remise_ligne)
        
        # Clés lues par le template HTML du Bon de Livraison
        art['qte_entier'] = quantite_securisee
        art['prix_entier'] = f"{prix_unitaire:,}".replace(',', '.')
        art['remise_pourcent_entier'] = f"{taux_remise} %" if taux_remise > 0 else "0 %"
        art['total_net_entier'] = f"{total_net_ligne:,}".replace(',', '.')
    
    # Données du bloc récapitulatif formatées pour le bas de page du BL
    commande.total_brut_formate = f"{int(commande.total_brut):,}".replace(',', '.')
    commande.montant_remise_formate = f"{int(commande.montant_remise):,}".replace(',', '.')
    commande.total_final_formate = f"{int(commande.total_final):,}".replace(',', '.')

    # Fallbacks entiers au cas où
    commande.total_brut_entier = int(commande.total_brut)
    commande.montant_remise_global_entier = int(commande.montant_remise)
    commande.total_final_entier = int(commande.total_final)
    commande.montant_remise_global = int(commande.montant_remise)
    
    return render(request, 'shop/bon_livraison.html', {
        'commande': commande,
        'articles_liste': articles_liste
    })

def voir_bon_commande_public(request, commande_id):
    """ 
    Permet au client de visualiser son bon public en permanence SANS CONNEXION.
    Génère le lien WhatsApp dynamiquement depuis la BDD (zéro crash).
    """
    # 🛡️ Récupération publique de la commande
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    articles_liste = json.loads(commande.details_json)
    
    # 1. Traitement et formatage de chaque ligne d'article
    for art in articles_liste:
        type_unite = art.get('type_unite', '')
        qte_brute = art.get('qte', art.get('quantite', 1))
        prix_unitaire = int(float(art.get('prix', 0)))
        
        if type_unite == 'M2' and art.get('longueur') and art.get('largeur'):
            qte_valeur = float(qte_brute)
            brut_ligne = int(qte_valeur * prix_unitaire)
            art['qte_formatee'] = f"{qte_valeur:.1f}" if qte_valeur.is_integer() else f"{qte_valeur:.2f}"
        else:
            qte_valeur = int(float(qte_brute))
            brut_ligne = qte_valeur * prix_unitaire
            art['qte_formatee'] = qte_valeur

        taux_remise = int(float(art.get('remise_pourcent', 0)))
        if taux_remise == 0 and int(art.get('remise', 0)) > 0:
            taux_remise = int(round((int(art.get('remise', 0)) / brut_ligne) * 100))
            
        montant_remise_ligne = round(brut_ligne * (taux_remise / 100.0))
        total_net_ligne = max(0, brut_ligne - montant_remise_ligne)
        
        art['prix_formate'] = f"{prix_unitaire:,}".replace(',', '.')
        art['remise_formatee'] = f"{taux_remise} %" if taux_remise > 0 else "0 %"
        art['total_formate'] = f"{total_net_ligne:,}".replace(',', '.')

    # 2. Injection du formatage par points pour les totaux globaux
    commande.total_brut_formate = f"{int(commande.total_brut):,}".replace(',', '.')
    commande.montant_remise_formate = f"{int(commande.montant_remise):,}".replace(',', '.')
    commande.total_final_formate = f"{int(commande.total_final):,}".replace(',', '.')

    # 🚀 3. RECONSTRUCTION DYNAMIQUE DU TEXTE WHATSAPP
    message_brut = (
        f"🛍️ *MON BON DE COMMANDE - YATOUT*\n\n"
        f"📦 *Bon N° :* #{commande.numero_bon_commande()}\n"
        f"👤 *Client :* {commande.nom_client}\n"
        f"📞 *Contact :* {commande.telephone}\n"
        f"-----------------------------------\n"
    )
    
    for art in articles_liste:
        message_brut += f"▪️ {art.get('titre', 'Impression')} (x{art.get('qte_formatee')}) : {art.get('total_formate')} FCFA\n"
        
    message_brut += (
        f"-----------------------------------\n"
        f"💵 *Net à payer :* *{commande.total_final_formate} FCFA*\n\n"
        f"Bonjour YaTout, je viens de vérifier mon récapitulatif public et je confirme ma commande !"
    )

    # 🟢 FIX URL WHATSAPP : Utilisation du format officiel universel wa.me ou API avec le point d'interrogation
    texte_url = urllib.parse.quote(message_brut)
    numero_entreprise = "2250574702092"
    # Votre ancienne URL manquait d'un "?" ou utilisait un mauvais chemin, voici l'officielle :
    lien_whatsapp = f"https://api.whatsapp.com/send?phone={numero_entreprise}&text={texte_url}"

    # 4. Traitement optionnel si le client valide un bouton sur la page
    if request.method == 'POST' and 'confirmer_client' in request.POST:
        commande.validee_par_client = True
        commande.save()
        return redirect(lien_whatsapp)

    # 5. RENDU : Chargement du gabarit
    return render(request, 'shop/bon_impression_pret.html', {
        'commande': commande,
        'articles_liste': articles_liste,
        'lien_whatsapp': lien_whatsapp,
    })


def verifier_code_admin(request):
    """ Vérifie le code d'accès administrateur à 6 chiffres (191953) et renvoie les commandes en AJAX """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code_saisi = data.get('code')
            
            if code_saisi == "191953": 
                commandes_qs = CommandeImpression.objects.all().order_by('-id')
                liste_commandes = []
                
                for cmd in commandes_qs:
                    liste_commandes.append({
                        'id': cmd.id,
                        'nom_client': cmd.nom_client,
                        'telephone': cmd.telephone,
                        'total_brut': cmd.total_brut,
                        'statut': cmd.statut,
                    })
                return JsonResponse({'autorise': True, 'commandes': liste_commandes})
        except Exception:
            pass
            
    return JsonResponse({'autorise': False}, status=403)



def voir_atelier(request):
    """ Gère l'affichage complet de l'atelier, le panier en session et le simulateur """
    prestations = Prestation.objects.all()
    
    # 1. Récupération des réalisations pour le carrousel d'images
    exemples_realisations = Realisation.objects.all().order_by('-date_ajout')[:5]
    
    # 2. Gestion du Panier stocké dans la Session Django
    if 'panier_impression' not in request.session:
        request.session['panier_impression'] = {}
    
    panier = request.session['panier_impression']
    
    # 3. Traitement du formulaire classique si le bouton vert de validation finale est cliqué
    if request.method == "POST" and 'nom_client' in request.POST:
        # Code existant de création définitive du Bon de Commande...
        pass

    # 4. Reconstitution de la liste visuelle et calculs dynamiques
    panier_visuel = []
    total_brut = 0
    
    for prest_id, quantite in panier.items():
        try:
            prestation = Prestation.objects.get(id=int(prest_id))
            total_ligne = prestation.prix_unitaire * int(quantite)
            total_brut += total_ligne
            
            panier_visuel.append({
                'prestation': prestation,
                'quantite': quantite,
                'total_ligne': total_ligne
            })
        except Prestation.DoesNotExist:
            continue
            
    # Calculs financiers de la remise commerciale
    remise_panier = int(total_brut * 0.05)
    total_final = total_brut - remise_panier

    return render(request, 'shop/page_impression.html', {
        'prestations': prestations,
        'exemples_realisations': exemples_realisations, # Envoi des photos à la galerie
        'panier_visuel': panier_visuel,
        'total_brut': total_brut,
        'remise_panier': remise_panier,
        'total_final': total_final,
    })


# 5. 🟢 L'API JAVASCRIPT QUE VOS BOUTONS APPELENT EN ARRIÈRE-PLAN
@csrf_exempt
def action_panier_api(request):
    """ Reçoit les clics JS (ajouter, modifier, supprimer) et met à jour la session """
    if request.method == "POST":
        data = json.loads(request.body)
        prest_id = str(data.get('prestation_id'))
        action = data.get('action')
        qte = int(data.get('quantite', 1))
        
        if 'panier_impression' not in request.session:
            request.session['panier_impression'] = {}
        panier = request.session['panier_impression']
        
        if action == 'ajouter':
            panier[prest_id] = panier.get(prest_id, 0) + 1
        elif action == 'modifier':
            if qte > 0:
                panier[prest_id] = qte
        elif action == 'supprimer':
            if prest_id in panier:
                del panier[prest_id]
                
        request.session['panier_impression'] = panier
        request.session.modified = True
        return JsonResponse({'status': 'success'})
        
    return JsonResponse({'status': 'error'}, status=400)

from django.http import JsonResponse
import json
from .models import CommandeImpression

def verifier_code_admin(request):
    """ Vérifie le code admin et renvoie la liste des commandes avec sécurité totale """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code_saisi = data.get('code')
            
            if code_saisi == "191953": 
                commandes_qs = CommandeImpression.objects.all().order_by('-id')
                liste_commandes = []
                
                for cmd in commandes_qs:
                    # 💡 Sécurité absolue : on utilise getattr() pour éviter les plantages si un champ est mal nommé
                    cmd_id = getattr(cmd, 'id', 0)
                    nom = getattr(cmd, 'nom_client', 'Client Inconnu')
                    tel = getattr(cmd, 'telephone', 'Aucun contact')
                    statut = getattr(cmd, 'statut', 'EN_ATTENTE')
                    
                    # On teste si total_brut existe, sinon on se rabat sur total_final ou 0
                    total = getattr(cmd, 'total_brut', getattr(cmd, 'total_final', 0))
                    
                    liste_commandes.append({
                        'id': cmd_id,
                        'nom_client': nom,
                        'telephone': tel,
                        'total_brut': int(total) if total else 0,
                        'statut': statut,
                    })
                
                return JsonResponse({'autorise': True, 'commandes': liste_commandes})
            else:
                return JsonResponse({'autorise': False, 'message': 'Code incorrect'})
        except Exception as e:
            # Si un plantage survient malgré tout, on renvoie l'erreur au JavaScript pour la lire à l'écran
            return JsonResponse({'autorise': False, 'error': str(e)}, status=500)
            
    return JsonResponse({'autorise': False}, status=403)


from django.contrib.auth.decorators import user_passes_test
from .models import Devis
from django.contrib import messages

# Sécurité : Seul le staff / superutilisateur a le droit d'entrer ici
def est_administrateur(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)
@user_passes_test(est_administrateur, login_url='connexion')
def espace_devis_dashboard(request):
    """Affiche la liste complète de tous les devis"""
    devis_list = Devis.objects.all()
    return render(request, 'shop/admin_devis_dashboard.html', {
        'devis_list': devis_list, 
        'prestation': True
    })




import io
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from reportlab.pdfgen import canvas
from .models import Devis # Ajustez 'Prestation' selon votre modèle réel

# =====================================================================
# 🔐 SÉCURITÉ ACCÈS ADMINISTRATEUR
# =====================================================================
def est_administrateur(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# =====================================================================
from django.db.models import Sum
from django.utils import timezone
from .models import Facture, Devis # S'assurer que Facture est importé ici
@user_passes_test(est_administrateur, login_url='connexion')
def espace_devis_dashboard(request):
    """Affiche les devis, les statistiques du mois et l'historique complet des paiements."""
    aujourdhui = timezone.now()
    factures_du_mois = Facture.objects.filter(
        date_paiement__year=aujourdhui.year,
        date_paiement__month=aujourdhui.month
    )
    
    total_du_mois = factures_du_mois.aggregate(Sum('montant_recu'))['montant_recu__sum'] or 0
    nombre_transactions = factures_du_mois.count()

    # 1. Liste des devis (votre code existant)
    devis_list = Devis.objects.all().order_by('-id')
    
    # 2. 📋 NOUVEAU : Historique de TOUS les paiements (sans limite de mois)
    historique_paiements = Facture.objects.all().order_by('-date_paiement')
    
    return render(request, 'shop/admin_devis_dashboard.html', {
        'devis_list': devis_list, 
        'historique_paiements': historique_paiements, # 👈 Transmis au HTML
        'prestation': True,
        'total_du_mois': total_du_mois,          
        'nombre_transactions': nombre_transactions,  
        'mois_actuel': aujourdhui.strftime("%B %Y")
    })



@user_passes_test(est_administrateur, login_url='connexion')
def creer_ou_modifier_devis(request, devis_id=None):
    """Formulaire pour créer, modifier ou supprimer un devis avec double sécurité"""
    devis = get_object_or_404(Devis, id=devis_id) if devis_id else None
    toutes_les_prestations = Prestation.objects.all()
    code_attendu = getattr(settings, 'SECRET_ADMIN_DELETE_CODE', '1234')

    if request.method == "POST":
        action_type = request.POST.get('action_type')
        code_saisi = request.POST.get('code_admin')
        
        # 🔒 SÉCURITÉ : VERROUILLAGE ÉDITION & SUPPRESSION (Pour Devis Validés ou BL)
        if devis and devis.statut in ['valide', 'converti_bl']:
            # Cas 1 : Tentative de suppression
            if action_type == "supprimer_devis":
                if code_saisi != code_attendu:
                    DevisAuditLog.objects.create(
                        devis_ref=f"#{devis.id}", client=devis.nom_client, montant=devis.montant_total,
                        statut_devis=devis.get_statut_display(), action='TENTATIVE',
                        resultat="Échec suppression : Code secret incorrect.", execute_par=request.user
                    )
                    messages.error(request, "❌ Code administrateur incorrect ! Suppression annulée.")
                    return redirect('espace_devis_dashboard')
                
                # Code correct -> Suppression
                DevisAuditLog.objects.create(
                    devis_ref=f"#{devis.id}", client=devis.nom_client, montant=devis.montant_total,
                    statut_devis=devis.get_statut_display(), action='SUPPRESSION',
                    resultat="Succès : Devis détruit avec code valide.", execute_par=request.user
                )
                devis.delete()
                messages.success(request, f"Le devis #{devis_id} a été supprimé.")
                return redirect('espace_devis_dashboard')
            
            # Cas 2 : Tentative de Modification / Enregistrement
            elif action_type == "sauvegarder":
                if code_saisi != code_attendu:
                    DevisAuditLog.objects.create(
                        devis_ref=f"#{devis.id}", client=devis.nom_client, montant=devis.montant_total,
                        statut_devis=devis.get_statut_display(), action='TENTATIVE',
                        resultat="Échec modification : Tentative d'enregistrement sans code valide.", execute_par=request.user
                    )
                    messages.error(request, "🔒 Ce devis est validé/converti en BL. Code administrateur requis pour modifier !")
                    return redirect(request.path) # Recharge la page actuelle
                
                # Si le code est bon, on l'autorise à continuer vers l'enregistrement ci-dessous
                DevisAuditLog.objects.create(
                    devis_ref=f"#{devis.id}", client=devis.nom_client, montant=devis.montant_total,
                    statut_devis=devis.get_statut_display(), action='MODIFICATION',
                    resultat="Succès : Modification forcée autorisée par code admin.", execute_par=request.user
                )

        # === LOGIQUE STANDARD D'ENREGISTREMENT (CRÉATION OU MODIFICATION VALIDÉE) ===
        nom = request.POST.get('nom_client')
        tel = request.POST.get('telephone')
        email = request.POST.get('email')
        desc = request.POST.get('description_prestation')
        statut = request.POST.get('statut', 'brouillon')
        livre_par = request.POST.get('livre_par', 'Nous-mêmes')
        
        montant_brut = request.POST.get('form-montant') or request.POST.get('montant_total') or '0'
        montant_propre = str(montant_brut).replace('\xa0', '').replace(' ', '').replace(',', '.')
        if 'F' in montant_propre:
            montant_propre = montant_propre.split('F')[0].strip()
            
        try:
            montant_decimal = Decimal(montant_propre)
        except Exception:
            montant_decimal = Decimal('0.00')

        if devis:
            devis.nom_client = nom
            devis.telephone = tel
            devis.email = email
            devis.description_prestation = desc
            devis.montant_total = montant_decimal  
            devis.statut = statut
            devis.livre_par = livre_par  
            devis.save()
            messages.success(request, f"Le devis #{devis.id} a été mis à jour.")
        else:
            devis = Devis.objects.create(
                nom_client=nom, telephone=tel, email=email,
                description_prestation=desc, montant_total=montant_decimal,  
                statut=statut, livre_par=livre_par, cree_par=request.user
            )
            messages.success(request, f"Nouveau devis #{devis.id} créé.")
        
        return redirect('espace_devis_dashboard')

    return render(request, 'shop/admin_form_devis.html', {
        'devis': devis, 
        'prestation': True,
        'liste_prestations': toutes_les_prestations
    })


# =====================================================================
# 🚚 CONVERSION SÉCURISÉE EN BON DE LIVRAISON (BL)
# =====================================================================
@user_passes_test(est_administrateur, login_url='connexion')
def convertir_en_bl(request, devis_id):
    """Bascule le statut du devis et génère un numéro de Bon de Livraison"""
    devis = get_object_or_404(Devis, id=devis_id)
    
    if devis.statut == 'valide':
        devis.statut = 'converti_bl'
        devis.numero_bl = f"BL-{devis.id}-2026"
        devis.save()
        messages.success(request, f"Succès ! Le devis #{devis.id} a été converti en Bon de Livraison ({devis.numero_bl}).")
    else:
        messages.error(request, "Impossible de générer le BL : Le devis doit d'abord être validé par le client.")
        
    return redirect('espace_devis_dashboard')

import io
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.contrib.auth.decorators import user_passes_test
from reportlab.pdfgen import canvas

@user_passes_test(est_administrateur, login_url='connexion')
def telecharger_devis_pdf(request, devis_id):
    """Génère un PDF officiel avec toutes les informations triées sur le bloc de droite"""
    devis = get_object_or_404(Devis, id=devis_id)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=(595, 842)) # Format de page standard A4
    
    # --- EN-TÊTE DE L'ENTREPRISE (YaTout imprim) ---
    p.setFont("Helvetica-Bold", 18)
    p.setFillColorRGB(0.43, 0.16, 0.92) # Violet signature
    p.drawString(50, 760, "YaTout imprim")
    
    p.setFont("Helvetica", 8)
    p.setFillColorRGB(0.3, 0.3, 0.3)
    p.drawString(50, 740, "Le Savant de l'imprimerie")
    p.drawString(50, 725, "Contact : +225 05 74 70 20 92 | Abidjan, Côte d'Ivoire")
    
    # --- DETAILS DU BLOC COMPTABLE ALIGNÉS À DROITE ---
    X_ALIGNE_DROITE = 545 # Limite droite du tableau
    
    # Titre principal
    p.setFont("Helvetica-Bold", 14)
    p.setFillColorRGB(0, 0, 0)
    p.drawRightString(X_ALIGNE_DROITE, 760, "DEVIS")
    
    p.setFont("Helvetica", 9)
    # De: Nom du client
    p.drawRightString(X_ALIGNE_DROITE, 742, f"De: {devis.nom_client}")
    
    # Récupération ou calcul à la volée du numéro séquentiel (ex: 26/Dv07-001)
    if hasattr(devis, 'numero_devis_personnalise') and devis.numero_devis_personnalise:
        num_affiche = devis.numero_devis_personnalise
    else:
      # Solution de secours : réinitialisation automatique du rang à chaque nouveau mois
        annee = devis.date_creation.strftime('%y')
        mois = devis.date_creation.month # Donne 8 pour août au lieu de 08
        
        # On compte les devis créés avant celui-ci dans le même mois et la même année
        devis_du_mois = Devis.objects.filter(
            date_creation__year=devis.date_creation.year,
            date_creation__month=devis.date_creation.month,
            id__lt=devis.id
        ).count()
        
        rang_mensuel = devis_du_mois + 1
        num_affiche = f"{annee}/Dv{mois}-{rang_mensuel:03d}"
        
    p.drawRightString(X_ALIGNE_DROITE, 725, f"n° : {num_affiche}")
    
    # Date d'émission
    p.drawRightString(X_ALIGNE_DROITE, 708, f"Date: {devis.date_creation.strftime('%d/%m/%Y')}")
    
    # Heure d'émission
    p.drawRightString(X_ALIGNE_DROITE, 691, f"Heure: {devis.date_creation.strftime('%H:%M')}")

    # Téléphone du client aligné à droite sous l'heure
    p.drawRightString(X_ALIGNE_DROITE, 674, f"Téléphone : {devis.telephone}")

    # Ligne horizontale de démarcation supérieure abaissée pour inclure le téléphone
    p.setStrokeColorRGB(0.85, 0.85, 0.85)
    p.setLineWidth(1)
    p.line(50, 655, X_ALIGNE_DROITE, 655)

    # =====================================================================
    # STRUCTURATION CALIBRÉE DU TABLEAU DE FACTURATION (y=540)
    # =====================================================================
    y = 540
    hauteur_ligne = 25
    
    # Tracé du rectangle gris d'en-tête de tableau
    p.setFillColorRGB(0.95, 0.95, 0.96)
    p.rect(50, y, 495, hauteur_ligne, fill=True, stroke=False)
    
    # Titres des colonnes
    p.setFont("Helvetica-Bold", 9)
    p.setFillColorRGB(0, 0, 0)
    p.drawString(55, y + 8, "REFERENCE")
    p.drawString(135, y + 8, "DESIGNATION")
    p.drawCentredString(340, y + 8, "QUANTITÉ")
    p.drawRightString(425, y + 8, "PRIX UNIT.")
    p.drawCentredString(470, y + 8, "REM %")
    p.drawRightString(X_ALIGNE_DROITE, y + 8, "MONTANT")
    
    # Soulignement de l'en-tête du tableau
    p.setStrokeColorRGB(0.2, 0.2, 0.2)
    p.line(50, y, X_ALIGNE_DROITE, y)
    
    # Configuration police des lignes de données
    p.setFont("Helvetica", 9)
    p.setStrokeColorRGB(0.85, 0.85, 0.85)
    
    lignes_prestation = devis.description_prestation.split('\n')
    
    # Traitement ligne par ligne
    for idx, ligne in enumerate(lignes_prestation):
        if not ligne.strip():
            continue
            
        y -= hauteur_ligne
        elements = [e.strip() for e in ligne.split('|')]
        
        ref = elements[0] if len(elements) > 0 and elements[0] else f"YAT-{100+idx}"
        des = elements[1] if len(elements) > 1 and elements[1] else "Prestation"
        qte_val = int(elements[2]) if len(elements) > 2 and elements[2].isdigit() else 1
        pxu_val = float(elements[3]) if len(elements) > 3 and elements[3].replace('.', '', 1).isdigit() else 0.0
        rem_val = float(elements[4]) if len(elements) > 4 and elements[4].replace('.', '', 1).isdigit() else 0.0
        
        larg_val = float(elements[5]) if len(elements) > 5 and elements[5].replace('.', '', 1).isdigit() else 1.0
        haut_val = float(elements[6]) if len(elements) > 6 and elements[6].replace('.', '', 1).isdigit() else 1.0
        
        surface_m2 = larg_val * haut_val

        # Formatage de la désignation pour placer la surface à la fin
        nom_minuscule = des.lower()
        mots_cles = ['bâche', 'bache', 'rollup', 'roll up', 'roll-up', 'affiche']
        
        if any(mot in nom_minuscule for mot in mots_cles):
            des = des.replace("[", "").replace("]", "").replace("(", "").replace(")", "").strip()
            des = des.replace(f"{int(surface_m2)}m2", "").replace(f"{int(surface_m2)}m²", "").strip()
            des = des.replace(f"{surface_m2:.2f}m2", "").replace(f"{surface_m2:.2f}m²", "").strip()
            des = " ".join(des.split())

            if des.lower().startswith("bâche") or des.lower().startswith("bache"):
                des = "Bâche" + des[5:]
            elif des.lower().startswith("affiche"):
                des = "Affiche" + des[7:]

            suffixe_m2 = f"{int(surface_m2)}m²" if surface_m2.is_integer() else f"{surface_m2:.2f}m²"
            des = f"{des} ({suffixe_m2})"

        montant_brut = qte_val * surface_m2 * pxu_val
        if rem_val > 0:
            montant_brut = montant_brut * (1 - (rem_val / 100))
        
        qte_text = str(qte_val)
        pxu_text = f"{int(pxu_val):,}".replace(",", " ")
        rem_text = f"{int(rem_val)}%" if rem_val > 0 else "0%"
        tot_text = f"{int(montant_brut):,}".replace(",", " ")

        p.drawString(55, y + 7, ref)
        p.drawString(135, y + 7, des[:45]) 
        p.drawCentredString(340, y + 7, qte_text)
        p.drawRightString(425, y + 7, pxu_text)
        p.drawCentredString(470, y + 7, rem_text)
        p.drawRightString(X_ALIGNE_DROITE, y + 7, tot_text)
        
        p.line(50, y, X_ALIGNE_DROITE, y)

    # =====================================================================
    # CADRAGE FINANCIER DU BAS DE PAGE
    # =====================================================================
    y_total = y - 45
    p.setStrokeColorRGB(0.7, 0.7, 0.7)
    p.rect(345, y_total - 20, 200, 40, fill=False, stroke=True)
    p.line(345, y_total, X_ALIGNE_DROITE, y_total)
    
    p.setFont("Helvetica", 10)
    p.setFillColorRGB(0.1, 0.1, 0.1)
    p.drawString(355, y_total + 5, "Sous-total")
    prix_formate = f"{int(devis.montant_total):,}".replace(",", " ")
    p.drawRightString(535, y_total + 5, f"{prix_formate} FCFA")
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(355, y_total - 14, "Total Général")
    p.setFillColorRGB(0.43, 0.16, 0.92) 
    p.drawRightString(535, y_total - 14, f"{prix_formate} FCFA")

    # --- PIED DE PAGE ---
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    p.drawCentredString(297, 50, "Ce devis est valable pour une durée de 30 jours à compter de sa date d'émission.")
    p.setFont("Helvetica-BoldOblique", 9)
    p.setFillColorRGB(0.43, 0.16, 0.92)
    p.drawCentredString(297, 35, "YaTout imprim - Votre image mérite la perfection ✨")

    p.showPage()
    p.save()
    buffer.seek(0)
    
    nom_fichier = f"Devis_{num_affiche.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=nom_fichier)


import io
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.contrib.auth.decorators import user_passes_test
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import timedelta


@user_passes_test(est_administrateur, login_url='connexion')
def telecharger_bl_pdf(request, devis_id):
    """Génère un Bon de Livraison au design épuré avec alignements recalibrés"""
    devis = get_object_or_404(Devis, id=devis_id)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=(595, 842)) # Format A4 standard
    
    X_GAUCHE = 40
    X_DROITE = 555
    LARGEUR_UTILE = X_DROITE - X_GAUCHE # 515 points

    # --- 1. EN-TÊTE ENTRÈPRISE ---
    p.setFont("Helvetica-Bold", 14)
    p.setFillColor(colors.HexColor("#1e293b")) 
    p.drawString(X_GAUCHE, 780, "YaTout imprim")
    
    p.setFont("Helvetica", 9)
    p.setFillColor(colors.HexColor("#475569"))
    p.drawString(X_GAUCHE, 766, "Abidjan, Côte d'Ivoire")
    p.drawString(X_GAUCHE, 754, "Téléphone : +225 05 74 70 20 92")
    p.drawString(X_GAUCHE, 742, "Email : contact@yatout.ci")
    
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColor(colors.HexColor("#64748b"))
    p.drawString(X_GAUCHE, 726, "Le Savant de l'imprimerie")

    # --- 2. BLOC CLIENT ---
    p.setFillColor(colors.HexColor("#f1f5f9")) 
    p.roundRect(360, 715, 195, 80, 6, fill=True, stroke=False)
    
    p.setFont("Helvetica-Bold", 10)
    p.setFillColor(colors.HexColor("#0f172a"))
    p.drawString(375, 775, devis.nom_client.upper())
    
    p.setFont("Helvetica", 9)
    p.setFillColor(colors.HexColor("#334155"))
    p.drawString(375, 758, f"Contact : {devis.telephone}")
    if devis.email:
        p.drawString(375, 744, f"Email : {devis.email}")
    p.drawString(375, 730, "Abidjan, Côte d'Ivoire")

    # --- 3. CALCUL DU NUMÉRO DE BL ---
    annee_court = devis.date_creation.strftime('%y')
    mois_court = str(int(devis.date_creation.strftime('%m')))
    
    if hasattr(devis, 'numero_bl') and devis.numero_bl and '/' in devis.numero_bl:
        num_bl_final = devis.numero_bl
    else:
        prefixe_mois = f"{annee_court}/BL-{mois_court}-"
        bl_du_mois = Devis.objects.filter(
            statut='converti_bl',
            date_creation__year=devis.date_creation.year,
            date_creation__month=devis.date_creation.month
        ).order_by('date_creation')
        
        liste_ids = list(bl_du_mois.values_list('id', flat=True))
        rang = liste_ids.index(devis.id) + 1 if devis.id in liste_ids else len(liste_ids) + 1
        num_bl_final = f"{prefixe_mois}{rang:04d}"
        
        if hasattr(devis, 'numero_bl'):
            devis.numero_bl = num_bl_final
            devis.save()

    # --- 4. TITRE DU DOCUMENT ---
    p.setFont("Helvetica-Bold", 16)
    p.setFillColor(colors.HexColor("#0f172a"))
    p.drawString(X_GAUCHE, 680, f"BON DE LIVRAISON {num_bl_final}")

    # --- 5. BLOC DES MÉTADONNÉES (4 Colonnes grises) ---
    y_bloc = 620
    hauteur_bloc = 40
    p.setFillColor(colors.HexColor("#f8fafc")) 
    p.rect(X_GAUCHE, y_bloc, LARGEUR_UTILE, hauteur_bloc, fill=True, stroke=False)
    
    # Séparateurs verticaux blancs discrets entre les 4 colonnes
    p.setStrokeColor(colors.white)
    p.setLineWidth(1.5)
    p.line(165, y_bloc, 165, y_bloc + hauteur_bloc)
    p.line(295, y_bloc, 295, y_bloc + hauteur_bloc)
    p.line(425, y_bloc, 425, y_bloc + hauteur_bloc)

    # Écriture des étiquettes (Labels)
    p.setFont("Helvetica-Bold", 7)
    p.setFillColor(colors.HexColor("#64748b"))
    p.drawString(48, y_bloc + 26, "DATE DU BON :")
    p.drawString(175, y_bloc + 26, "DATE D'ÉCHÉANCE :") # Rétabli et décalé à 175
    p.drawString(303, y_bloc + 26, "ORIGINE :")
    p.drawString(433, y_bloc + 26, "LIVRÉ PAR :")

    # Calcul de la date d'échéance à +30 jours
    from datetime import timedelta
    date_echeance = devis.date_creation + timedelta(days=30)

    # Écriture des valeurs dynamiques bien centrées dans leurs cases respectives
    p.setFont("Helvetica-Bold", 9)
    p.setFillColor(colors.HexColor("#1e293b"))
    p.drawString(48, y_bloc + 10, devis.date_creation.strftime('%d/%m/%Y'))
    p.drawString(175, y_bloc + 10, date_echeance.strftime('%d/%m/%Y')) # Affiche la date + 30 jours
    
    num_origine = devis.numero_devis_personnalise or f"{annee_court}/Dv{devis.date_creation.strftime('%m')}-{devis.id:03d}"
    p.drawString(303, y_bloc + 10, num_origine)
    valeur_livraison = devis.livre_par if devis.livre_par else "Nous-mêmes"
    p.drawString(433, y_bloc + 10, valeur_livraison)

    # =====================================================================
    # 6. TABLEAU DES PRESTATIONS RECALIBRÉ (Espaces élargis)
    # =====================================================================
    y = 565
    hauteur_ligne = 24
    
    p.setFillColor(colors.HexColor("#f1f5f9"))
    p.rect(X_GAUCHE, y, LARGEUR_UTILE, hauteur_ligne, fill=True, stroke=False)
    
    p.setFont("Helvetica-Bold", 8)
    p.setFillColor(colors.HexColor("#475569"))
    p.drawString(45, y + 8, "RÉFÉRENCE")
    p.drawString(125, y + 8, "DÉSIGNATION")
    p.drawCentredString(335, y + 8, "QTÉ")            # Décalé à gauche (335 au lieu de 360)
    p.drawRightString(430, y + 8, "PRIX UNITAIRE")     # Reculé à gauche (430 au lieu de 440)
    p.drawCentredString(480, y + 8, "REM. %")          # Réajusté
    p.drawRightString(X_DROITE - 5, y + 8, "MONTANT")
    
    p.setStrokeColor(colors.HexColor("#cbd5e1"))
    p.setLineWidth(0.5)
    p.line(X_GAUCHE, y, X_DROITE, y)
    
    p.setFont("Helvetica", 9)
    lignes_prestation = devis.description_prestation.split('\n')
    
    for idx, ligne in enumerate(lignes_prestation):
        if not ligne.strip():
            continue
            
        y -= hauteur_ligne
        elements = [e.strip() for e in ligne.split('|')]
        
        ref = elements[0] if len(elements) > 0 and elements[0] else f"REF-{100+idx}"
        des = elements[1] if len(elements) > 1 and elements[1] else "Prestation"
        qte_val = int(elements[2]) if len(elements) > 2 and elements[2].isdigit() else 1
        pxu_val = float(elements[3]) if len(elements) > 3 and elements[3].replace('.', '', 1).isdigit() else 0.0
        rem_val = float(elements[4]) if len(elements) > 4 and elements[4].replace('.', '', 1).isdigit() else 0.0
        larg_val = float(elements[5]) if len(elements) > 5 and elements[5].replace('.', '', 1).isdigit() else 1.0
        haut_val = float(elements[6]) if len(elements) > 6 and elements[6].replace('.', '', 1).isdigit() else 1.0
        
        surface_m2 = larg_val * haut_val

        nom_minuscule = des.lower()
        mots_cles = ['bâche', 'bache', 'rollup', 'roll up', 'roll-up', 'affiche']
        if any(mot in nom_minuscule for mot in mots_cles):
            des = des.replace("[", "").replace("]", "").replace("(", "").replace(")", "").strip()
            des = des.replace(f"{int(surface_m2)}m2", "").replace(f"{int(surface_m2)}m²", "").strip()
            des = " ".join(des.split())
            if des.lower().startswith("bâche") or des.lower().startswith("bache"):
                des = "Bâche" + des[5:]
            suffixe_m2 = f"{int(surface_m2)}m²" if surface_m2.is_integer() else f"{surface_m2:.2f}m²"
            des = f"{des} ({suffixe_m2})"

        montant_brut = qte_val * surface_m2 * pxu_val
        if rem_val > 0:
            montant_brut = montant_brut * (1 - (rem_val / 100))
        
        # Dessin avec les nouveaux calages X précis
        p.drawString(45, y + 7, ref)
        p.drawString(125, y + 7, des[:35])              # Diminué légèrement la coupure texte à 35 pour la sécurité
        p.drawCentredString(335, y + 7, str(qte_val))
        p.drawRightString(430, y + 7, f"{int(pxu_val):,}".replace(",", " ") + " F") # Écrit "F" au lieu de "FCFA" pour gagner de la place
        p.drawCentredString(480, y + 7, f"{int(rem_val)}%" if rem_val > 0 else "0%")
        p.drawRightString(X_DROITE - 5, y + 7, f"{int(montant_brut):,}".replace(",", " ") + " F")
        
        p.setStrokeColor(colors.HexColor("#f1f5f9"))
        p.line(X_GAUCHE, y, X_DROITE, y)

    # =====================================================================
    # 7. BLOC FINANCIER STRUCTURÉ
    # =====================================================================
    y_total = y - 35
    largeur_grille = 195
    x_grille = X_DROITE - largeur_grille
    hauteur_case = 20
    
    p.setStrokeColor(colors.HexColor("#cbd5e1"))
    p.setLineWidth(0.5)
    
    labels_finance = ["Sous-total", "Remise globale", "TVA 0%", "Total"]
    prix_formate = f"{int(devis.montant_total):,}".replace(",", " ") + " FCFA"
    valeurs_finance = [prix_formate, "-0 FCFA", "0 FCFA", prix_formate]
    
    for i in range(4):
        if i == 3:
            p.setFillColor(colors.HexColor("#f8fafc"))
            p.rect(x_grille, y_total - (i * hauteur_case), largeur_grille, hauteur_case, fill=True, stroke=False)
            p.setFont("Helvetica-Bold", 9)
            p.setFillColor(colors.HexColor("#0f172a"))
        else:
            p.setFont("Helvetica", 9)
            p.setFillColor(colors.HexColor("#475569"))
            
        p.rect(x_grille, y_total - (i * hauteur_case), largeur_grille, hauteur_case, fill=False, stroke=True)
        p.drawString(x_grille + 10, y_total - (i * hauteur_case) + 6, labels_finance[i])
        p.drawRightString(X_DROITE - 10, y_total - (i * hauteur_case) + 6, valeurs_finance[i])

    # --- 8. MENTIONS LÉGALES ---
    p.setFont("Helvetica-Bold", 8)
    p.setFillColor(colors.HexColor("#64748b"))
    p.drawString(X_GAUCHE, y_total - 100, f"Merci d'utiliser la communication suivante pour votre paiement : {num_bl_final}")

    p.setFont("Helvetica", 8)
    p.drawString(X_GAUCHE, y_total - 114, "Arrêter la facture à la somme de : Conforme au montant net indiqué ci-dessus.")

    # 🔴 RAJOUTER CES TROIS LIGNES ICI POUR LE SLOGAN EN BAS DE PAGE
    p.setFont("Helvetica-BoldOblique", 10)
    p.setFillColor(colors.HexColor("#7c3aed")) # Utilise votre violet signature
    p.drawCentredString(297, 40, "Avec YaTout imprim, « Votre image mérite la perfection »")

    p.showPage()
    p.save()
    buffer.seek(0)
    
    nom_fichier = f"BL_{num_bl_final.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=nom_fichier)

import io
import base64
import qrcode
from decimal import Decimal
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from shop.models import Facture, Devis  # Vérifiez que le chemin vers vos modèles est correct

def generer_facture_depuis_bl(request):
    if request.method == 'POST':
        # 1. Récupération de l'unique information requise : le numéro de BL
        numero_bl_saisi = request.POST.get('numero_bl', '').strip()
        mode_paiement = request.POST.get('mode_paiement')

        if not numero_bl_saisi:
            messages.error(request, "Veuillez saisir une référence de BL.")
            return redirect('espace_devis_dashboard')

        # 2. Recherche automatique robuste (Saisie complète ou partielle)
        devis_bl = Devis.objects.filter(numero_bl=numero_bl_saisi).first()
        
        if not devis_bl:
            devis_bl = Devis.objects.filter(numero_bl__icontains=numero_bl_saisi).first()

        if not devis_bl:
            messages.error(request, f"Aucun Bon de Livraison trouvé avec le numéro {numero_bl_saisi}.")
            return redirect('espace_devis_dashboard')

        # 3. Vérification de sécurité (éviter les doublons de facturation)
        if Facture.objects.filter(devis_associe=devis_bl).exists():
            messages.warning(request, f"Une facture a déjà été émise pour ce BL.")
            return redirect('espace_devis_dashboard')

        # 4. Automatisation des calculs financiers (Payé à 100% par défaut)
        montant_total_bl = Decimal(str(devis_bl.montant_total))
        montant_recu = montant_total_bl  
        reste_a_payer = Decimal('0.00')
        statut = 'PAYEE'

        # 5. Génération du numéro de facture dynamique aligné sur le préfixe du BL
        annee_courante = timezone.now().year
        nombre_factures = Facture.objects.count() + 1
        
        if devis_bl.numero_bl and "/" in devis_bl.numero_bl:
            prefixe_id = devis_bl.numero_bl.split('/')[0]
            numero_facture = f"{prefixe_id}/FAC-{annee_courante}-{nombre_factures:04d}"
        else:
            numero_facture = f"FAC-{annee_courante}-{nombre_factures:04d}"

        # 6. Sauvegarde définitive en base de données
        facture = Facture.objects.create(
            devis_associe=devis_bl,
            montant_total_bl=montant_total_bl,
            montant_recu=montant_recu,
            reste_a_payer=reste_a_payer,
            numero_facture=numero_facture,
            mode_paiement=mode_paiement,
            statut_paiement=statut
        )

        messages.success(request, f"Facture {numero_facture} générée avec succès !")
        return redirect('detail_facture', facture_id=facture.id)

    return redirect('espace_devis_dashboard')


def detail_facture(request, facture_id):
    facture = get_object_or_404(Facture, id=facture_id)
    
    # 1. Contenu textuel à intégrer dans le QR Code
    qr_data = (
        f"FACTURE YATOUT IMPRIM\n"
        f"N°: {facture.numero_facture}\n"
        f"Client: {facture.devis_associe.nom_client}\n"
        f"Total: {facture.montant_total_bl} FCFA\n"
        f"Statut: {facture.get_statut_paiement_display()}"
    )
    
    # 2. Génération du QR Code sous forme d'image en mémoire
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    
    # 3. Conversion de l'image en texte Base64 lisible par le HTML
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return render(request, 'shop/facture_detail.html', {
        'facture': facture,
        'qr_code_image': qr_base64
    })


# ✅ RECORRIGÉ : Utilisation d'une vérification staff directe pour éviter l'erreur de variable manquante
@user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url='connexion')
def supprimer_facture_securisee(request, facture_id):
    """Suppression d'un paiement / facture après validation du code secret admin."""
    if request.method == "POST":
        code_saisi = request.POST.get("code_secret")
        code_attendu = getattr(settings, 'SECRET_ADMIN_DELETE_CODE', '1234')

        if code_saisi == code_attendu:
            facture = get_object_or_404(Facture, id=facture_id)
            numero_fac = facture.numero_facture
            
            facture.delete()
            messages.success(request, f"🗑️ La facture {numero_fac} a été définitivement effacée des registres.")
        else:
            messages.error(request, "❌ Code administrateur incorrect ! Action de suppression révoquée.")

    return redirect('espace_devis_dashboard')