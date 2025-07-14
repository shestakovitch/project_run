from rest_framework import serializers
from .models import Run, User


class RunSerializer(serializers.ModelSerializer):
    class Meta:
        model = Run
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

    def get_type(self, obj):
        return 'coach' if obj.is_staff else 'athlete'