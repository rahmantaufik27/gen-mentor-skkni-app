"""
Temporary admin authentication.

Hardcoded credentials for now (no admin-users table yet) - kept in its own
service, separate from AuthenticationService (learner auth), so replacing
this with a real admin-accounts table later only touches this one file, not
the controller/route layer or the learner auth flow.
"""

ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "adminadmin"


class AdminAuthService:
    """Verifies admin credentials. Temporary/hardcoded - see module docstring."""

    @staticmethod
    def verify_credentials(email: str, password: str) -> bool:
        """
        Check email/password against the temporary hardcoded admin account.

        Args:
            email: Submitted admin email
            password: Submitted admin password

        Returns:
            True if credentials match
        """
        return email.strip().lower() == ADMIN_EMAIL and password == ADMIN_PASSWORD
