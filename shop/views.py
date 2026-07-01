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
from django.http import JsonResponse
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
from .models import Produit, Prestation, CommandeImpression
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
                return redirect('accueil')
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

@login_required(login_url='connexion')
def dashboard_vendeur(request):
    """Affiche les statistiques financières et logistiques du vendeur."""
    try:
        vendeur = request.user.vendeur
    except Vendeur.DoesNotExist:
        return redirect('inscription_vendeur')

    mes_produits = Produit.objects.filter(vendeur=vendeur)
    
    # 1. CORRECTION : On passe par 'items__' pour filtrer les commandes
    mes_ventes = Commande.objects.filter(items__produit__vendeur=vendeur).order_by('-date_commande').distinct()

    # 2. CORRECTION : On calcule les revenus en filtrant uniquement les articles de CE vendeur
    total_revenus = 0
    for vente in mes_ventes:
        for item in vente.items.filter(produit__vendeur=vendeur):
            total_revenus += item.get_cost()

    nombre_ventes = mes_ventes.count()

    context = {
        'vendeur': vendeur,
        'produits': mes_produits,
        'ventes': mes_ventes,
        'total_revenus': total_revenus,
        'nombre_ventes': nombre_ventes,
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





from django.db.models import Q, F

GEMINI_API_KEY = ""


@csrf_exempt
def assistant_chatbot_api(request):
    # CORRECTION 1 : Récupérer le bon nom de variable configuré sur Railway
    api_key = os.environ.get("CLE_API_GEMINI")
    
    print("--- DEBUG IA --- LA CLÉ RECUPEREE EST :", api_key)
  
    reponse_bot = "Désolé, je rencontre des difficultés techniques à me connecter."
    session_key = ''

    # ... [Le reste de votre code reste identique (POST, BDD, Historique, Payload...)] ...

            # Vers la fin de votre fonction, remplacez les headers par ceci :
    headers = {
                'Content-Type': 'application/json',
                'x-goog-api-key': api_key  # CORRECTION 2 : On utilise la variable Python locale "api_key"
            }
            
    response = requests.post(url_api, json=payload, headers=headers, timeout=10)

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
        contexte_produits = "Aucun article spécifique trouvé dans la boutique."
        contexte_impressions = "Aucun support d'impression spécifique trouvé pour cette demande."
        
        # --- A. RECHERCHE CÔTÉ BOUTIQUE ---
        mots_cles_catalogue = ['produit', 'article', 'vendre', 'acheter', 'catalogue', 'dispo', 'boutique', 'promotion', 'promo', 'solde', 'rabais']
        un_mot_cle_trouve = any(mot in message_client.lower() for mot in mots_cles_catalogue)
        
        if un_mot_cle_trouve or len(message_client) > 2:
            produits_trouves = Produit.objects.filter(
                Q(nom__icontains=message_client) | Q(description__icontains=message_client),
                stock__gt=0
            ).select_related('vendeur').distinct()[:4]
            
            if 'promo' in message_client.lower() or 'solde' in message_client.lower() or 'rabais' in message_client.lower():
                produits_trouves = Produit.objects.filter(ancien_prix__gt=F('prix'), stock__gt=0).select_related('vendeur')[:4]

            if produits_trouves.exists():
                liste_p = []
                for p in produits_trouves:
                    devise = p.vendeur.get_devise_display() if hasattr(p.vendeur, 'get_devise_display') else p.vendeur.devise
                    info_p = f"- {p.nom} : {p.prix} {devise} (Boutique : {p.vendeur.nom_boutique})"
                    if p.ancien_prix and p.ancien_prix > p.prix:
                        info_p += f" [PROMO! Avant: {p.ancien_prix} {devise} - Remise: {p.reduction_pourcentage}%]"
                    liste_p.append(info_p)
                contexte_produits = "Articles boutique trouvés :\n" + "\n".join(liste_p)

        # --- B. 🖨️ NOUVEAU : RECHERCHE CÔTÉ ATELIER D'IMPRESSION ---
        from .models import Prestation # Assurez-vous que l'import est fait
        mots_cles_impression = ['impression', 'imprimer', 'affiche', 'bache', 'bâche', 'flyer', 'support', 'autocollant', 'lettre', 'f cfa', 'fcfa']
        besoin_impression = any(mot in message_client.lower() for mot in mots_cles_impression)

        if besoin_impression or len(message_client) > 2:
            # On cherche si un support d'impression correspond au message
            prestations_trouvees = Prestation.objects.filter(
                Q(titre__icontains=message_client) | Q(description__icontains=message_client)
            ).distinct()[:4]
            
            # Si le client demande globalement les prix ou les supports de l'atelier
            if 'support' in message_client.lower() or 'tarifs' in message_client.lower() or 'prix' in message_client.lower() or not prestations_trouvees.exists():
                # Par défaut, on lui donne les 4 supports principaux si sa recherche est trop floue
                prestations_trouvees = Prestation.objects.all()[:4]

            if prestations_trouvees.exists():
                liste_i = []
                for prest in prestations_trouvees:
                    # Extraction propre du choix d'unité (ex: Au mètre carré, par lot de 100...)
                    unite = prest.get_type_unite_display() if hasattr(prest, 'get_type_unite_display') else prest.type_unite
                    liste_i.append(f"- {prest.titre} : {prest.prix_unitaire} FCFA ({unite})")
                contexte_impressions = "Supports d'imprimerie disponibles à l'atelier YaTout :\n" + "\n".join(liste_i)

        # 3. CONSTITUTION DE L'HISTORIQUE CHRONOLOGIQUE
        try:
            # Tri par 'id' décroissant pour capter les derniers échanges, puis inversion
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
                "Tu es l'assistant virtuel officiel du site d'e-commerce multi-vendeur 'YaTout' et de son atelier 'YaTout Impression'. "
                "Ton rôle est d'aider les acheteurs, les vendeurs et les clients de l'atelier avec politesse, enthousiasme et concision. "
                f"Information temporelle : Nous sommes aujourd'hui le {date_aujourdhui}. "
                "Règles strictes de l'atelier d'imprimerie à connaître : "
                "1. Pour l'atelier, le client sélectionne son support à gauche, ajuste ses options (finitions, délais) et remplit le formulaire à droite pour simuler son devis en direct. "
                "2. La remise commerciale standard de l'atelier est de 5% incluse sur le Net à payer. "
                "3. Les finitions disponibles sont : Standard/Brillante, Mate (+10%) et Vernis sélectif. Les délais sont Normal ou Urgent/Express 24h. "
                "\n--- CATALOGUE DES SUPPORTS D'IMPRESSION RÉELS ---\n"
                f"{contexte_impressions}\n"
                "\n--- ARTICLES EN STOCK DE LA BOUTIQUE E-COMMERCE ---\n"
                f"{contexte_produits}\n"
                "Règle d'or : Ne vends et n'invente jamais de supports ou de prix imaginaires. Utilise strictement les listes ci-dessus. "
                "Réponds toujours en français avec des émojis appropriés et reste amical."
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
                'x-goog-api-key': CLE_API_GEMINI
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




@staff_member_required
def generer_bon_pdf(request, commande_id):
    commande = get_object_or_404(CommandeImpression, id=commande_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{commande.numero_bon()}.pdf"'

    # Marges définies à 40 points
    marge_gauche = 40
    marge_droite = 40
    
    doc = SimpleDocTemplate(
        response, 
        pagesize=letter, 
        rightMargin=marge_droite, 
        leftMargin=marge_gauche, 
        topMargin=40, 
        bottomMargin=40
    )
    story = []
    
    # --- CALCUL DE LA LARGEUR MAXIMALE DISPONIBLE SUR LA FEUILLE ---
    largeur_page = letter[0]  # Largeur totale de la feuille letter
    largeur_utile = largeur_page - (marge_gauche + marge_droite) # Largeur réelle pour le contenu (532 points)
    
    styles = getSampleStyleSheet()
    normal_style = styles['Normal']
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontName='Helvetica-Bold')
    
    # Styles d'alignement pour les prix dans le tableau
    style_prix_entete = ParagraphStyle('PrixEntete', parent=bold_style, alignment=2) # Aligné à droite
    style_prix_cellule = ParagraphStyle('PrixCellule', parent=normal_style, alignment=2) # Aligné à droite

    # --- 1. CONFIGURATION DU BLOC GAUCHE (ENTREPRISE + INFOS BON) ---
    bloc_gauche = []
    
    chemin_logo = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
    if os.path.exists(chemin_logo):
        logo = Image(chemin_logo, width=110, height=45)
        logo.hAlign = 'LEFT'
        bloc_gauche.append(logo)
        bloc_gauche.append(Spacer(1, 5))
        
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#2E0854"), spaceAfter=3)
    bloc_gauche.append(Paragraph("<b>YaTout Print</b>", title_style))
    bloc_gauche.append(Paragraph("<font size=9 color='#7b6f93'>Atelier d'Impression Numérique</font>", normal_style))
    bloc_gauche.append(Paragraph("<font size=9>Email : print@yatout.com<br/>Tél : +225 07 00 00 00 00 (CI)</font>", normal_style))
    
    bloc_gauche.append(Spacer(1, 15))
    bloc_gauche.append(Paragraph(f"<b>Numéro de Bon :</b> {commande.numero_bon()}", normal_style))
    bloc_gauche.append(Paragraph(f"<b>Date / Heure :</b> {commande.date_commande.strftime('%d/%m/%Y à %H:%M')}", normal_style))

    # --- 2. CONFIGURATION DU BLOC DROITE (COORDONNÉES CLIENT) ---
    bloc_droite = []
    client_title_style = ParagraphStyle('ClientTitle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor("#2E0854"), spaceAfter=8)
    bloc_droite.append(Paragraph("<b>FACTURE & DESTINATAIRE</b>", client_title_style))
    bloc_droite.append(Paragraph(f"<b>Client :</b> {commande.nom_client}", normal_style))
    
    if commande.telephone.startswith('+') or commande.telephone.startswith('00'):
        tel_affiche = commande.telephone
    else:
        tel_affiche = f"+225 {commande.telephone}"
        
    bloc_droite.append(Paragraph(f"<b>Contact :</b> {tel_affiche}", normal_style))
    bloc_droite.append(Paragraph(f"<b>Email :</b> {commande.email_client}", normal_style))

    # --- 3. ALIGNEMENT FACE À FACE (Prend toute la largeur utile divisée en deux) ---
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

    # --- 4. TABLEAU DES ARTICLES (DÉSIGNATION PLEINE LARGEUR) ---
    # Nous fixons des tailles strictes pour le Prix (90), Quantité (60) et Total (110).
    # La colonne Désignation prend TOUT le reste de l'espace de la feuille (largeur_utile - 260)
    col_prix = 90
    col_qte = 60
    col_total = 110
    col_designation = largeur_utile - (col_prix + col_qte + col_total)

    data = [
        [Paragraph("<b>Désignation Prestation</b>", bold_style), 
         Paragraph("<b>Prix Unit.</b>", style_prix_entete), 
         Paragraph("<b>Quantité</b>", bold_style), 
         Paragraph("<b>Total Brut</b>", style_prix_entete)]
    ]
    
    articles = json.loads(commande.details_json)
    for art in articles:
        data.append([
            Paragraph(f"<b>{art['titre']}</b>", normal_style),
            Paragraph(f"{art['prix']:,} FCFA", style_prix_cellule),
            f"x{art['qte']}",
            Paragraph(f"{art['total']:,} FCFA", style_prix_cellule)
        ])

    # Lignes des totaux de fin de facture
    data.append(["", "", Paragraph("<b>Total Brut :</b>", bold_style), Paragraph(f"<b>{commande.total_brut:,} FCFA</b>", style_prix_cellule)])
    data.append(["", "", Paragraph("<font color='red'><b>Remise (5%) :</b></font>", bold_style), Paragraph(f"<font color='red'><b>-{commande.montant_remise:,} FCFA</b></font>", style_prix_cellule)])
    data.append(["", "", Paragraph("<b>MONTANT NET A PAYER :</b>", bold_style), Paragraph(f"<b>{commande.total_final:,} FCFA</b>", style_prix_cellule)])

    # Application des largeurs dynamiques calculées pour colWidths
    tableau = Table(data, colWidths=[col_designation, col_prix, col_qte, col_total])
    tableau.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3E8FF")),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),      # Aligne le texte de désignation à gauche
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),     # Aligne le prix unitaire à droite
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),    # Centre les quantités
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),     # Aligne le prix total à droite
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, len(articles)), 0.5, colors.HexColor("#E8E3F0")),
        ('LINEABOVE', (2, -1), (3, -1), 1.5, colors.HexColor("#2E0854")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),     # Un peu d'espace pour respirer
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    story.append(tableau)
    doc.build(story)
    return response




@staff_member_required
def liste_commandes_admin(request):
    # On récupère les commandes
    commandes = CommandeImpression.objects.all().order_by('-date_commande')
    
    # On pré-calcule les totaux pour chaque commande pour les afficher dans le tableau HTML
    for cmd in commandes:
        cmd.totaux = cmd.calcul_total() # Ajoute les calculs dynamiquement
        
    return render(request, 'admin_commandes.html', {'commandes': commandes})




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
    sujet = f"✅ Votre bon d'impression #{commande.numero_bon()} a été validé !"
    message = f"Bonjour {commande.nom_client},\n\nBonne nouvelle ! L'administrateur de YaTout vient de valider votre bon de commande.\n\nNous lançons la fabrication de vos impressions. Nous vous contacterons très vite au {commande.telephone} dès que vos supports seront prêts.\n\nMerci pour votre confiance !"
    
    try:
        send_mail(sujet, message, 'noreply@yatout.com', [commande.email_client], fail_silently=True)
    except Exception:
        pass
        
    return redirect('liste_commandes_admin')





def page_impressions(request):
    """ GÈRE L'ATELIER : Permet de choisir un support unique dans le select et calcule l'estimation """
    prestations = Prestation.objects.all()

    # Initialisation des variables de session pour mémoriser la simulation en cours
    if 'simulation_print' not in request.session:
        request.session['simulation_print'] = {
            'prestation_id': None,
            'quantite': 1
        }
    
    sim = request.session['simulation_print']

    if request.method == "POST":
        # CAS A : L'utilisateur change de produit dans le menu déroulant à droite
        if 'prestation_id' in request.POST and 'maj_quantite' not in request.POST and 'nom_client' not in request.POST:
            id_choisi = request.POST.get('prestation_id')
            if id_choisi:
                sim['prestation_id'] = int(id_choisi)
                sim['quantite'] = 1 
            else:
                sim['prestation_id'] = None
                sim['quantite'] = 1
            
            request.session['simulation_print'] = sim
            request.session.modified = True
            return redirect('page_impressions')

        # CAS B : L'utilisateur met à jour la quantité (Clic sur "Recalculer")
        elif 'maj_quantite' in request.POST:
            id_choisi = request.POST.get('prestation_id')
            try:
                nouvelle_qte = int(request.POST.get('quantite', 1))
                if nouvelle_qte < 1:
                    nouvelle_qte = 1
            except ValueError:
                nouvelle_qte = 1
                
            sim['prestation_id'] = int(id_choisi) if id_choisi else None
            sim['quantite'] = nouvelle_qte
            
            request.session['simulation_print'] = sim
            request.session.modified = True
            return redirect('page_impressions')

        # CAS C : Validation finale et création du Bon de Commande
        elif 'nom_client' in request.POST:
            nom = request.POST.get('nom_client')
            email = request.POST.get('email_client')
            tel = request.POST.get('telephone_client')
            id_choisi = request.POST.get('prestation_id')
            quantite = int(request.POST.get('quantite', 1))

            if id_choisi:
                prest = get_object_or_404(Prestation, id=id_choisi)
                total_brut = prest.prix_unitaire * quantite
                montant_remise = int(total_brut * 0.05)
                total_final = total_brut - montant_remise

                structure_json = [{
                    'titre': prest.titre, 
                    'qte': quantite, 
                    'prix': prest.prix_unitaire, 
                    'total': total_brut
                }]

                commande = CommandeImpression.objects.create(
                    nom_client=nom, 
                    email_client=email, 
                    telephone=tel,
                    details_json=json.dumps(structure_json), 
                    total_brut=total_brut,
                    montant_remise=montant_remise, 
                    total_final=total_final
                )

                request.session['simulation_print'] = {'prestation_id': None, 'quantite': 1}
                request.session.modified = True
                return render(request, 'shop/impression_succes.html', {'commande': commande})

    # Traitement de la zone d'affichage (GET)
    item_selectionne = None
    quantite_actuelle = sim.get('quantite', 1)
    total_brut = 0

    if sim.get('prestation_id'):
        try:
            item_selectionne = Prestation.objects.get(id=sim['prestation_id'])
            total_brut = item_selectionne.prix_unitaire * int(quantite_actuelle)
        except Prestation.DoesNotExist:
            sim['prestation_id'] = None
            request.session['simulation_print'] = sim
            request.session.modified = True

    remise_panier = int(total_brut * 0.05)
    total_final = total_brut - remise_panier

   # 1. On récupère les prestations qui servent d'exemples de réalisations
    exemples_realisations = Prestation.objects.all()

    # 2. Votre bloc de retour existant
    return render(request, 'shop/impressions.html', {
        'prestations': prestations,
        'item_selectionne': item_selectionne,
        'quantite_actuelle': quantite_actuelle,
        'total_brut': total_brut,
        'remise_panier': remise_panier,
        'total_final': total_final,
        'exemples_realisations': exemples_realisations,
    })


def page_prestations(request):
    """ Affiche la page catalogue contenant tous les tarifs et caractéristiques techniques """
    prestations = Prestation.objects.all()
    return render(request, 'shop/prestations.html', {'prestations': prestations})





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


# 2. Vue pour lister vos vraies prestations d'impression
def page_prestations(request):
    # Récupère toutes les prestations enregistrées dans l'admin Django
    prestations = Prestation.objects.all()
    return render(request, 'shop/prestations.html', {'prestations': prestations})




def detail_prestation(request, prestation_id):
    prestation = get_object_or_404(Prestation, id=prestation_id)
    
    # Valeurs par défaut au premier chargement (GET)
    quantite_saisie = 1
    longueur = 1.0
    largeur = 1.0
    prix_total = prestation.prix_unitaire 
    unite_texte = f"{quantite_saisie} unité(s)"

    if request.method == "POST":
        # 1. Règles de calcul selon l'unité et récupération des champs
        if prestation.type_unite == 'M2':
            longueur = float(request.POST.get('longueur', 1))
            largeur = float(request.POST.get('largeur', 1))
            surface_m2 = longueur * largeur
            prix_total = int(surface_m2 * prestation.prix_unitaire)
            unite_texte = f"Surface: {surface_m2:.2f} m² ({longueur}m x {largeur}m)"
            quantite_saisie = surface_m2 # Utilisé pour la cohérence
        elif prestation.type_unite == 'LOT_100':
            quantite_saisie = float(request.POST.get('quantite', 1))
            prix_total = int((quantite_saisie / 100) * prestation.prix_unitaire)
            unite_texte = f"{int(quantite_saisie)} exemplaires"
        elif prestation.type_unite == 'UNITE':
            quantite_saisie = float(request.POST.get('quantite', 1))
            prix_total = int(quantite_saisie * prestation.prix_unitaire)
            unite_texte = f"{int(quantite_saisie)} unité(s)"
        else: # LETTRE
            quantite_saisie = float(request.POST.get('quantite', 1))
            prix_total = int(quantite_saisie * prestation.prix_unitaire)
            unite_texte = f"{int(quantite_saisie)} lettres"

        # 2. Validation finale et envoi vers la page intermédiaire WhatsApp
        if 'valider_whatsapp' in request.POST or 'valider_commande' in request.POST:
            nom = request.POST.get('nom_client')
            email = request.POST.get('email_client', '')
            tel = request.POST.get('telephone_client')
            
            # Structure de base de l'élément du panier
            item_panier = {
                'titre': prestation.titre,
                'type_unite': prestation.type_unite,
                'prix': prestation.prix_unitaire,
                'total': prix_total
            }

            # Ajout des spécificités géométriques dans le JSON si c'est du m² (utile pour Flutter / Web)
            if prestation.type_unite == 'M2':
                item_panier['longueur'] = longueur
                item_panier['largeur'] = largeur
                item_panier['surface_m2'] = round(surface_m2, 2)
            else:
                item_panier['qte'] = int(quantite_saisie) if quantite_saisie.is_integer() else quantite_saisie

            structure_tableau_json = [item_panier]
            
            montant_remise = int(prix_total * 0.05)
            total_final = prix_total - montant_remise

            commande = CommandeImpression.objects.create(
                nom_client=nom,
                email_client=email,
                telephone=tel,
                details_json=json.dumps(structure_tableau_json),
                total_brut=prix_total,
                montant_remise=montant_remise,
                total_final=total_final,
                statut='EN_ATTENTE'
            )
            
            # Si le client clique sur "Ajouter au panier", on effectue une action spécifique
            if 'valider_commande' in request.POST:
                # Adaptez ici selon la redirection de votre panier multi-vendeurs global
                return render(request, 'shop/bon_impression_pret.html', {'commande': commande})

            # Sinon, on génère le flux WhatsApp classique
            numero_bon = commande.numero_bon()

            message_brut = (
                f"Bonjour YaTout, je valide ma commande.\n"
                f"Bon : {numero_bon}\n"
                f"Client : {nom}\n"
                f"Prestation : {prestation.titre}\n"
                f"Détails : {unite_texte}\n"
                f"Net a payer : {total_final} FCFA"
            )

            # Utilisation de urllib pour un encodage URL plus robuste (gère les accents et caractères spéciaux)
            texte_url = urllib.parse.quote(message_brut)
            numero_entreprise = "2250574702092"
            lien_whatsapp_final = f"https://wa.me/{numero_entreprise}?text={texte_url}"
            
            return render(request, 'shop/bon_impression_pret.html', {
                'commande': commande,
                'lien_whatsapp': lien_whatsapp_final
            })

    # Rendu final (GET ou après calcul d'estimation brute)
    return render(request, 'shop/detail_prestation.html', {
        'prestation': prestation,
        'quantite_saisie': int(quantite_saisie) if isinstance(quantite_saisie, (int, float)) and quantite_saisie.is_integer() else quantite_saisie,
        'prix_total': prix_total,
        'longueur': longueur,
        'largeur': largeur
    })





def voir_bon_commande(request, commande_id):
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    
    if request.method == "POST":
        if 'changer_remise' in request.POST:
            nouvelle_remise_pourcent = float(request.POST.get('pourcentage_remise', 5))
            total_brut = commande.total_brut
            montant_remise = int(total_brut * (nouvelle_remise_pourcent / 100))
            commande.montant_remise = montant_remise
            commande.total_final = total_brut - montant_remise
            commande.save()
            
        # 🟢 VERIFIEZ CETTE LIGNE : Elle doit être stricte, sans "and ..."
        elif 'generer_bl' in request.POST:
            commande.bl_genere = True
            commande.statut = 'VALIDE'
            commande.save()
            # Redirection directe vers la vue du Bon de Livraison
            return redirect('voir_bon_livraison', commande_id=commande.id)
        
    articles_liste = json.loads(commande.details_json)
    pourcentage_actuel = int((commande.montant_remise / commande.total_brut) * 100) if commande.total_brut > 0 else 0

    return render(request, 'shop/bon_commande.html', {
        'commande': commande,
        'articles_liste': articles_liste,
        'pourcentage_actuel': pourcentage_actuel
    })


def voir_bon_livraison(request, commande_id):
    """ Génère la page du Bon de Livraison officiel (Reçu) si l'admin l'a validé """
    # Sécurité : Seul un bon transféré par l'admin est visible en BL
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    
    articles_liste = json.loads(commande.details_json)
    
    return render(request, 'shop/bon_livraison.html', {
        'commande': commande,
        'articles_liste': articles_liste
    })



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