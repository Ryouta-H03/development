# Amazon Bedrock APIを使った、チャットBot

## 📌 1. この演習の目的（ゴール）

ターミナル上から質問を送り、Amazon Bedrock の生成AIモデルから回答を取得する。

## 🏗️ 2. 全体構成（アーキテクチャ）

質問はターミナルから入り、次の流れで処理されます。

```
ユーザー(ターミナル)
    ↓  質問文を引数で渡す
ask.py (Boto3)
    ↓  invoke_model で呼び出し
Amazon Bedrock (Nova Lite / us-east-1)
    ↓  生成した回答を返す
ask.py がターミナルに表示
```

階層でとらえると、次の4層になります。

| 層 | 役割 | 主な要素 |
|----|------|----------|
| 👤 ユーザー層 | 利用者との接点 | ターミナル |
| ⚙️ アプリ層 | 制御・つなぎ込み | `ask.py` / Boto3 |
| 🤖 AI推論層 | 回答の生成 | 基盤モデル（`amazon.nova-lite-v1:0`） |
| 🗄️ サービス層 | 実行基盤 | Amazon Bedrock（`us-east-1`） |

## ✅ 3. 前提条件（はじめる前に）

- OSは Mac（Windowsでの動作確認はしていません）
- AWSアカウントがあり、認証情報が設定済みであること（→ 手順 4.5）
- 使用するモデル（`amazon.nova-lite-v1:0`）のモデルアクセスが有効化されていること（→ 手順 4.6）
- Python3 がインストール済みであること

## 🚀 4. セットアップ手順

### 4.1. フォルダ作成

```
mkdir bedrock-chat
cd bedrock-chat
```

### 4.2. 仮想環境の作成

```
python3 -m venv venv-bedrock-chat
```

### 4.3. 仮想環境の有効化

```
source venv-bedrock-chat/bin/activate
```

### 4.4. AWS SDK(Boto3)インストール

```
pip install boto3
```

### 4.5. AWS認証情報の設定

事前に IAM ユーザーのアクセスキーを発行し、`aws configure` で登録します。

```
aws configure
```

プロンプトに沿って以下を入力します。入力内容は `~/.aws/credentials` に保存され、以降は Boto3 が自動で読み込みます。

- AWS Access Key ID
- AWS Secret Access Key
- Default region name: `us-east-1`
- Default output format: （空欄でも可）

設定できているかは次のコマンドで確認できます。ARN やアカウントIDが返れば成功です。

```
aws sts get-caller-identity
```

> ⚠️ セキュリティ上の注意
> シークレットアクセスキーは第三者に共有せず、コードやREADMEに直接書き込まないでください。
> また学習・アプリ用途では、フル権限（Admin）ではなく、Bedrock 呼び出しに必要な権限だけを持つ専用の IAM ユーザーを使うことが推奨されます。

### 4.6. モデルアクセスの有効化

AWS マネジメントコンソールで対象モデルを有効化します。有効化していないと、認証が通っていても実行時に `AccessDeniedException` で失敗します。

1. リージョンを `us-east-1`（バージニア北部）に切り替える
2. Amazon Bedrock → 「モデルアクセス（Model access）」を開く
3. `amazon.nova-lite-v1:0` を有効化してアクセスをリクエストする

## ▶️ 5. 実行方法

### 5.1. 階層移動し、仮想環境を有効化

```
cd bedrock-chat
source venv-bedrock-chat/bin/activate
```

### 5.2. コマンド実行

質問文は必ずダブルクォートで囲みます。囲まないと単語ごとに別々の引数に割れてしまい、最初の1語しか渡らなかったり、意図しない回答になります。

```
python3 ask.py "これはテストですか？"
```

実行例:

```
(venv-bedrock-chat) $ python3 ask.py "これはテストですか？"
はい、テストの一環としてのご質問ですね。何かお手伝いできることがあればお気軽にどうぞ。
```

## 📘 6. ask.py の説明

`ask.py` は次の処理を行います。

1. コマンドライン引数から質問文を受け取る（複数語も結合して1つの質問にまとめる）
2. Boto3 の `bedrock-runtime` クライアントを作成する
3. `invoke_model` で Nova Lite に質問を送る（`system` で日本語回答を指定、`maxTokens` で出力上限を指定）
4. 返ってきたレスポンスから回答テキストを取り出して表示する

コード全文は同梱の `ask.py` を参照してください。

## 📂 ディレクトリ構成

```
📂 bedrock-chat
├── 📘 ask.py
├── 📄 README.md
└── 📂 venv-bedrock-chat
```

## 🧹 後片付け（重要）

- 演習が終わったら仮想環境を無効化する: `deactivate`
- 不要になったフォルダは削除する: `rm -rf bedrock-chat`
- 使わなくなった IAM アクセスキーは、AWS コンソールで無効化・削除しておく

## 🔧 トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| `Usage: python3 ask.py "質問文"` と表示される | 引数（質問文）を渡していない | 質問文をクォートで囲んで渡す |
| 意図しない言語や無関係な文章が返る | 質問文をクォートで囲まず、単語が割れている | `"..."` で囲んで渡す |
| `AccessDeniedException` | モデルアクセスが未有効化 | 手順 4.6 でモデルを有効化する |
| `NoCredentialsError` / `UnrecognizedClientException` | 認証情報が未設定または不正 | 手順 4.5 で `aws configure` を実行する |
| リージョン関連のエラー | リージョン不一致 | `us-east-1` を指定・使用しているか確認する |

## 📚 参考資料

- Amazon Bedrock ドキュメント
- Boto3 ドキュメント（`bedrock-runtime`）

## 📝 補足・メモ

特になし。