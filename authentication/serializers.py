from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from authentication.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'username']


class UserWithTokenSerializer(serializers.ModelSerializer):
    token = serializers.SerializerMethodField() # manually create token
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['token', 'email', 'username', 'password']

    def get_token(self, obj):
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
        payload = jwt_payload_handler(obj)
        token = jwt_encode_handler(payload)
        return token

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        new_user = self.Meta.model(**validated_data)
        if password is not None:
            new_user.set_password(password)
        new_user.save()
        return new_user
