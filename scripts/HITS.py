import os

import pymysql
import numpy as np
from tqdm import tqdm

db_config = {
        'host': '127.0.0.1',
        'user': 'django',
        'password': os.getenv("MYSQL_PASSWORD"),
        'db': 'search_engine',
        'charset': 'utf8mb4'
    }

def calculate_hits(max_iter=100, tol=1e-6):
    """Calculate HITS scores using raw SQL and numpy"""

    try:
        # Establish database connection
        conn = pymysql.connect(**db_config)

        with conn.cursor() as cursor:
            # Get all documents and create ID mapping
            cursor.execute("SELECT id FROM searchapp_document")
            doc_ids = [row[0] for row in cursor.fetchall()]
            n_docs = len(doc_ids)
            if n_docs == 0:
                return {}

            id_to_idx = {doc_id: i for i, doc_id in enumerate(doc_ids)}
            idx_to_id = {i: doc_id for doc_id, i in id_to_idx.items()}

            # Get all links
            cursor.execute("SELECT from_document_id, to_document_id FROM searchapp_urllinkage")
            links = cursor.fetchall()

            # Convert links to numpy indices
            i_indices = []
            j_indices = []
            for from_id, to_id in tqdm(links, desc="Processing links"):
                if from_id in id_to_idx and to_id in id_to_idx:
                    i_indices.append(id_to_idx[from_id])  # from
                    j_indices.append(id_to_idx[to_id])    # to

            i_indices = np.array(i_indices)
            j_indices = np.array(j_indices)

            # Initialize authority and hub scores
            authority = np.ones(n_docs, dtype=np.float64)
            hub = np.ones(n_docs, dtype=np.float64)

            # Iterative update
            with tqdm(total=max_iter, desc="HITS Iterations") as pbar:
                for _ in range(max_iter):
                    old_authority = authority.copy()
                    old_hub = hub.copy()

                    # Update authority: sum hub of incoming nodes
                    authority = np.bincount(j_indices, weights=hub[i_indices], minlength=n_docs)

                    # Update hub: sum authority of outgoing nodes
                    hub = np.bincount(i_indices, weights=authority[j_indices], minlength=n_docs)

                    # Normalize
                    authority /= np.linalg.norm(authority, 2)
                    hub /= np.linalg.norm(hub, 2)

                    # Check convergence
                    delta = np.linalg.norm(authority - old_authority, 1) + np.linalg.norm(hub - old_hub, 1)
                    pbar.set_postfix({'Δ': f"{delta:.2e}"})
                    pbar.update(1)

                    if delta < tol:
                        break

            # Format result: authority as score (or combine both if necesssary)
            score_dict = {
                idx_to_id[i]: (float(authority[i]) * 100, float(hub[i]) * 100)
                for i in range(n_docs)
            }
            return score_dict

    finally:
        conn.close()



def save_hits_to_db(score_dict):
    try:
        conn = pymysql.connect(**db_config)
        with conn.cursor() as cursor:
            batch_size = 1000
            items = list(score_dict.items())

            update_query = """
                UPDATE searchapp_document 
                SET authority_score = %s, hub_score = %s
                WHERE id = %s
            """

            with tqdm(total=len(items), desc="Storing HITS scores") as pbar:
                for i in range(0, len(items), batch_size):
                    batch = [
                        (float(authority), float(hub), int(doc_id))
                        for doc_id, (authority, hub) in items[i:i + batch_size]
                    ]
                    cursor.executemany(update_query, batch)
                    conn.commit()
                    pbar.update(len(batch))

            print(f"Successfully updated {len(items)} documents")

    except Exception as e:
        print(f"Error storing HITS scores: {str(e)}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    result = calculate_hits()
    save_hits_to_db(result)