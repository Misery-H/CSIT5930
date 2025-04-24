import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("ALIYUN_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

PROMPT_TEMPLATE = """
You are an intelligent summarization engine. Given a user query and the top documents retrieved by a search engine, your task is to write a concise, coherent, and informative conclusion that directly answers the query based on the information found in the documents.

Instructions:

**DO NOT start any sentence with phrases like "The documents...", "The query...", or similar meta-commentary.**

Focus only on the information from the documents.

Identify key insights or consensus points relevant to the query.

If the documents disagree, briefly reflect both views.

Do not add any new or external information.

Keep the tone neutral and factual.

Give your summarization without explanation and explicit refer to specific documents

"""

def chat_complete_stream(prompt):
    print(f"Start asking ai using Aliyun: {prompt}")
    answer_content = ""

    stream = client.chat.completions.create(
        model="deepseek-v3",
        messages=[
            {"role": "user", "content": prompt}
        ],
        stream=True
    )

    for chunk in stream:
        if not getattr(chunk, 'choices', None):
            print("\n" + "=" * 20 + "Token usage" + "=" * 20 + "\n")
            print(chunk.usage)
            continue

        delta = chunk.choices[0].delta

        yield delta.content
        answer_content += delta.content

    print("=" * 20 + "Full response" + "=" * 20)
    print(answer_content)

def chat_complete(content):
    print(f"Start asking ai using Aliyun: {content}")

    completion = client.chat.completions.create(
        model="deepseek-v3",
        messages=[
            {'role': 'user', 'content': content}
        ]
    )

    print(completion.choices[0].message.content)