from django.db import models

class TriageRecord(models.Model):
    ticket_key = models.CharField(max_length=50)
    request    = models.TextField()
    response   = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ticket_key} - {self.created_at}"