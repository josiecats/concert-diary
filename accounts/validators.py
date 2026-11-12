from django.core.validators import RegexValidator

# Usernames appear in profile URLs (/u/<username>/), so keep them URL-safe.
username_validators = [
    RegexValidator(
        r"^[A-Za-z0-9_]{3,30}$",
        "Use 3 to 30 letters, numbers or underscores.",
    )
]
