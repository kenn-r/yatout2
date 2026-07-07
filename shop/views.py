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






@staff_member_required
def generer_bon_pdf(request, commande_id):
    # Récupération de la commande principale
    commande = get_object_or_404(CommandeImpression, id=commande_id)

    response = HttpResponse(content_type='application/pdf')
    # Modification optionnelle : 'inline' au lieu de 'attachment' permet de voir le PDF sur Safari/Chrome avant d'imprimer
    response['Content-Disposition'] = f'inline; filename="{commande.numero_bon()}.pdf"'

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
    
    # Vérification et ajout dynamique du titre du document (Bon de Commande ou Livraison)
    # Si le champ 'bl_genere' est à True, le titre s'adapte automatiquement sur le document
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
    bloc_gauche.append(Paragraph(f"<b>Numéro :</b> {commande.numero_bon()}", normal_style))
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

    # --- 4. TABLEAU DES ARTICLES AVEC GESTION DE LA REMISE ARTICLE ---
    # Répartition des colonnes sur la largeur utile totale (532 points) :
    col_prix = 80
    col_qte = 45
    col_remise = 75   # 👈 Nouvelle colonne dédiée à la remise sur chaque article
    col_total = 95
    col_designation = largeur_utile - (col_prix + col_qte + col_remise + col_total) # Reste ~237 pour le texte

    data = [
        [Paragraph("<b>Désignation Prestation</b>", bold_style), 
         Paragraph("<b>Prix Unit.</b>", style_prix_entete), 
         Paragraph("<b>Qté</b>", bold_style), 
         Paragraph("<b>Remise / Art.</b>", style_prix_entete), # 👈 En-tête de remise
         Paragraph("<b>Total Net</b>", style_prix_entete)]
    ]
    
    articles = json.loads(commande.details_json)
    for art in articles:
    # 1. Récupération sécurisée de la quantité (gère 'qte' ou 'quantite')
        qte_valeur = int(art.get('qte', art.get('quantite', 1)))
    
    # 2. Récupération sécurisée du champ 'remise' ou 'discount' 
    remise_art_valeur = art.get('remise', 0)
    
    # 3. Ajout sécurisé dans les données du tableau ReportLab
    data.append([
        Paragraph(f"<b>{art['titre']}</b>", normal_style),
        Paragraph(f"{art['prix']:,} FCFA", style_prix_cellule),
        Paragraph(f"x{qte_valeur}", bold_style),  # 🟢 Utilise la variable sécurisée
        Paragraph(f"-{remise_art_valeur:,} FCFA" if remise_art_valeur else "0 FCFA", style_prix_cellule),
        Paragraph(f"{art['total']:,} FCFA", style_prix_cellule)
    ])

    # Lignes des totaux globaux et de la case pour la remise globale finale
    data.append(["", "", "", Paragraph("<b>Total Brut :</b>", bold_style), Paragraph(f"<b>{commande.total_brut:,} FCFA</b>", style_prix_cellule)])
    data.append(["", "", "", Paragraph("<font color='red'><b>Remise globale :</b></font>", bold_style), Paragraph(f"<font color='red'><b>-{commande.montant_remise:,} FCFA</b></font>", style_prix_cellule)])
    data.append(["", "", "", Paragraph("<b>NET A PAYER :</b>", bold_style), Paragraph(f"<b>{commande.total_final:,} FCFA</b>", style_prix_cellule)])

    # Application de la structure à 5 colonnes
    tableau = Table(data, colWidths=[col_designation, col_prix, col_qte, col_remise, col_total])
    tableau.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F3E8FF")),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),      
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),     
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),    
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),     # Aligne la colonne des remises à droite
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
    
    # Création des cadres de visa comme visible sur le modèle imprimé (Visa Livreur / Visa Client)
    style_visa = ParagraphStyle('VisaStyle', parent=bold_style, fontSize=10, textColor=colors.HexColor("#555555"))
    cell_livreur = [Paragraph("<b>Visa Livreur / Cachet</b>", style_visa), Spacer(1, 40)]
    cell_client = [Paragraph("<b>Visa Client (Lu et approuvé)</b>", style_visa), Spacer(1, 40)]
    
    table_visa = Table([[cell_livreur, cell_client]], colWidths=[largeur_utile/2, largeur_utile/2])
    table_visa.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor("#CCCCCC")), # Ligne pour signer
        ('LINEBELOW', (1, 0), (1, 0), 0.5, colors.HexColor("#CCCCCC")),
        ('RIGHTPADDING', (0, 0), (0, 0), 30), # Évite que les lignes ne collent
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

    # 🌟 AJOUT : On récupère toutes les commandes d'impression du site
    toutes_les_commandes = CommandeImpression.objects.all().order_by('-date_commande')

    # 2. Votre bloc de retour mis à jour avec les commandes
    return render(request, 'shop/impressions.html', {
        'prestations': prestations,
        'item_selectionne': item_selectionne,
        'quantite_actuelle': quantite_actuelle,
        'total_brut': total_brut,
        'remise_panier': remise_panier,
        'total_final': total_final,
        'exemples_realisations': exemples_realisations,
        'toutes_les_commandes': toutes_les_commandes, # 🚀 Indispensable pour remplir votre tableau
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


# 2. Placez ce décorateur juste AU-DESSUS de votre fonction
@csrf_exempt
def voir_bon_commande(request, commande_id):
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    articles_liste = json.loads(commande.details_json)
    # ... (le reste de votre code reste identique)
    
    # 1. Préparation initiale des variables entières pour l'affichage (GET)
    for art in articles_liste:
        quantite_securisee = int(art.get('qte', art.get('quantite', 1)))
        prix_unitaire = int(float(art.get('prix', 0)))
        brut_ligne = quantite_securisee * prix_unitaire
        
        # Lecture du pourcentage de remise stocké (ex: 25)
        taux_remise = int(float(art.get('remise_pourcent', 0)))
        montant_remise_ligne = round(brut_ligne * (taux_remise / 100.0))
        total_net_ligne = max(0, brut_ligne - montant_remise_ligne)
        
        # Clés lues par le template HTML du Bon de Commande
        art['qte_entier'] = quantite_securisee
        art['prix_entier'] = prix_unitaire
        art['remise_pourcent_entier'] = f"{taux_remise} %" if taux_remise > 0 else "0 %"
        art['total_net_entier'] = total_net_ligne

    # Récupération des totaux généraux pour le bloc du bas
    commande.total_brut_entier = int(commande.total_brut)
    commande.montant_remise_global_entier = int(commande.montant_remise)
    commande.total_final_entier = int(commande.total_final)
    commande.montant_remise_global = int(commande.montant_remise)

    # Récupération ou initialisation du pourcentage de remise globale actuel
    pourcentage_actuel = int((commande.montant_remise / commande.total_brut) * 100) if commande.total_brut > 0 else 0

    if request.method == "POST":
        # ACTION 1 : MISE A JOUR DES REMISES EN POURCENTAGE PAR ARTICLE INDIVIDUEL
        if 'appliquer_remises_articles' in request.POST:
            nouveau_total_brut_global = 0
            total_remise_cumulee = 0
            
            for index, art in enumerate(articles_liste):
                cle_remise = f"remise_{index}"
                
                # Le vendeur saisit un pourcentage entier sur l'interface (ex: 25)
                taux_remise = int(float(request.POST.get(cle_remise, 0)))
                
                quantite_securisee = int(art.get('qte', art.get('quantite', 1)))
                prix_unitaire = int(float(art.get('prix', 0)))
                total_brut_ligne = quantite_securisee * prix_unitaire
                
                # Calcul de la réduction en FCFA (arrondi à l'entier)
                montant_reduction_ligne = round(total_brut_ligne * (taux_remise / 100.0))
                total_net_ligne = max(0, total_brut_ligne - montant_reduction_ligne)
                
                # Enregistrement des valeurs définitives dans le JSON
                art['remise_pourcent'] = taux_remise
                art['remise'] = montant_reduction_ligne
                art['total'] = total_net_ligne
                
                # Cumul des montants pour la commande globale
                nouveau_total_brut_global += total_brut_ligne
                total_remise_cumulee += montant_reduction_ligne
            
            # Recalcul de la remise globale basée sur le nouveau brut
            nouveau_montant_remise_global = round(nouveau_total_brut_global * (pourcentage_actuel / 100))
            
            # Sauvegarde finale en base de données (Nombres entiers stricts)
            commande.details_json = json.dumps(articles_liste)
            commande.total_brut = int(nouveau_total_brut_global)
            commande.montant_remise = int(total_remise_cumulee + nouveau_montant_remise_global)
            commande.total_final = int(nouveau_total_brut_global - commande.montant_remise)
            commande.save()
            
            messages.success(request, "Les remises par article ont été appliquées avec succès !")
            return redirect('voir_bon_commande', commande_id=commande.id)

        # ACTION 2 : MISE A JOUR DE LA REMISE GLOBALE EN POURCENTAGE
        elif 'changer_remise' in request.POST:
            nouvelle_remise_pourcent = int(float(request.POST.get('pourcentage_remise', 5)))
            total_brut = int(commande.total_brut)
            montant_remise = round(total_brut * (nouvelle_remise_pourcent / 100))
            
            commande.montant_remise = int(montant_remise)
            commande.total_final = int(total_brut - montant_remise)
            commande.save()
            
            messages.success(request, f"Remise globale mise à jour à {nouvelle_remise_pourcent}%")
            return redirect('voir_bon_commande', commande_id=commande.id)
            
        # ACTION 3 : GENERATION DU BON DE LIVRAISON + ENVOI MAIL
        elif 'generer_bl' in request.POST:
            commande.bl_genere = True
            commande.statut = 'VALIDE'
            commande.save()
            
            sujet = f"✅ Votre bon d'impression #{commande.numero_bon} a été validé !"
            message = (
                f"Bonjour {commande.nom_client},\n\n"
                f"Bonne nouvelle ! L'administrateur de YaTout vient de valider votre bon de commande.\n\n"
                f"Nous lançons la fabrication de vos impressions. Nous vous contacterons très vite au "
                f"{commande.telephone} dès que vos supports seront prêts pour la livraison.\n\n"
                f"Merci pour votre confiance !"
            )
        try:
                send_mail(sujet, message, 'noreply@yatout.com', [commande.email_client], fail_silently=True)
        except Exception:
                pass

        messages.success(request, "Bon de Livraison généré et validé avec succès ! 🎉")
            
            # 🟢 Utilisation de la route absolue exacte de votre URL n°32
        return redirect(f"/impression/bon-livraison/{commande.id}/")

        # 🟢 Cette ligne doit être alignée avec le "if request.method == 'POST':"
    return render(request, 'shop/bon_commande.html', {
            'commande': commande,
            'articles_liste': articles_liste,
            'pourcentage_actuel': pourcentage_actuel
        })

def voir_bon_livraison(request, commande_id):
    """ Génère la page du Bon de Livraison officiel sans centimes """
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    articles_liste = json.loads(commande.details_json)
    
    # Injection des données entières formatées pour le template du BL
    for art in articles_liste:
        quantite_securisee = int(art.get('qte', art.get('quantite', 1)))
        prix_unitaire = int(float(art.get('prix', 0)))
        brut_ligne = quantite_securisee * prix_unitaire
        
        taux_remise = int(float(art.get('remise_pourcent', 0)))
        montant_remise_ligne = round(brut_ligne * (taux_remise / 100.0))
        total_net_ligne = max(0, brut_ligne - montant_remise_ligne)
        
        # Clés lues par le template HTML du Bon de Livraison
        art['qte_entier'] = quantite_securisee
        art['prix_entier'] = prix_unitaire
        art['remise_pourcent_entier'] = f"{taux_remise} %" if taux_remise > 0 else "0 %"
        art['total_net_entier'] = total_net_ligne
    
    # Données du bloc récapitulatif
    commande.total_brut_entier = int(commande.total_brut)
    commande.montant_remise_global_entier = int(commande.montant_remise)
    commande.total_final_entier = int(commande.total_final)
    commande.montant_remise_global = int(commande.montant_remise)
    
    return render(request, 'shop/bon_livraison.html', {
        'commande': commande,
        'articles_liste': articles_liste
    })

def voir_bon_commande_public(request, commande_id):
    """ Permet au client de visualiser son bon sans aucune décimale avec séparateur de milliers par un point """
    commande = get_object_or_404(CommandeImpression, id=commande_id)
    articles_liste = json.loads(commande.details_json)
    
    for art in articles:
    # 1. Récupération sécurisée de la quantité et du prix unitaire
        qte_valeur = int(art.get('qte', art.get('quantite', 1)))
        prix_unitaire = int(float(art.get('prix', 0)))
        brut_ligne = qte_valeur * prix_unitaire
        
        # 2. Récupération du pourcentage de remise (ex: 5)
        # On cherche d'abord la clé 'remise_pourcent'
        taux_remise = int(float(art.get('remise_pourcent', 0)))
        
        # Si 'remise_pourcent' n'existe pas mais qu'un montant en FCFA est stocké dans 'remise'
        if taux_remise == 0 and int(art.get('remise', 0)) > 0:
            taux_remise = int(round((int(art.get('remise', 0)) / brut_ligne) * 100))
            
        # 3. Calculs des montants nets de la ligne
        montant_remise_ligne = round(brut_ligne * (taux_remise / 100.0))
        total_net_ligne = max(0, brut_ligne - montant_remise_ligne)
        
        # 4. Formatage avec des points pour les milliers (Ex: 45.000)
        prix_formate = f"{prix_unitaire:,}".replace(',', '.')
        total_formate = f"{total_net_ligne:,}".replace(',', '.')
        
        # Préparation du texte en pourcentage pour la colonne
        remise_formatee = f"{taux_remise} %" if taux_remise > 0 else "0 %"

        # 5. Injection directe dans le tableau de ReportLab
        data.append([
            Paragraph(f"<b>{art['titre']}</b>", normal_style),
            Paragraph(f"{prix_formate} FCFA", style_prix_cellule),
            Paragraph(f"x{qte_valeur}", bold_style),
            
            # 🟢 CORRECTION ICI : On remplace l'ancien texte par la variable en pourcentage
            Paragraph(remise_formatee, style_prix_cellule), 
            
            Paragraph(f"{total_formate} FCFA", style_prix_cellule)
        ])

    return render(request, 'shop/bon_commande_public.html', {
        'commande': commande,
        'articles_liste': articles_liste,
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