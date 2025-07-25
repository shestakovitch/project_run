from dataclasses import field
from rest_framework import serializers
from .models import Run, User, AthleteInfo, Challenge, Position, CollectibleItem


class UserSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    runs_finished = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'date_joined', 'username', 'last_name', 'first_name', 'type', 'runs_finished']

    def get_type(self, obj):
        return 'coach' if obj.is_staff else 'athlete'

    def get_runs_finished(self, obj):
        return obj.run_set.filter(status='finished').count()


class AthleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'last_name', 'first_name']


class RunSerializer(serializers.ModelSerializer):
    athlete_data = AthleteSerializer(source='athlete', read_only=True)
    # athlete = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)

    class Meta:
        model = Run
        fields = ['created_at', 'comment', 'athlete_data', 'status', 'distance']


class AthleteInfoSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = AthleteInfo
        fields = ['user_id', 'goals', 'weight']


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ['athlete', 'full_name']


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'run', 'latitude', 'longitude']

    def validate_run(self, run):
        if run.status != 'in_progress':
            raise serializers.ValidationError('Run must be in progress!')

        return run

    def validate_latitude(self, latitude):
        if not -90.0 <= latitude <= 90.0:
            raise serializers.ValidationError('Latitude must be between -90.0 and 90.0!')

        return round(latitude, 4)

    def validate_longitude(self, longitude):
        if not -180.0 <= longitude <= 180.0:
            raise serializers.ValidationError('Longitude must be between -180.0 and 180.0!')

        return round(longitude, 4)


class CollectibleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectibleItem
        fields = ['name', 'uid', 'latitude','longitude', 'picture', 'value']


class UserDetailSerializer(UserSerializer): # Наследуемся от Базового сериализатора
    items = CollectibleItemSerializer(source='collected_items', many=True) # Новое поле

    class Meta(UserSerializer.Meta): # Наследуем настройки Meta из родительского сериализатора
        fields = UserSerializer.Meta.fields + ['items'] # Так добавляются поля
