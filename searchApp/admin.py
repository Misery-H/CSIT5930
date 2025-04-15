from django.contrib import admin

# Register your models here.
from .models import Document, Term, InvertedIndex, UrlLinkage,ForwardIndex, TermCluster

admin.site.register(Document)
admin.site.register(Term)
admin.site.register(InvertedIndex)
admin.site.register(UrlLinkage)
admin.site.register(ForwardIndex)
admin.site.register(TermCluster)

