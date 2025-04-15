from django.db import models


class Document(models.Model):
    url = models.URLField(max_length=512)
    content_hash = models.CharField(max_length=768, unique=True)  # Use SHA-256 to identify a document
    title = models.TextField(blank=True)
    description = models.TextField(blank=True)
    content = models.TextField()
    crawl_time = models.DateTimeField(auto_now_add=True)
    tf_max = models.IntegerField(default=1)
    last_modify = models.DateTimeField(auto_now_add=True)
    page_size = models.IntegerField(default=0)
    pr_score = models.FloatField(default=0.00)
    hits_score = models.FloatField(default=0.00)

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

class TermCluster(models.Model):
    term = models.OneToOneField(Term, on_delete=models.CASCADE, primary_key=True)
    cluster = models.IntegerField()

    class Meta:
        indexes = [
            models.Index(fields=['cluster']),
        ]

class InvertedIndex(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    tf = models.IntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name='unique_term_doc',
                fields=['term_id', 'document_id'],
            )
        ]


class UrlLinkage(models.Model):
    from_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='from_document')
    to_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='to_document')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name='unique_from_to',
                fields=['from_document', 'to_document'],
            )
        ]
class ForwardIndex(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    position = models.IntegerField(blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name='unique_term_position',
                fields=['term_id', 'document_id','position'],
            )
        ]

