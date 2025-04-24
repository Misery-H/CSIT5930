import os

# from sklearn.cluster._hdbscan import hdbscan
import hdbscan
import joblib
import numpy as np
import pymysql
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'django',
    'password': os.getenv("MYSQL_PASSWORD"),
    'db': 'search_engine',
    'charset': 'utf8mb4'
}

MODEL_NAME = 'all-MiniLM-L6-v2'
MODEL_CACHE = 'model_cache/'
CLUSTERER_FILE = 'hdbscan_model.pkl'


def update_term_clusters():
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            # Get all terms with their document frequency
            cursor.execute("""
                SELECT t.id, t.term, t.df 
                FROM searchApp_term t
                ORDER BY t.df DESC
            """)
            rows = cursor.fetchall()

            if not rows:
                return

            # Unpack tuple results
            term_ids = [row[0] for row in rows]
            term_texts = [row[1] for row in rows]
            doc_freqs = np.array([row[2] for row in rows], dtype=np.float32)

            # Generate embeddings with frequency weighting
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embeddings = model.encode(term_texts, show_progress_bar=True)

            # Apply DF weighting
            weighted_embeddings = embeddings * doc_freqs[:, np.newaxis]

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=3,
                cluster_selection_method='leaf',
                prediction_data=True
            )
            clusters = clusterer.fit_predict(weighted_embeddings)
            unique_clusters = np.unique(clusters)
            print(f"Found {len(unique_clusters)} clusters with {sum(clusters == -1)} noise points")

            # Save models
            joblib.dump(clusterer, CLUSTERER_FILE)
            model.save(MODEL_CACHE)

            # Update database
            update_sql = """
                            INSERT INTO searchApp_termcluster (term_id, cluster)
                            VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE cluster = VALUES(cluster)
                        """
            # Convert -1 (noise) to unique cluster IDs
            cluster_ids = [int(c) if c != -1 else int(1000000 + i)
                           for i, c in enumerate(clusters)]
            batch_data = list(zip(term_ids, cluster_ids))

            cursor.executemany(update_sql, batch_data)
            conn.commit()

    finally:
        conn.close()


def expand_query(query_term):
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            # Check if term exists
            cursor.execute("""
                SELECT cluster FROM searchApp_termcluster
                JOIN searchApp_term ON searchApp_termcluster.term_id = searchApp_term.id
                WHERE searchApp_term.term = %s
                LIMIT 1
            """, (query_term,))
            result = cursor.fetchone()

            if result:
                print(f"Term {query_term} hit vocabulary")
                cluster_id = result[0]
            else:
                print(f"Term {query_term} doesn't hit vocabulary")
                # Handle new term
                model = SentenceTransformer(MODEL_CACHE)
                clusterer = joblib.load(CLUSTERER_FILE)

                # Encode and normalize
                query_embedding = model.encode([query_term])
                query_embedding = query_embedding / np.linalg.norm(query_embedding)

                # Predict cluster
                cluster_id, _ = hdbscan.approximate_predict(clusterer, query_embedding)
                cluster_id = int(cluster_id[0])

                # Handle noise prediction
                if cluster_id == -1:
                    # Find nearest neighbor
                    cursor.execute("SELECT id, term FROM searchApp_term")
                    all_terms = cursor.fetchall()
                    term_texts = [t[1] for t in all_terms]
                    embeddings = model.encode(term_texts)
                    nbrs = NearestNeighbors(n_neighbors=1).fit(embeddings)
                    _, idx = nbrs.kneighbors(query_embedding)
                    nearest_term_id = all_terms[idx[0][0]][0]

                    # Get cluster of nearest neighbor
                    cursor.execute("""
                        SELECT cluster FROM searchApp_termcluster
                        WHERE term_id = %s
                    """, (nearest_term_id,))
                    cluster_id = cursor.fetchone()[0]

            # Get top terms in cluster
            cursor.execute("""
                SELECT t.term, SUM(ii.tf) AS total_tf
                FROM searchApp_termcluster tc
                JOIN searchApp_term t ON tc.term_id = t.id
                JOIN searchApp_invertedindex ii ON t.id = ii.term_id
                WHERE tc.cluster = %s
                AND t.term != %s
                GROUP BY t.term
                ORDER BY total_tf DESC
                LIMIT 10
            """, (cluster_id, query_term))

            results = cursor.fetchall()
            return [query_term] + [row[0] for row in results]

    except FileNotFoundError:
        print("Clustering models not found. Run update_term_clusters first.")
        return [query_term]
    finally:
        conn.close()


# Usage example
if __name__ == "__main__":
    update_term_clusters()
    print(expand_query('Taiwan'))
