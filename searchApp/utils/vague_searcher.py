# -*- coding:utf-8 -*-　
# Last modify: Liu Wentao
# Description: Vague search based on semantic expansion
# Note:


from django.db.models import Sum, Q
from searchApp.models import Term, TermCluster, InvertedIndex
from sentence_transformers import SentenceTransformer
import joblib
import numpy as np
import hdbscan


def expand_terms(term_list):
    expanded_terms = []

    try:
        # Load models once
        model = SentenceTransformer('model_cache/')
        clusterer = joblib.load('hdbscan_model.pkl')

        # Preload all terms and embeddings for noise handling
        all_terms = list(Term.objects.values_list('id', 'term'))
        all_term_texts = [t[1] for t in all_terms]
        all_embeddings = model.encode(all_term_texts) if all_terms else []

        # Get existing terms in batch
        existing_terms = Term.objects.filter(term__in=term_list)
        term_clusters = {
            t.term: t.termcluster.cluster
            for t in existing_terms.select_related('termcluster')
        }

        for term in term_list:
            cluster = term_clusters.get(term)

            if not cluster:
                # Handle new term
                query_embedding = model.encode([term])[0]
                query_embedding = query_embedding / np.linalg.norm(query_embedding)

                # Predict cluster
                cluster, _ = hdbscan.approximate_predict(clusterer, query_embedding.reshape(1, -1))
                cluster = int(cluster[0])

                # Handle noise
                if cluster == -1 and all_embeddings.any():
                    similarities = np.dot(all_embeddings, query_embedding)
                    nearest_idx = np.argmax(similarities)
                    cluster = TermCluster.objects.get(
                        term_id=all_terms[nearest_idx][0]
                    ).cluster

            if cluster and cluster != -1:
                # Get top terms in cluster
                related = InvertedIndex.objects.filter(
                    term__termcluster__cluster=cluster
                ).exclude(
                    Q(term__term=term) | Q(term__term__in=expanded_terms)
                ).values('term__term').annotate(
                    total_tf=Sum('tf')
                ).order_by('-total_tf')[:3]

                expanded_terms.append(term)
                expanded_terms.extend([t['term__term'] for t in related])
            else:
                expanded_terms.append(term)

    except (FileNotFoundError, TermCluster.DoesNotExist):
        return term_list

    return list(dict.fromkeys(expanded_terms))