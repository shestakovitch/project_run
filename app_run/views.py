from django.contrib.auth import authenticate
from django.core.serializers import serialize
from rest_framework import viewsets, status
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from geopy.distance import geodesic
from django.db.models import Sum, Count, Q, Avg, Prefetch
import openpyxl

from .models import Run, User, AthleteInfo, Challenge, Position, CollectibleItem, Subscribe
from .serializers import RunSerializer, UserSerializer, AthleteInfoSerializer, ChallengeSerializer, PositionSerializer, \
    CollectibleItemSerializer, UserDetailSerializer, AthleteDetailSerializer, CoachDetailSerializer


@api_view(['GET'])
def company_details(request):
    details = {'company_name': settings.COMPANY_NAME,
               'slogan': settings.SLOGAN,
               'contacts': settings.CONTACTS}

    return Response(details)


class UserPagination(PageNumberPagination):
    page_size_query_param = 'size'  # Разрешаем изменять количество объектов через query параметр size в url


class RunPagination(PageNumberPagination):
    page_size_query_param = 'size'  # Разрешаем изменять количество объектов через query параметр size в url


class RunViewSet(viewsets.ModelViewSet):
    queryset = Run.objects.select_related('athlete').all()
    serializer_class = RunSerializer
    filter_backends = [DjangoFilterBackend,
                       OrderingFilter]  # Указываем какой класс будет использоваться для фильтра и сортировки
    pagination_class = RunPagination  # Указываем пагинацию

    filterset_fields = ['status', 'athlete']  # Поля, по которым будет происходить фильтрация
    ordering_fields = ['created_at']  # Поля по которым будет возможна сортировка


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    filter_backends = [SearchFilter, OrderingFilter]  # Подключаем SearchFilter здесь
    pagination_class = UserPagination  # Указываем пагинацию

    search_fields = ['first_name', 'last_name']  # Поля по котором будет производиться поиск
    ordering_fields = ['date_joined']  # Поля по которым будет возможна сортировка

    def get_queryset(self):
        qs = User.objects.filter(is_superuser=False)  # Отфильтровываем superuser
        user_type = self.request.query_params.get('type')

        if user_type == 'coach':
            qs = qs.filter(is_staff=True)
        elif user_type == 'athlete':
            qs = qs.filter(is_staff=False)

        # Для решения проблемы N+1 вычисляем кол-во finished забегов здесь, а не в UserSerializer при помощи метода
        # get_runs_finished
        # Аннотация вычисляемых полей: количество finished забегов и средний рейтинг
        qs = qs.annotate(
            runs_finished=Count('run', filter=Q(run__status='finished')),
            rating=Avg('subscribers__rating', filter=Q(subscribers__rating__isnull=False)),
        )
        # Предзагрузка подписок и подписчиков с select_related для ForeignKey
        subscription_prefetch = Prefetch(
            'subscriptions',
            queryset=Subscribe.objects.select_related('coach', 'athlete')
            .only('id', 'coach_id', 'athlete_id', 'rating'),
            to_attr='prefetched_subscriptions'
        )
        subscriber_prefetch = Prefetch(
            'subscribers',
            queryset=Subscribe.objects.select_related('coach', 'athlete')
            .only('id', 'coach_id', 'athlete_id', 'rating'),
            to_attr='prefetched_subscribers'
        )
        # Обязательно предзагружаем связанные коллекции, чтобы избежать N+1 в сериализаторах
        qs = qs.prefetch_related(subscription_prefetch, subscriber_prefetch)
        # Предзагрузить collected_items для UserDetailSerializer, чтобы избежать лишних запросов в detail
        if self.action == 'retrieve':
            qs = qs.prefetch_related('collected_items')
        # Ограничиваем поля User, учитывая, что сериализаторы используют именно эти данные
        qs = qs.only('id', 'username', 'first_name', 'last_name', 'date_joined', 'is_staff')
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':  # Возвращаем детализированный сериализатор для метода retrieve (GET с указанием id)
            user = self.get_object()
            if user.is_staff:
                return CoachDetailSerializer
            else:
                return AthleteDetailSerializer
        return UserDetailSerializer


class StartRunAPIView(APIView):
    def post(self, request, run_id):
        run = get_object_or_404(Run, id=run_id)

        if run.status in ('in_progress', 'finished'):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        run.status = 'in_progress'
        run.save()
        return Response(RunSerializer(run).data, status=status.HTTP_200_OK)


class StopRunAPIView(APIView):
    def post(self, request, run_id):
        run = get_object_or_404(Run, id=run_id)

        if run.status in ('init', 'finished'):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        positions = Position.objects.filter(run=run).order_by('date_time')

        if positions.count() >= 2:
            total_time = (positions.last().date_time - positions.first().date_time).total_seconds()

            if total_time > 0:
                run.run_time_seconds = int(total_time)
                avg_speed = positions.aggregate(avg_speed=Avg('speed'))['avg_speed']
                run.speed = round(avg_speed, 2) if avg_speed else 0.0
            else:
                run.run_time_seconds = 0.0
                run.speed = 0.0
        else:
            run.run_time_seconds = 0.0
            run.speed = 0.0

        run.distance = positions.last().distance if positions.exists() else 0.0
        run.status = 'finished'
        run.save()

        # Челлендж "Сделай 10 Забегов!"
        finished_count = Run.objects.filter(athlete=run.athlete, status='finished').count()

        if finished_count == 10:
            Challenge.objects.get_or_create(athlete=run.athlete, full_name='Сделай 10 Забегов!')

        # Челлендж "Пробеги 50 километров!"
        finished_km = Run.objects.filter(athlete=run.athlete, status='finished').aggregate(Sum('distance'))[
            'distance__sum']

        if finished_km >= 50:
            Challenge.objects.get_or_create(athlete=run.athlete, full_name='Пробеги 50 километров!')

        # Челлендж "2 километра за 10 минут!"
        if run.distance >= 2 and run.run_time_seconds <= 600:
            Challenge.objects.get_or_create(athlete=run.athlete, full_name='2 километра за 10 минут!')

        return Response(RunSerializer(run).data, status=status.HTTP_200_OK)


class AthleteInfoAPIView(APIView):
    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        athlete_info, created = AthleteInfo.objects.get_or_create(user=user)

        return Response(AthleteInfoSerializer(athlete_info).data, status=status.HTTP_200_OK)

    def put(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        data = request.data.copy()
        data['user'] = user.id

        try:
            weight = float(data.get('weight'))
            if weight <= 0 or weight >= 900:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        except(TypeError, ValueError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        athlete_info, created = AthleteInfo.objects.update_or_create(user=user, defaults={'weight': data.get('weight'),
                                                                                          'goals': data.get('goals')})

        return Response(AthleteInfoSerializer(athlete_info).data, status=status.HTTP_201_CREATED)


class ChallengeAPIView(APIView):
    def get(self, request):
        athlete_id = request.query_params.get('athlete')

        if athlete_id:
            challenges = Challenge.objects.filter(athlete_id=athlete_id)
        else:
            challenges = Challenge.objects.all()

        return Response(ChallengeSerializer(challenges, many=True).data, status=status.HTTP_200_OK)


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer

    def get_queryset(self):
        run_id = self.request.query_params.get('run')

        if run_id:
            return self.queryset.filter(run_id=run_id)

        return self.queryset

    def perform_create(self, serializer):
        data = serializer.validated_data
        run = data['run']
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        date_time = data['date_time']

        prev = Position.objects.filter(run=run, date_time__lt=date_time).order_by('-date_time').first()

        if prev:
            prev_point = (prev.latitude, prev.longitude)
            curr_point = (latitude, longitude)

            segment_distance = geodesic(prev_point, curr_point).km
            time_delta = (date_time - prev.date_time).total_seconds()
            speed = segment_distance * 1000 / time_delta if time_delta > 0 else 0.0
            distance = prev.distance + segment_distance
        else:
            speed = 0.0
            distance = 0.0

        position = serializer.save(speed=round(speed, 2), distance=round(distance, 2))

        # Проверяем есть ли CollectibleItem на расстоянии <= 100 метров
        user = position.run.athlete
        user_location = (position.latitude, position.longitude)
        for item in CollectibleItem.objects.all():
            item_location = (item.latitude, item.longitude)
            if geodesic(user_location, item_location).meters <= 100:
                item.collected_by.add(user)


class CollectibleItemViewSet(viewsets.ModelViewSet):
    queryset = CollectibleItem.objects.all()
    serializer_class = CollectibleItemSerializer


class UploadFileView(APIView):
    def post(self, request):
        upload_file = request.FILES.get('file')

        if not upload_file or not upload_file.name.endswith('xlsx'):
            return Response({'error': 'File should be .xlsx'}, status=400)

        wb = openpyxl.load_workbook(upload_file)
        sheet = wb.active

        invalid_rows = []

        # Получаем уже существующие пары (name, uid) для проверки дубликатов
        existing_items = set(
            CollectibleItem.objects.values_list('name', 'uid')
        )

        # Для отслеживания дубликатов внутри файла
        file_items = set()

        for row in sheet.iter_rows(min_row=2, values_only=True):
            name, uid, value, latitude, longitude, picture = row

            # Проверяем на дубликаты (name, uid) в базе и в файле
            if (name, uid) in existing_items or (name, uid) in file_items:
                invalid_rows.append(list(row))
                continue

            data = {
                'name': name,
                'uid': uid,
                'value': value,
                'latitude': latitude,
                'longitude': longitude,
                'picture': picture,
            }

            serializer = CollectibleItemSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                # Добавляем в множества, чтобы не загружать дубликаты из файла
                existing_items.add((name, uid))
                file_items.add((name, uid))
            else:
                invalid_rows.append(list(row))

        return Response(invalid_rows, status=200)


class SubscribeAPIView(APIView):
    def post(self, request, id):
        athlete_id = request.data.get('athlete')
        coach_id = id

        athlete = get_object_or_404(User, id=athlete_id)
        coach = get_object_or_404(User, id=coach_id)

        if not athlete:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if not coach:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not coach.is_staff:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if Subscribe.objects.filter(athlete=athlete, coach=coach).exists():
            return Response(status=status.HTTP_400_BAD_REQUEST)

        Subscribe.objects.create(athlete=athlete, coach=coach)
        return Response(status=status.HTTP_200_OK)


class ChallengesSummaryAPIView(APIView):
    def get(self, request):
        challenges = Challenge.objects.select_related('athlete')

        summary = {}
        for challenge in challenges:
            athlete = challenge.athlete
            summary.setdefault(challenge.full_name, []).append({
                'id': athlete.id,
                'full_name': f'{athlete.first_name} {athlete.last_name}',
                'username': athlete.username
            })

        result = []
        for full_name, athletes in summary.items():
            result.append({
                'name_to_display': full_name,
                'athletes': athletes
            })

        return Response(result)


class RateCoachAPIView(APIView):
    def post(self, request, coach_id):
        coach = get_object_or_404(User.objects.filter(is_staff=True), id=coach_id)

        athlete_id = request.data.get('athlete')
        rating_raw = request.data.get('rating')

        if not athlete_id or not rating_raw:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if not 1 <= rating <= 5:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        athlete = get_object_or_404(User.objects.filter(is_staff=False), id=athlete_id)

        # Обновляем рейтинг одним запросом
        updated_count = Subscribe.objects.filter(coach=coach, athlete=athlete).update(rating=rating)
        if updated_count == 0:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)
