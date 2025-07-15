from rest_framework import serializers
from .models import Run, User


class UserSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'last_name', 'first_name']

    def get_type(self, obj):
        return 'coach' if obj.is_staff else 'athlete'


class RunSerializer(serializers.ModelSerializer):
    athlete_data = UserSerializer(source='athlete', read_only=True)

    class Meta:
        model = Run
        fields = ['athlete_data']
