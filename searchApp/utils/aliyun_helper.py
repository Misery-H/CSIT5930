import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("ALIYUN_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)


def chat_complete_stream(content):
    prompt = "Please conclude the following content in 100 words:{}".format(content)
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