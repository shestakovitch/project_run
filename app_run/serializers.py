from dataclasses import field
from rest_framework import serializers
from .models import Run, User, AthleteInfo, Challenge, Position, CollectibleItem


class UserSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()  # Так мы задаем вычисляемое поле

    # Если не поставить read_only=True, DRF подумает, что это поле должно приходить в теле запроса при
    # создании/обновлении — и может вызвать ошибку вроде: "runs_finished" is a required field.
    runs_finished = serializers.IntegerField(read_only=True)
    rating = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'date_joined', 'username', 'last_name', 'first_name',
                  'type',  # Добавляем поля, которых нет в модели. type вычисляем через get_type
                  'runs_finished', # runs_finished вычисляем во UserViewSet, чтобы избежать проблемы N+1
                  'rating']

    def get_type(self, obj):  # Определяем метод, который вычисляет значение поля
        return 'coach' if obj.is_staff else 'athlete'


class AthleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'last_name', 'first_name']


class RunSerializer(serializers.ModelSerializer):
    athlete_data = AthleteSerializer(source='athlete', read_only=True)
    athlete = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)

    class Meta:
        model = Run
        fields = ['id', 'created_at', 'comment', 'athlete', 'athlete_data', 'status', 'distance', 'run_time_seconds',
                  'speed']


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
    date_time = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%f',
                                          input_formats=['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'])

    class Meta:
        model = Position
        fields = ['id', 'run', 'latitude', 'longitude', 'date_time', 'speed', 'distance']
        read_only_fields = ['speed', 'distance']

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
        fields = ['id', 'name', 'uid', 'latitude', 'longitude', 'picture', 'value']


class UserDetailSerializer(UserSerializer):  # Наследуемся от Базового сериализатора
    items = CollectibleItemSerializer(source='collected_items', many=True)  # Новое поле


    class Meta(UserSerializer.Meta):  # Наследуем настройки Meta из родительского сериализатора
        fields = UserSerializer.Meta.fields + ['items']  # Так добавляются поля


class AthleteDetailSerializer(UserSerializer):
    items = CollectibleItemSerializer(read_only=True, many=True)
    coach = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = UserSerializer.Meta.fields + ['items', 'coach']

    def get_coach(self, obj):
        subscribe = obj.subscriptions.last()
        return subscribe.coach.id if subscribe else None


class CoachDetailSerializer(UserSerializer):
    athletes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = UserSerializer.Meta.fields + ['athletes']

    def get_athletes(self, obj):
        subscribes = obj.subscribers.all()
        athletes = [subscribe.athlete.id for subscribe in subscribes]
        return athletes
