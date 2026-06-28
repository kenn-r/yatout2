from decimal import Decimal
from django.conf import settings
from .models import Produit

class Cart:
    def __init__(self, request):
        """Initialise le panier en utilisant les sessions Django."""
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            # S'il n'y a pas de panier, on en crée un vide
            cart = self.session['cart'] = {}
        self.cart = cart

    def add(self, produit, quantity=1, override_quantity=False):
        """Ajoute un produit au panier ou met à jour sa quantité."""
        produit_id = str(produit.id)
        if produit_id not in self.cart:
            self.cart[produit_id] = {
                'quantity': 0,
                'price': str(produit.prix)
            }
        
        if override_quantity:
            self.cart[produit_id]['quantity'] = quantity
        else:
            self.cart[produit_id]['quantity'] += quantity
        self.save()

    def save(self):
        """Marque la session comme modifiée pour qu'elle soit sauvegardée."""
        self.session.modified = True

    def remove(self, produit):
        """Supprime un produit du panier."""
        produit_id = str(produit.id)
        if produit_id in self.cart:
            del self.cart[produit_id]
            self.save()

    def __iter__(self):
        """Parcourt les articles du panier et récupère les objets de la base de données."""
        produit_ids = self.cart.keys()
        # On récupère tous les produits d'un coup et on les met dans un dictionnaire pour y accéder vite
        produits = {str(p.id): p for p in Produit.objects.filter(id__in=produit_ids)}
        
        for produit_id, item in self.cart.items():
            # On vérifie si le produit existe bien encore en base de données
            if produit_id in produits:
                item['produit'] = produits[produit_id]
                item['price'] = Decimal(item['price'])
                item['total_price'] = item['price'] * item['quantity']
                yield item

                
    def __len__(self):
        """Compte le nombre total d'articles dans le panier."""
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        """Calcule le coût total de tous les articles du panier."""
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())

    def clear(self):
        """Vide complètement le panier."""
        del self.session['cart']
        self.save()