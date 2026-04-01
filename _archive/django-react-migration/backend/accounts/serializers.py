from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import CustomUser


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["short_name"] = user.username
        token["worker_role"] = user.worker_role or ""
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data["user"] = {
            "username": user.username,
            "full_name": user.full_name,
            "worker_role": user.worker_role,
        }
        return data


class UserMeSerializer(serializers.ModelSerializer):
    short_name = serializers.CharField(source="username", read_only=True)

    class Meta:
        model = CustomUser
        fields = ("short_name", "full_name", "worker_role", "tarif_per_hour", "enabled")
