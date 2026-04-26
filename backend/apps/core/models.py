from django.db import models

class Mood(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)
    mood_type = models.CharField(max_length=50)
    intensity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.mood_type} ({self.intensity})"