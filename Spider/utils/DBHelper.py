# -*- coding:utf-8 -*-　
# Last modify: Liu Wentao
# Description: Database helper for calling MySQL operations outside of django framework
# Note:
import os
from contextlib import contextmanager

import pymysql
from MySQLdb.cursors import DictCursor


class DBHelper:
    def __init__(self, username="django", host="127.0.0.1", port=3306, database="search_engine", charset="utf8mb4"):
        self.db_config = {
            "host": host,
            "port": port,
            "user": username,
            'password': os.getenv("MYSQL_PASSWORD"),
            "database": database,
            "charset": charset,
        }

    @contextmanager
    def _get_connection(self):
        """
        _get_connection: It is not suggested to call this function directly, use other functions to connect to MySQL.
        """
        # Get database connection
        conn = pymysql.connect(
            host=self.db_config["host"],
            port=self.db_config["port"],
            user=self.db_config["user"],
            password=self.db_config["password"],
            db=self.db_config["database"],
            charset=self.db_config["charset"],
        )

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def add_document(self, document):
        """
        add_document: Add a new document to the database. The records are deduplicated based on content_hash.
        Args:
            document: a python dictionary.

        Returns: document id

        """
        if not document:
            return -1

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # IGNORE is added here based on verifying unique content_hash to avoid duplication.
                sql = """
                    INSERT IGNORE INTO searchapp_document
                    (url, content_hash, title, description, content, crawl_time, tf_max,last_modify)
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)
                """

                cursor.execute(sql, (
                    document.get("url"),
                    document.get("content_hash"),
                    document.get("title"),
                    document.get("description"),
                    document.get("content"),
                    document.get("tf_max"),
                    document.get("last_modify"),
                ))

                if cursor.lastrowid == 0:
                    cursor.execute("SELECT id FROM searchapp_document WHERE content_hash = %s",
                                   (document.get("content_hash")))
                    doc_id = cursor.fetchone()[0]
                else:
                    doc_id = cursor.lastrowid

        return doc_id
    def update_document(self, document,page_id):
        """
        update_document: Update a document in the database. The records are deduplicated based on content_hash.
        Args:
            document: a python dictionary.

        Returns: document id

        """
        if not document:
            return -1

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # IGNORE is added here based on verifying unique content_hash to avoid duplication.
                sql = """
                    UPDATE searchapp_document
                    SET url = %s, content_hash = %s, title = %s, description = %s, content = %s, crawl_time = NOW(), tf_max = %s,last_modify = %s
                    WHERE id = %s
                """

                cursor.execute(sql, (
                    document.get("url"),
                    document.get("content_hash"),
                    document.get("title"),
                    document.get("description"),
                    document.get("content"),
                    document.get("tf_max"),
                    document.get("last_modify"),
                    document.get("content_hash"),
                    page_id
                ))

                if cursor.lastrowid == 0:
                    cursor.execute("SELECT id FROM searchapp_document WHERE content_hash = %s",
                                   (document.get("content_hash")))
                    doc_id = cursor.fetchone()[0]
                else:
                    doc_id = cursor.lastrowid

        return doc_id
    def _get_or_create_term(self, term, conn):
        """
        _get_or_create_term: maintain a term in the "term" table, with its document frequency.
        It is NOT suggested to call this function directly, use add_inverted_index instead.
        Args:
            term: string to be added
            conn: database connection

        Returns: term id

        """
        with conn.cursor() as cursor:
            # Meta operation
            sql = """
                INSERT INTO searchapp_term (term, df) 
                VALUES (%s, 1)
                ON DUPLICATE KEY UPDATE df = df + 1
            """
            cursor.execute(sql, (term,))

            # Fetch term id
            cursor.execute("SELECT id FROM searchapp_term WHERE term = %s", (term,))
            term_id = cursor.fetchone()[0]
            return term_id

    def add_inverted_index(self, doc_id, term_tf_dict):
        """
        add_inverted_index: this function automatically maintain the "term" table while appending inverted index.
        Args:
            doc_id: document id to be inverted indexed.
            term_tf_dict: a dictionary with tuple meta elements (term, term-frequency)
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                for term, tf in term_tf_dict.items():
                    term_id = self._get_or_create_term(term, conn)

                    sql = """
                        INSERT INTO searchapp_invertedindex (term_id, document_id, tf)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE tf = VALUES(tf)
                    """
                    cursor.execute(sql, (term_id, doc_id, tf))

    def get_documents_by_term(self, term):
        """
        get_documents_by_term: retrieve documents from inverted index by term, the workflow of this function is:
        term -> term id -> documents list
        Args:
            term: a string term

        Returns: a list containing documents data (dictionaries).

        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM searchapp_term WHERE term = %s",
                    (term,)
                )
                term_result = cursor.fetchone()

                if not term_result:
                    return []

                term_id = term_result[0]

                query_sql = """
                    SELECT 
                        d.id,
                        d.url,
                        d.title,
                        d.description,
                        d.content,
                        d.crawl_time,
                        d.tf_max,
                        ii.tf
                    FROM searchapp_document d
                    INNER JOIN searchapp_invertedindex ii 
                        ON d.id = ii.document_id
                    WHERE ii.term_id = %s
                    ORDER BY ii.tf DESC
                """
                cursor.execute(query_sql, (term_id,))

                documents = []
                for row in cursor.fetchall():
                    documents.append({
                        'doc_id': row[0],
                        'url': row[1],
                        'title': row[2],
                        'description': row[3],
                        'content': row[4],
                        'crawl_time': row[5].isoformat() if row[5] else None,
                        'tf_max': row[6],
                        'tf': row[7],
                    })

                return documents

    def add_url_linkage(self, from_doc_id, to_doc_id):
        """
        add_url_linkage: add a url linkage to the document.
        Args:
            from_doc_id: url source document id
            to_doc_id: url point to document id
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                sql = """
                   INSERT IGNORE INTO searchapp_urllinkage (from_document_id, to_document_id)
                   VALUES (%s, %s)
                """
                cursor.execute(sql, (from_doc_id, to_doc_id))
    def delete_url_linkage(self, from_doc_id):
        """
        delete_url_linkage: delete a url linkage to the document.
        Args:
            from_doc_id: url source document id
            to_doc_id: url point to document id
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                sql = """
                   DELETE FROM searchapp_urllinkage WHERE from_document_id = %s 
                """
                cursor.execute(sql, (from_doc_id))
    def get_all_documents(self):
        """
        get_all_documents: retrieve all documents from the database.
        Returns: a list containing documents data (dictionaries).
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        d.url,
                        d.title,
                        d.description,
                        d.content,
                        d.crawl_time,
                        d.tf_max,
                        d.last_modify
                    FROM searchapp_document d
                    """
                )

                documents = {}
                for row in cursor.fetchall():
                    documents[row[0]]={
                        'title': row[1],
                        'description': row[2],
                        'content': row[3],
                        'crawl_time': row[4].isoformat() if row[5] else None,
                        'tf_max': row[5],
                        'last_modify': row[6].isoformat() if row[6] else None,
                    }

                return documents

    def get_page_id(self, current_url):
        """
        get_page_id: retrieve the document id by url.
        Args:
            current_url: a string url

        Returns: document id
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM searchapp_document WHERE url = %s",
                    (current_url,)
                )
                result = cursor.fetchone()
                if result:
                    return result[0]
                else:
                    return -1
    def add_term(self,term_dict):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # 将字典转换为(term, df)元组列表
                data = [(term, df) for term, df in term_dict.items()]
                data = list(sorted(data, key=lambda x: x[1], reverse=True))

                # 使用executemany进行批量插入
                cursor.executemany(
                    "INSERT INTO searchapp_term (term, df) VALUES (%s, %s)",
                    data
                )



    def get_term(self,term):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id,df FROM searchapp_term WHERE term = %s",
                    (term,)
                )
                row = cursor.fetchone()
                if row:
                    return row[0],row[1]
                else:
                    return None,None

