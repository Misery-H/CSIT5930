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

def calculate_pagerank():
    """Calculate PageRank using raw SQL and numpy with convergence threshold"""
    # Database configuration - replace with your actual credentials

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

            # Get all links with progress bar
            cursor.execute("SELECT from_document_id, to_document_id FROM search_engine.searchapp_urllinkage")
            links = cursor.fetchall()

            # Convert links to numpy indices
            i_indices = []
            j_indices = []
            for from_id, to_id in tqdm(links, desc="Processing links"):
                if from_id in id_to_idx and to_id in id_to_idx:
                    i_indices.append(id_to_idx[from_id])
                    j_indices.append(id_to_idx[to_id])

            # Calculate outgoing link counts using numpy
            i_indices = np.array(i_indices)
            unique_i, outgoing_counts = np.unique(i_indices, return_counts=True)

            # Initialize full outgoing counts array
            full_outgoing = np.zeros(n_docs, dtype=np.float64)
            np.add.at(full_outgoing, unique_i, outgoing_counts)
            full_outgoing[full_outgoing == 0] = np.nan  # Mark dangling nodes

            # Initialize PageRank parameters
            damping = 0.85
            tol = 1e-6
            max_iter = 100
            pr = np.full(n_docs, 1/n_docs, dtype=np.float64)

            # PageRank iteration with convergence check
            with tqdm(total=max_iter, desc="PageRank Iterations") as pbar:
                for _ in range(max_iter):
                    # Calculate S matrix contributions
                    S = pr.copy()
                    S /= full_outgoing
                    S[np.isnan(S)] = 0  # Handle dangling nodes

                    # Calculate incoming contributions
                    incoming = np.bincount(j_indices, weights=S[i_indices], minlength=n_docs)

                    # Calculate dangling node mass
                    dangling = pr[np.isnan(full_outgoing)].sum()

                    # Update PageRank values
                    new_pr = (1 - damping)/n_docs + damping * (incoming + dangling/n_docs)

                    # Check convergence
                    delta = np.abs(new_pr - pr).sum()
                    pbar.set_postfix({'Δ': f"{delta:.2e}"})
                    pbar.update(1)

                    if delta < tol:
                        break

                    pr = new_pr.copy()

            # Normalize and format results
            pr /= pr.sum()  # Ensure sum to 1
            pr *= 100 # Normalize to sum = 100
            return {doc_id: pr[i] for doc_id, i in id_to_idx.items()}

    finally:
        conn.close()


def save_to_db(pr_score):
    try:
        conn = pymysql.connect(**db_config)
        with conn.cursor() as cursor:
            # Create batch update parameters
            batch_size = 1000
            items = list(pr_score.items())

            # Prepare SQL statement
            update_query = """
                    UPDATE searchapp_document 
                    SET pr_score = %s 
                    WHERE id = %s
                """

            # Batch update with progress bar
            with tqdm(total=len(items), desc="Storing scores") as pbar:
                for i in range(0, len(items), batch_size):
                    batch = [
                        (float(score), int(doc_id))
                        for doc_id, score in items[i:i + batch_size]
                    ]

                    cursor.executemany(update_query, batch)
                    conn.commit()
                    pbar.update(len(batch))

            print(f"Successfully updated {len(items)} documents")

    except Exception as e:
        print(f"Error storing scores: {str(e)}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    result = calculate_pagerank()
    save_to_db(result)