from django import template
from allauth.socialaccount.adapter import get_adapter

register = template.Library()


@register.simple_tag(takes_context=True)
def google_login_enabled(context):
    """True when a Google OAuth app is configured (client ID set in .env) (US-1)."""
    return bool(get_adapter().list_apps(context.get("request"), provider="google"))
