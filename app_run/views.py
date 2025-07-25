from django.contrib.auth import authenticate
from django.core.serializers import serialize
from rest_framework import viewsets, status
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from geopy.distance import geodesic
from django.db.models import Sum
import openpyxl
from rest_framework.exceptions import PermissionDenied

from .models import Run, User, AthleteInfo, Challenge, Position, CollectibleItem
from .serializers import RunSerializer, UserSerializer, AthleteInfoSerializer, ChallengeSerializer, PositionSerializer, \
    CollectibleItemSerializer, UserDetailSerializer


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

    def perform_create(self, serializer):
        # Больше не проверяем авторизацию, просто сохраняем
        serializer.save()


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    filter_backends = [SearchFilter, OrderingFilter]  # Подключаем SearchFilter здесь
    pagination_class = UserPagination  # Указываем пагинацию

    search_fields = ['first_name', 'last_name']  # Поля по котором будет производиться поиск
    ordering_fields = ['date_joined']  # Поля по которым будет возможна сортировка

    def get_queryset(self):
        qs = User.objects.filter(is_superuser=False)
        user_type = self.request.query_params.get('type')

        if user_type == 'coach':
            qs = qs.filter(is_staff=True)
        elif user_type == 'athlete':
            qs = qs.filter(is_staff=False)

        return qs
    
    def get_serializer_class(self):
        if self.action == 'retrieve': # Возвращаем детализированный сериализатор для метода retrieve (GET с указанием id)
            return UserDetailSerializer
        
        return UserSerializer


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

        positions = Position.objects.filter(run=run).values_list('latitude', 'longitude')
        total_distance = 0.0

        if len(positions) >= 2:
            for i in range(1, len(positions)):
                total_distance += geodesic(positions[i - 1], positions[i]).km

        run.distance = round(total_distance, 2)
        run.status = 'finished'
        run.save()

        finished_count = Run.objects.filter(athlete=run.athlete, status='finished').count()

        if finished_count == 10:
            Challenge.objects.get_or_create(athlete=run.athlete, full_name='Сделай 10 Забегов!')

        finished_km = Run.objects.filter(athlete=run.athlete, status='finished').aggregate(Sum('distance'))[
            'distance__sum']

        if finished_km >= 50:
            Challenge.objects.get_or_create(athlete=run.athlete, full_name='Пробеги 50 километров!')

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

    def check_and_collect_items(position):
        user = position.run.athlete
        user_location = (position.latitude, position.longitude)
        for item in CollectibleItem.objects.all():
            item_location = (item.latitude, item.longitude)
            if geodesic(user_location, item_location).meters <= 100:
                item.collected_by.add(user)

    def perform_create(self, serializer):
        position = serializer.save()
        self.check_and_collect_items(position)

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
