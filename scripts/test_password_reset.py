"""
Quick script to exercise the password reset flow end-to-end using Django's test client.

Usage:
    DJANGO_SETTINGS_MODULE=realestate.settings python scripts/test_password_reset.py

What it does:
  1) Creates a test user (or reuses if already there).
  2) Hits /users/password_reset/ to request a reset for that email.
  3) Reads the reset link from the in-memory email backend (uses locmem for the test).
  4) Visits the link and posts a new password.
  5) Logs in with the new password to verify success.
"""

import os
import re
import sys
import django
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse


def main():
    # Ensure Django is configured
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realestate.settings")
    django.setup()

    User = get_user_model()
    test_email = "password-reset-test@example.com"
    initial_password = "OldPassw0rd!"
    new_password = "NewPassw0rd!"

    # Create or reset the test user
    user, created = User.objects.get_or_create(email=test_email, defaults={"is_active": True})
    user.set_password(initial_password)
    user.is_active = True
    user.save()

    client = Client()

    reset_url = reverse("password_reset")

    with override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ALLOWED_HOSTS=["*"],
    ):
        # Request reset
        resp = client.post(reset_url, {"email": test_email}, follow=True)
        if resp.status_code >= 400:
            print(f"Failed to submit password reset form (status {resp.status_code})")
            sys.exit(1)

        from django.core import mail

        if not mail.outbox:
            print("No email sent; password reset request did not produce an email.")
            sys.exit(1)

        message = mail.outbox[-1]
        body = message.body

        # Extract reset link (default pattern)
        match = re.search(r"https?://[^\s]+/reset/[^\s]+", body)
        if match:
            reset_link = match.group(0)
        else:
            # Fallback: grab any URL if pattern changed
            any_url = re.search(r"https?://[^\s]+", body)
            if any_url:
                reset_link = any_url.group(0)
                print("Did not match expected /reset/ pattern, using first URL found.")
            else:
                print("Could not find reset link in email body.")
                sys.exit(1)

        print(f"Reset link: {reset_link}")

        # Visit reset link (GET)
        resp = client.get(reset_link, follow=True)
        if resp.status_code >= 400:
            print(f"Reset link GET failed (status {resp.status_code})")
            if hasattr(resp, "redirect_chain"):
                print("Redirect chain:", resp.redirect_chain)
            sys.exit(1)
        # Inspect context for validlink flag or messages
        if resp.context:
            for ctx in resp.context:
                if "validlink" in ctx:
                    print("validlink:", ctx.get("validlink"))
                form = ctx.get("form")
                if form and form.errors:
                    print("Form errors after GET:", form.errors)

        # Submit new password via the link (POST)
        resp = client.post(
            reset_link,
            {"new_password1": new_password, "new_password2": new_password},
            follow=True,
        )
        if resp.status_code >= 400:
            print(f"Reset confirmation POST failed (status {resp.status_code})")
            if hasattr(resp, "redirect_chain"):
                print("Redirect chain:", resp.redirect_chain)
            sys.exit(1)
        # If form errors are present, surface them
        for ctx in resp.context or []:
            form = ctx.get("form")
            if form and form.errors:
                print("Form errors:", form.errors)
                sys.exit(1)

    # Verify password actually changed
    user.refresh_from_db()
    if not user.check_password(new_password):
        print("Password was not updated.")
        sys.exit(1)

    # Verify login with new password works
    logged_in = client.login(username=test_email, password=new_password)
    if not logged_in:
        print("Login with new password failed; reset may not have succeeded.")
        sys.exit(1)

    print("Password reset flow succeeded end-to-end.")


if __name__ == "__main__":
    main()
