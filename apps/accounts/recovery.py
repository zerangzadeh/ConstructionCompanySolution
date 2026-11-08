from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountRecoveryTokens(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        value = super()._make_hash_value(user, timestamp)
        if user.auth_session_revision is not None:
            return f"{value}:{user.auth_session_revision}"
        return value


account_recovery_tokens = AccountRecoveryTokens()
