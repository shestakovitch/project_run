from django.db import models
from django.contrib.auth.models import User


class Run(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField()
    athlete = models.ForeignKey(User, on_delete=models.CASCADE)

    status_choices = [('init', 'Init'),
                      ('in_progress', 'In Progress'),
                      ('finished', 'Finished')
                      ]

    status = models.CharField(max_length=20, choices=status_choices, default='init')
    distance = models.FloatField(null=True, blank=True, default=0.0)
    run_time_seconds = models.IntegerField(null=True, blank=True)


class AthleteInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    weight = models.PositiveIntegerField(null=True, blank=True)
    goals = models.TextField(null=True, blank=True)


class Challenge(models.Model):
    athlete = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)


class Position(models.Model):
    run = models.ForeignKey(Run, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=8, decimal_places=4)
    longitude = models.DecimalField(max_digits=9, decimal_places=4)
    date_time = models.DateTimeField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)


class CollectibleItem(models.Model):
    name = models.CharField(max_length=255)
    uid = models.CharField(max_length=100, unique=True)
    latitude = models.DecimalField(max_digits=8, decimal_places=4)
    longitude = models.DecimalField(max_digits=9, decimal_places=4)
    picture = models.URLField()
    value = models.IntegerField()
    collected_by = models.ManyToManyField(User, related_name='collected_items', blank=True)
