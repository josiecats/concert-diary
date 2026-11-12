from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, render


def visible_owner(request, username):
    """Return (owner, None) if the viewer may see this diary, else (owner, 403 response).

    Private profiles are visible to their owner only (US-2), including the diary and map JSON.
    """
    owner = get_object_or_404(get_user_model().objects.select_related("profile"), username=username)
    if owner.profile.visible_to(request.user):
        return owner, None
    return owner, render(request, "accounts/private.html", {"owner": owner}, status=403)
