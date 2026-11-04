from django import forms

from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "avatar_url", "bio", "home_city", "is_private"]
        labels = {
            "display_name": "Display name",
            "avatar_url": "Avatar image URL",
            "bio": "Bio",
            "home_city": "Home city",
            "is_private": "Make my profile private",
        }
        help_texts = {
            "avatar_url": "Paste a link to a square image. Photo uploads come later.",
            "is_private": "Only you will see your profile, diary and map.",
        }
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "field", "autocomplete": "name"}),
            "avatar_url": forms.URLInput(attrs={"class": "field", "placeholder": "https://"}),
            "bio": forms.Textarea(attrs={"class": "field", "rows": 3}),
            "home_city": forms.TextInput(attrs={"class": "field", "placeholder": "Syracuse, NY"}),
        }
