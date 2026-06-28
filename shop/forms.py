from django import forms
from django.contrib.auth.models import User
from .models import Vendeur, Produit

class InscriptionVendeurForm(forms.ModelForm):
    # 1. AJOUT OBLIGATOIRE des champs de création du compte utilisateur Django
    username = forms.CharField(
        label="Nom d'utilisateur",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full p-2 border rounded-md border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500'
        })
    )
    
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(attrs={
            'class': 'w-full p-2 border rounded-md border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500'
        })
    )
    
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full p-2 border rounded-md border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500'
        })
    )

    class Meta:
        model = Vendeur
        fields = ['nom_boutique', 'description', 'devise']
        widgets = {
            'nom_boutique': forms.TextInput(attrs={
                'class': 'w-full p-2 border rounded-md border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full p-2 border rounded-md border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500'
            }),
            'devise': forms.Select(attrs={
                'class': 'w-full p-2 border rounded-md border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500'
            }),
        }

class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        # 🛠️ AJOUT de 'ancien_prix' dans la liste des champs affichés
        fields = ['nom', 'description', 'prix', 'ancien_prix', 'stock', 'image']
        
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'w-full p-2 border rounded-md border-purple-300'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'w-full p-2 border rounded-md border-purple-300'}),
            'prix': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full p-2 border rounded-md border-purple-300', 'placeholder': 'Prix actuel de vente'}),
            
            # 🛠️ AJOUT du widget pour l'ancien prix avec les classes de votre thème mauve
            'ancien_prix': forms.NumberInput(attrs={
                'step': '0.01', 
                'class': 'w-full p-2 border rounded-md border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500',
                'placeholder': 'Ancien prix barré (Optionnel)'
            }),
            
            'stock': forms.NumberInput(attrs={'min': '0', 'class': 'w-full p-2 border rounded-md border-purple-300'}),
            'image': forms.ClearableFileInput(attrs={'class': 'w-full p-1 text-sm'}),
        }

    # 💡 BONUS SÉCURITÉ : Empêche le vendeur de tricher sur la promotion
    def clean(self):
        cleaned_data = super().clean()
        prix = cleaned_data.get('prix')
        ancien_prix = cleaned_data.get('ancien_prix')

        if ancien_prix and prix and ancien_prix <= prix:
            raise forms.ValidationError(
                "L'ancien prix (barré) doit obligatoirement être supérieur au prix actuel pour afficher une réduction valide."
            )
        return cleaned_data