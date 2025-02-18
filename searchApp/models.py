from django.db import models


class Document(models.Model):
    url = models.URLField(max_length=512)
    content_hash = models.CharField(max_length=768, unique=True)  # Use SHA-256 to identify a document
    title = models.TextField(blank=True)
    description = models.TextField(blank=True)
    content = models.TextField()
    crawl_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['content_hash']),
            models.Index(fields=['crawl_time']),
        ]


class Term(models.Model):
    term = models.CharField(max_length=255, unique=True)
    df = models.IntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=['term']),
        ]


class InvertedIndex(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    tf_max = models.IntegerField(default=1)
    tf = models.IntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=['term']),
        ]
