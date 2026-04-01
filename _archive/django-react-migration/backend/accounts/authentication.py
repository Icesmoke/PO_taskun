from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .utils import verify_legacy_password

UserModel = get_user_model()


class LegacyAwareBackend(ModelBackend):
    """
    Стандартная проверка пароля Django; если задан legacy_password_hash — проверка как во Flask,
    затем перенос в PBKDF2.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            return None

        if user.legacy_password_hash:
            if not verify_legacy_password(user.legacy_password_hash, password):
                return None
            if not self.user_can_authenticate(user):
                return None
            user.set_password(password)
            user.legacy_password_hash = ""
            user.save(update_fields=["password", "legacy_password_hash"])
            return user

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        if not getattr(user, "enabled", True):
            return False
        return super().user_can_authenticate(user)
