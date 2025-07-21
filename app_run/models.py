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
