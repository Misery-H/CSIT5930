import os
from dotenv import load_dotenv
load_dotenv()

from codecs import backslashreplace_errors

from openai import OpenAI

import pymysql
import numpy as np
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

db_config = {
    'host': '127.0.0.1',
    'user': 'django',
    'password': os.getenv("MYSQL_PASSWORD"),
    'db': 'search_engine',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

client = OpenAI(
    api_key=os.getenv("ALIYUN_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)


def chat_complete(content):
    prompt = """
Summarize the provided content of a webpage and generate a concise, factual description of the webpage. This summary will be shown in a search engine, so write in that style. 
- Use definition writing style, avoid using words like "This is ..."
- Focus strictly on existing content. 
- Prioritize accuracy over creativity.
- Write no more than 80 words.
IMPORTANT: ONLY OUTPUT THE DESCRIPTION OF THE HTML BODY WITHOUT EXPLAINING!

Here is the html body you need to describe: 

<body>
{}
</body>
    """
    print(f"Start asking ai using Aliyun: {prompt.format(content)}")

    completion = client.chat.completions.create(
        model="deepseek-v3",
        messages=[
            {'role': 'user', 'content': prompt.format(content)}
        ],
        temperature=0.5, # Less creative
        top_p=0.6,
        presence_penalty=0.95
    )

    print(f"Result:\n{completion.choices[0].message.content}\n\n")

    return completion.choices[0].message.content


def generate_desc():
    """Generate description using AI"""

    try:
        conn = pymysql.connect(**db_config)

        with conn.cursor() as cursor:
            # Get all documents and create ID mapping
            cursor.execute("SELECT id FROM searchApp_document")

            # Divide into sections
            page_size = 50
            offset = 0

            while True:
                cursor.execute("SELECT * FROM searchApp_document LIMIT %s OFFSET %s", (page_size, offset))
                records = cursor.fetchall()

                if not records:
                    break

                with tqdm(total=len(records), desc=f"Processing from {offset}") as pbar:
                    for record in records:
                        if record['description'] == 'TODO':
                            url = record['url']
                            try:
                                response = requests.get(url, timeout=10)
                                response.raise_for_status()
                                soup = BeautifulSoup(response.text, 'html.parser')
                                body = soup.find('body').get_text(strip=True)[:5000]  # 限制长度防止过长

                                # 生成描述
                                new_description = chat_complete(body)

                                new_description += "`AIDESC"

                                # 更新数据库
                                cursor.execute(
                                    "UPDATE searchApp_document SET description = %s WHERE id = %s",
                                    (new_description, record['id'])
                                )
                                conn.commit()
                                print(f"Updated record {record['id']} with new description.")
                            except requests.RequestException as e:
                                print(f"Request failed for {url}: {e}")
                            except Exception as e:
                                print(f"Error processing {url}: {e}")
                                conn.rollback()
                    pbar.update(1)

                offset += page_size

    finally:
        conn.close()


if __name__ == '__main__':
    generate_desc()