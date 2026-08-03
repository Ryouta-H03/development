# Lambda + S3 + Glue + Athena で作る簡易データパイプライン

## 📌 1. この演習の目的（ゴール）

リストデータを Lambda で CSV 化して S3 に格納し、Glue クローラでスキーマをカタログ化、Athena で SQL クエリを実行し、その結果を再び S3 に格納する、という一連のサーバーレスデータパイプラインを構築する。

## 📖 0. 用語解説（先に読むと理解しやすい）

| 用語 | 説明 |
|---|---|
| **サーバーレス** | サーバーの構築・管理を自分で行わず、クラウド側が用意した実行環境を必要な時だけ使う仕組み。使った分だけ課金され、使わない時は稼働・課金されない。 |
| **Lambda** | コードを事前にアップロードしておくと、イベント(呼び出し)が発生した時だけ自動で実行してくれるAWSのサーバーレス実行サービス。常時起動しているサーバーではない。 |
| **S3(Simple Storage Service)** | AWSが提供するファイル保管サービス(オブジェクトストレージ)。フォルダのような概念(実際は「キー」というパス文字列)でファイルを整理できる。 |
| **Glue** | データのスキーマ(列名・型などの構造情報)を管理する「データカタログ」機能と、それを自動生成する「クローラ」を含むAWSのデータ統合サービス。 |
| **Glue Crawler(クローラ)** | S3などに置かれたファイルを実際に読み取り、スキーマを自動推測してGlue Data Catalogに登録してくれる仕組み。データ自体は移動・変更しない。 |
| **Glue Data Catalog** | 「どこに、どんな構造のデータがあるか」を記録しておくメタデータ(データについてのデータ)の保管庫。Athenaはここを見てクエリの対象を把握する。 |
| **Athena** | S3上のデータに対して、SQL(データベース言語)を使って直接検索・集計できるAWSのクエリサービス。事前にデータベースサーバーを立てる必要がない。 |
| **IAM(Identity and Access Management)** | 「誰が」「何を」操作してよいかを管理するAWSの権限管理サービス。 |
| **IAMロール** | 人間ではなく、AWSのサービス(Lambdaなど)自身に与える「権限のセット」。「このロールを引き受けたLambdaは、S3に書き込んでよい」のように使う。 |
| **信頼ポリシー(Trust Policy)** | IAMロールにおいて「誰がこのロールを引き受けられるか」を定義する設定。 |
| **許可ポリシー(Permission Policy)** | IAMロールにおいて「引き受けた後に何をしてよいか」を定義する設定。 |
| **ARN(Amazon Resource Name)** | AWS上のリソース(S3バケットやIAMロールなど)を一意に指し示す識別子の書式。例: `arn:aws:s3:::バケット名`。 |
| **CSV(Comma-Separated Values)** | データをカンマ区切りで並べた、表形式データの代表的なファイル形式。 |
| **pandas** | Pythonで表形式データ(行と列)を扱うためのライブラリ。集計・変換・CSV入出力などが簡潔に書ける。 |
| **Lambda Layer** | Lambda関数本体とは別に、共通のライブラリ(pandasなど)をまとめて追加できる仕組み。標準では入っていないライブラリを使う際に必要。 |
| **boto3** | PythonからAWSの各サービス(S3やLambdaなど)を操作するための公式SDK(ソフトウェア開発キット)。 |
| **Hiveパーティション形式** | `year=2026/month=08/day=02/` のように、フォルダ名に `キー=値` を含める命名ルール。Glueクローラがこの形式を見ると、自動的に絞り込み用の列(パーティション)として認識してくれる。 |
| **SerDe(Serializer/Deserializer)** | ファイルの中身(CSVやJSONなど)を、どのようにテーブルの行・列として読み書きするかを定義する変換ルール。Glue/Athenaの内部で使われる。 |
| **スキーマ** | データの構造(列名・データ型など)の定義のこと。 |
| **クエリ** | データベースやAthenaに対して投げる「検索・集計の指示文」。SQLで記述する。 |
| **IaC(Infrastructure as Code)** | インフラ(サーバーやネットワークなどの環境)の構成を、コンソールでの手作業ではなく、コードとして記述・管理する考え方。 |

## 🏗️ 2. 全体構成（アーキテクチャ）

```
[Lambda] → CSV生成(pandas) → [S3: raw/ 生データ置き場]
                                    ↓
                            [Glue Crawler] → データカタログ(テーブル)自動生成
                                    ↓
                            [Athena] → SQLクエリ実行
                                    ↓
                            [S3: athena-results/ クエリ結果置き場]
```

| 層 | 役割 | 主な要素 |
|----|------|----------|
| 生成層 | リストデータをCSV化 | Lambda（Python + pandas） |
| 保管層 | ファイルの永続化 | S3（Hiveパーティション形式） |
| カタログ層 | スキーマ・メタデータの管理 | Glue Data Catalog / Crawler |
| 分析層 | SQLによるデータ抽出 | Athena |
| 出力層 | クエリ結果の保管 | S3（クエリ結果保存先） |

## ✅ 3. 前提条件（はじめる前に）

- リージョン(AWSのデータセンターがある地域)は `ap-northeast-1`（東京）を使用
- AWSアカウントが発行済みで、マネジメントコンソール(AWSのブラウザ管理画面)にログインできること
- Lambda・S3・Glue・IAM・Athenaを作成できる権限を持つIAMユーザーであること
- Lambdaランタイム(実行環境のプログラミング言語・バージョン)は Python 3.13 を想定（pandas利用のためLambda Layerが必要）

## 🚀 4. セットアップ手順

> 💡 作成する順番は「IAMロール → S3バケット → Lambda → Glue Crawler → Athena」です。

### 4.1. IAMロールの作成（Lambda用）

IAM → ロール →「ロールを作成」

- 信頼されたエンティティ: **AWSのサービス** →「Lambda」を選択（信頼ポリシーは自動生成される）
- アタッチする許可ポリシー:
  - `AWSLambdaBasicExecutionRole`（マネージドポリシー=AWSが用意済みの権限セット。CloudWatch Logs〈実行ログの保管サービス〉への出力用）
  - S3書き込み用のカスタムポリシー（下記）

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::<YOUR_BUCKET_NAME>/raw/*"
    }
  ]
}
```

> ⚠️ 信頼ポリシー（誰がロールを引き受けられるか）と、許可ポリシー（何ができるか）は別物。`Resource`フィールドは許可ポリシー側にのみ書ける。信頼ポリシーに混同して貼り付けるとエラーになる。

### 4.2. S3バケットの作成

バケットとは、S3におけるファイルの保管場所(入れ物)の単位のこと。

```
<YOUR_BUCKET_NAME>/
├── raw/                    ← Lambdaの出力先（Glueクローラの対象）
└── athena-results/         ← Athenaのクエリ結果出力先
```

### 4.3. Lambda関数の作成

**Lambda Layerの追加（pandas利用のため必須）**

pandasは標準ライブラリ（Pythonに最初から入っている機能）ではないため、AWS提供のLambda Layer（`AWSSDKPandas-PythonXXX`、ランタイムバージョンに合わせる）を追加する。

- ランタイムとLayerの **Pythonバージョン**・**アーキテクチャ(x86_64/arm64、CPUの種類)** を一致させること

**関数コード（`lambda_function.py`）**

```python
import boto3
import pandas as pd
import io
from datetime import datetime, timezone

# boto3クライアントはグローバルスコープで生成
# (Lambdaのウォームスタート=実行環境の再利用時に使い回されるため、接続コストを削減できる)
s3 = boto3.client('s3')

# 環境変数から取得するのが望ましい(ここでは例示のためベタ書き)
BUCKET_NAME = '<YOUR_BUCKET_NAME>'


def lambda_handler(event, context):
    # event: Lambda呼び出し時に渡される入力データ
    # context: 実行環境に関する情報(今回は未使用)
    # event.get('data', [...]) は「eventの中にdataキーがあればその値を、
    # なければデフォルト値(サンプルデータ)を使う」という意味
    data_list = event.get('data', [
        {'id': 1, 'name': 'Alice', 'age': 30},
        {'id': 2, 'name': 'Bob', 'age': 25},
        {'id': 3, 'name': 'Charlie', 'age': 35},
    ])

    if not data_list:
        return {'statusCode': 400, 'body': 'No data provided'}

    # 辞書のリストからDataFrame(pandasの表形式データ構造)を作成
    # pandasは全レコードを走査して列を決定するため、レコード間でキーが多少
    # 不揃いでも欠損値はNaN(Not a Number、欠損値を表す特殊な値)として補完される
    df = pd.DataFrame(data_list)

    # メモリ上に仮想ファイルを用意(ディスクI/Oを避けるため。
    # io.StringIOは「文字列を読み書きできる、実体を持たない仮想ファイル」)
    csv_buffer = io.StringIO()

    # index=False を付けないと、pandasの行インデックス(0,1,2...という自動連番)が
    # 余計な列としてCSVに出力されてしまう
    df.to_csv(csv_buffer, index=False)

    # 日付パーティション形式のキー(S3上でのファイルパスに相当する文字列)を生成
    # "year=2026/month=08/day=02/" というHive形式にしておくと、
    # Glueクローラがこれを自動でパーティション列として認識してくれる
    now = datetime.now(timezone.utc)  # UTC(協定世界時)で現在時刻を取得
    key = (
        f"raw/year={now.year}/month={now.month:02d}/day={now.day:02d}/"
        f"data_{now.strftime('%Y%m%d%H%M%S')}.csv"
    )

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=csv_buffer.getvalue(),
        ContentType='text/csv'
    )

    return {
        'statusCode': 200,
        'body': f'CSV uploaded to s3://{BUCKET_NAME}/{key}'
    }
```

### 4.4. Glue Crawlerの作成

Glue → Crawlers →「Create crawler」

- Data source(データの取得元): S3、パスは `s3://<YOUR_BUCKET_NAME>/raw/`
- IAMロール: `AWSGlueServiceRole` ポリシー付きのロールを選択
- Target database(登録先のデータベース): 新規 or 既存のデータベースを指定
- 作成後「Run crawler」を実行

> 💡 手動でのテーブル作成（列定義・SerDe指定など）はエラーが起きやすいため、**クローラによる自動生成を推奨**（詳細は6章のトラブルシューティング参照）。

### 4.5. Athenaでのクエリ実行

初回のみ、クエリ結果の出力先を設定（Athena → Settings → クエリ結果の場所 → `s3://<YOUR_BUCKET_NAME>/athena-results/`）。

```sql
-- パーティションを認識させる(手動テーブル作成時、新しいパーティションが増えた場合に必要)
-- MSCK REPAIR TABLE: S3上の新しいパーティション(フォルダ)をテーブル定義に反映させるコマンド
MSCK REPAIR TABLE <database_name>.<table_name>;

-- クエリ本体(SELECT: 指定した列・条件でデータを取得するSQLの基本構文)
SELECT id, name, age, year, month, day
FROM <database_name>.<table_name>
WHERE year = '2026' AND month = '08' AND day = '02';
```

> ⚠️ Athenaは1回の実行につき1つのSQL文しか受け付けない。セミコロン区切りで複数文を書いても実行できないため、1文ずつ分けて実行する。

## ▶️ 5. 実行方法（動作確認）

1. Lambdaをテスト実行 → S3の`raw/`配下にCSVが生成されることを確認
2. Glueクローラを実行 → Data Catalogにテーブルが作られることを確認（Glue → Tables）
3. Athenaで`SELECT`クエリを実行 → データが正しく取得できることを確認
4. S3の`athena-results/`配下に、クエリ実行結果のCSV（ランダムなファイル名）が自動生成されていることを確認

Athenaはクエリ実行のたびに、指定した出力先へ自動的に結果をCSV保存する仕様のため、④は特別な追加実装なしに実現される。

## 📘 6. 各コンポーネントの説明

- **Lambda**: リストデータをCSV文字列に変換し、S3へ格納するだけの役割。常時起動するサーバーではなく、呼び出された時だけ動く。pandas利用にはLambda Layerの追加が必要。
- **S3（raw/）**: 生データの置き場。Hiveパーティション形式（`year=YYYY/month=MM/day=DD/`）にしておくと、Glueクローラがパーティション列として自動認識する。
- **Glue Crawler**: S3上のファイルをスキャンし、スキーマ（列名・型）を推測してGlue Data Catalogにテーブルとして登録する。データそのものは動かさず、メタデータ（データについての情報）のみ生成する。
- **Athena**: Glue Data Catalogのテーブル定義を参照し、S3上のデータに直接SQLを投げるサーバーレスクエリサービス。事前にデータベースサーバーを起動しておく必要がなく、スキャンしたデータ量に応じて課金される。
- **S3（athena-results/）**: Athenaのクエリ結果が自動的に保存される場所。

## 📂 リソース構成

```
Region: ap-northeast-1
├── IAM Role（Lambda実行用: S3書き込み権限）
├── IAM Role（Glue Crawler用: AWSGlueServiceRole + S3読み取り権限）
├── S3 Bucket
│   ├── raw/                  ← Lambda出力先(Hiveパーティション形式)
│   └── athena-results/       ← Athenaクエリ結果出力先
├── Lambda Function（Python 3.13 + pandas Layer）
├── Glue Database
│   └── Glue Table（クローラ自動生成）
└── Athena（クエリ実行環境）
```

## 🧹 後片付け（重要）

料金が発生し続けないよう、演習が終わったら以下を確認・削除する。

1. Glue Crawlerのスケジュール実行が設定されていないか確認（オンデマンド実行=手動実行のみなら追加課金なし）
2. Athenaのクエリ結果（S3内）が不要に増え続けていないか確認、不要なら削除
3. Lambda・S3・Glueのデータベース/テーブルは、いずれも「実行・保存量に応じた課金」であり、放置自体では大きな課金は発生しないが、テスト用データが不要になったらS3のオブジェクトを削除しておくと良い
4. 使わなくなったIAMロール・ポリシーは整理する

## 🔧 トラブルシューティング

| 症状・エラーメッセージ | 原因 | 対処 |
|---|---|---|
| `Has prohibited field Resource` | IAMロール作成時、信頼ポリシーの欄に許可ポリシー（`Resource`を含むJSON）を貼り付けてしまった | 信頼ポリシーには`Effect`/`Principal`/`Action`/`Condition`のみ記載。`Resource`を含むポリシーは作成後に許可ポリシーとして別途アタッチする |
| テスト実行結果が `"Hello from Lambda!"` になる | コードを編集しただけで「Deploy」ボタンを押していない | コード編集後、必ず「Deploy」をクリックしてから実行する |
| `NameError: name 'xxx' is not defined` | 文字列をクォート(`'`または`"`)で囲み忘れ、Pythonが減算式として解釈してしまった | 文字列は必ずシングルクォートかダブルクォートで囲む |
| `Runtime.UserCodeSyntaxError: invalid syntax` | クォートのつもりでバッククォート（`` ` ``）を使ってしまった | バッククォートはPythonの文字列構文ではない。`'`または`"`に置き換える |
| `AccessDenied ... s3:PutObject ... not authorized` | Lambda実行ロールにS3書き込み権限が付与されていない | 対象ロールにS3書き込み許可のインラインポリシーを追加する |
| `Only one sql statement is allowed` | Athenaのクエリ欄にセミコロン区切りで複数文をまとめて実行しようとした | 1回の実行につき1文のみ。複数の処理は分けて順番に実行する |
| `mismatched input 'xxx'. Expecting: '(', 'LATERAL', ...` | データベース名・テーブル名がSQLの予約語（`CASE`など、SQL自体が特別な意味を持たせている単語）と衝突している | 識別子をダブルクォート（`"テーブル名"`）で囲んで、予約語ではなくただの名前であることを明示する |
| `TABLE_NOT_FOUND` | クエリで指定したデータベース名・テーブル名が実際のものと一致していない | `SHOW DATABASES;` / `SHOW TABLES IN <db>;` で実際の名前を確認してから指定し直す |
| `SemanticException: Database does not exist` | 指定したデータベース名が存在しない（typoや作成先の勘違い） | `SHOW DATABASES;` で実在するデータベース名を確認する |
| `COLUMN_NOT_FOUND: Relation contains no accessible columns` | 手動でテーブルを作成した際、列（Schema）が正しく定義されていない | Glueコンソールでテーブルの列定義を確認・追加する。根本対応としてはクローラでの自動生成に切り替える |
| `BAD_DATA: Error parsing column 'id' with value 'id'` | CSVのヘッダー行（列名の行）がデータとして読み込まれてしまっている | テーブルプロパティに`skip.header.line.count`=`1`を設定する。ただしSerDeの種類によっては効かない場合がある |
| `TYPE_MISMATCH: Cannot apply operator: integer = varchar` | int型（整数型）の列とヘッダー行の文字列（varchar型）を`WHERE`で比較しようとした | そもそもCSVの型変換(パース)はWHERE評価より前に走るため、この方法では回避できない。テーブル定義側の見直しが必要 |
| `mismatched input 'TBLPROPERTIES'. Expecting: 'AUTHORIZATION', 'PROPERTIES'` | AthenaのSQLエンジン(Trino系、Hiveとは別のクエリエンジン)はHive構文の`SET TBLPROPERTIES(...)`をサポートしない | `ALTER TABLE ... SET PROPERTIES key=value;`という Athena/Trino構文を使う。またはGlueコンソールから直接Table propertiesを編集する |
| 手動作成したCSVテーブルで、上記のヘッダー混入・列欠落などの問題が繰り返し発生する | 手動テーブル作成はSerDeの指定やヘッダー行のスキップ設定などが事故りやすい | **Glueクローラで自動生成する**のが最も確実。クローラは実データをスキャンして適切なSerDe・ヘッダー設定を自動選択する |
| クエリ結果がどこに保存されているか分からない | Athenaは特別な実装なしに、設定した出力先へ自動でクエリ結果を保存する仕様 | Athena → Settingsで設定したS3パス（例: `athena-results/`）を確認する。ファイル名はランダムなUUID(一意な識別子)形式になる |

## 📚 参考資料

- AWS Lambda ドキュメント
- Amazon S3 ドキュメント
- AWS Glue ドキュメント
- Amazon Athena ドキュメント

## 📝 補足・メモ

- 本ドキュメント内のアカウントID・バケット名・ロール名などは、GitHub公開のためすべてプレースホルダー（`<YOUR_BUCKET_NAME>`等）に置き換えている。実際に手を動かす際は、自身の環境の値に読み替えること。
- pandasを使わずCSVを組み立てる場合は、標準ライブラリの`csv`モジュール（`csv.DictWriter`）でも同様の実装が可能。pandasの方がコード量は少ないが、Lambda Layerの追加設定が必須になる点はトレードオフ。
