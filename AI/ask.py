import boto3
import json
import sys

args = sys.argv

# 引数チェック: sys.argv[0] はスクリプト名なので、質問文があるなら最低 2 個
if len(args) < 2:
    print('Usage: python3 ask.py "質問文"')
    sys.exit(1)

# 引数を結合する。クォートを忘れて単語ごとに割れても全語を拾える
prompt = " ".join(args[1:])

client = boto3.client("bedrock-runtime", region_name="us-east-1")


def ask(prompt: str) -> str:
    response = client.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        body=json.dumps({
            # 入力言語に引っ張られず日本語で固定する
            "system": [{"text": "必ず日本語で回答してください。"}],
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            # 出力が途中で切れないよう上限を明示する
            "inferenceConfig": {"maxTokens": 1000}
        })
    )
    body = json.loads(response["body"].read())
    return body["output"]["message"]["content"][0]["text"]


print(ask(prompt))
