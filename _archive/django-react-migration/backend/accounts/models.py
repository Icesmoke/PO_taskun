from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Логин — short_name (поле username), как во Flask.
    legacy_password_hash — сырое значение из taskun.sqlite до первого успешного входа в Django.
    """

    email = models.EmailField(blank=True)
    full_name = models.CharField("ФИО", max_length=255, blank=True)
    worker_role = models.CharField("Роль", max_length=128, blank=True)
    tarif_per_hour = models.FloatField("Тариф/час", null=True, blank=True)
    enabled = models.BooleanField("Активен", default=True)
    legacy_password_hash = models.TextField(
        "Пароль (legacy)",
        blank=True,
        help_text="Из SQLite до миграции на Django PBKDF2 при первом входе",
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self) -> str:
        return self.username
