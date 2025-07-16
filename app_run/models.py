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
