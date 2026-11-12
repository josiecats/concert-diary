from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from shows import top3
from shows.models import Attendance
from shows.stats import lifetime_stats

from .access import visible_owner
from .forms import ProfileForm


def home(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile", request.user.username)
    demo = get_user_model().objects.filter(username="demo", profile__is_private=False).first()
    return render(request, "accounts/landing.html", {"demo": demo, "top3": top3.top3_for(demo) if demo else []})


def profile(request, username):
    owner, denied = visible_owner(request, username)
    if denied:
        return denied
    logs = Attendance.objects.with_related().filter(user=owner)
    context = {
        "owner": owner,
        "profile": owner.profile,
        "is_owner": request.user == owner,
        "stats": lifetime_stats(owner),
        "top3": top3.top3_for(owner),
        "not_on_map": [a for a in logs.filter(event__venue__lat__isnull=True)],
        "recent": logs.order_by("-created_at")[:5],
    }
    return render(request, "accounts/profile.html", context)


@login_required
def settings_view(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("accounts:profile", request.user.username)
    return render(request, "accounts/settings.html", {"form": form})


@login_required
def onboarding(request):
    return render(request, "accounts/onboarding.html")
