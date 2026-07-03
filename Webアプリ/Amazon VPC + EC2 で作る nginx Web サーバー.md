# Amazon VPC + EC2 で作る nginx Web サーバー

## 📌 1. この演習の目的（ゴール）

ブラウザから、Amazon VPC 上に構築した EC2 インスタンス（nginx）へアクセスし、Web ページ（nginx のウェルカムページ）を表示する。

## 🏗️ 2. 全体構成（アーキテクチャ）

リクエストはブラウザから入り、次の流れで処理されます。

```
ユーザー(ブラウザ)
    ↓  HTTP(80) でアクセス
インターネットゲートウェイ(IGW)
    ↓  ルートテーブル(0.0.0.0/0 → IGW)で経路制御
パブリックサブネット (10.0.0.0/24)
    ↓  セキュリティグループ(インバウンド HTTP:80 許可)
EC2 インスタンス (nginx)
    ↓  Webページを返す
ユーザーのブラウザに表示
```

階層でとらえると、次の5層になります。

| 層 | 役割 | 主な要素 |
|----|------|----------|
| 👤 ユーザー層 | 利用者との接点 | ブラウザ |
| 🌐 入口層 | インターネットとの接続・経路制御 | インターネットゲートウェイ / ルートテーブル |
| 🛡️ 制御層 | 通信の許可・制限 | セキュリティグループ（HTTP:80） |
| 🖥️ 実行層 | Webサーバーの実行 | EC2 インスタンス（nginx） |
| 🗄️ 基盤層 | ネットワーク基盤 | VPC（`10.0.0.0/16`）/ パブリックサブネット（`10.0.0.0/24`） |

> 📎 構成図は同梱の `architecture.svg` を参照してください。

## ✅ 3. 前提条件（はじめる前に）

- リージョンは `ap-northeast-1`（東京）を使用します
- AWSアカウントが発行済みで、マネジメントコンソールにログインできること
- VPC・EC2 を作成できる権限を持つ IAM ユーザーであること
- 使用する AMI は Amazon Linux 2023 を想定します（他の AMI では nginx の導入手順が異なります）

## 🚀 4. セットアップ手順

> 💡 作成する順番は「VPC → サブネット → IGW → ルートテーブル → セキュリティグループ → EC2」です。ネットワークの土台から先に作ると迷いにくくなります。

### 4.1. VPC の作成

「お使いのVPC」 →「VPCを作成」

- 作成するリソース：VPCのみ
- 名前タグ - オプション：任意（例：`handson-vpc`）
- IPv4 CIDR ブロック
- IPv4 CIDR：`10.0.0.0/16`
- IPv6 CIDR ブロック：IPv6 CIDR ブロックなし. 

「VPCを作成」

### 4.2. パブリックサブネットの作成

「サブネット」 →「サブネットを作成」

- VPC：手順 4.1 で作成した VPC を選択
- サブネット名：任意（例：`handson-public-subnet`）
- アベイラビリティーゾーン：`ap-northeast-1a`
- IPv4 サブネット CIDR ブロック：`10.0.0.0/24`. 

「サブネットを作成」

### 4.3. インターネットゲートウェイ（IGW）の作成とアタッチ

「インターネットゲートウェイ」 →「インターネットゲートウェイの作成」

- 名前タグ：任意（例：`handson-igw`）. 

「インターネットゲートウェイの作成」

2. 作成した IGW を選択 →「アクション」→「VPCにアタッチ」で手順 4.1 の VPC にアタッチする

> ⚠️ IGW を作っただけでは通信できません。**VPC へのアタッチ**を忘れないでください。

### 4.4. ルートテーブルの設定

ルートテーブル → 対象 VPC のルートテーブルを選択 →「ルートを編集」

| 送信先 | ターゲット |
|--------|-----------|
| `10.0.0.0/16`（デフォルト） | `local` |
| `0.0.0.0/0` | `igw-XXXX`（手順 4.3 の IGW） |

### 4.5. サブネットの関連付け

同じルートテーブルの「サブネットの関連付け」タブ →「サブネットの関連付けを編集」

- 手順 4.2 で作成したパブリックサブネットを関連付ける

> ⚠️ ここが抜けると、ルートを設定してもサブネットに反映されず、インターネットに出られません。**作成したサブネットの関連付け**を忘れないでください。

### 4.6. セキュリティグループの作成

セキュリティグループ →「セキュリティグループを作成」

- VPC：手順 4.1 で作成した VPC を選択
- インバウンドルール：

| タイプ | プロトコル | ポート | ソース |
|--------|-----------|--------|--------|
| HTTP | TCP | `80` | `0.0.0.0/0` |

> ⚠️ セキュリティグループは**作成した VPC に紐づけ**、インバウンドで **HTTP・80** を許可する必要があります。

### 4.7. EC2 インスタンスの起動

EC2 →「インスタンスを起動」

- AMI：Amazon Linux 2023
- インスタンスタイプ：`t2.micro`（無料利用枠対象）
- ネットワーク：手順 4.1 の VPC ／ 手順 4.2 のパブリックサブネット
- パブリック IP の自動割り当て：**有効**
- セキュリティグループ：手順 4.6 で作成したもの
- ユーザーデータ：下記のスクリプトを貼り付け（手順 4.8）

### 4.8. nginx のインストール・起動（ユーザーデータ）

起動時に自動で nginx を導入・起動するため、ユーザーデータに以下を設定します。

```bash
#!/bin/bash
# nginx をインストールして起動し、おしゃれな稼働確認ページを配信する
dnf install -y nginx
systemctl enable --now nginx

# 配信するページ（デフォルトの Welcome ページを上書き）
cat > /usr/share/nginx/html/index.html <<'HTMLEOF'
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>稼働中 — Amazon EC2 + nginx</title>
<style>
  :root{
    --ink:#0A0F1A;
    --panel:#0F1626;
    --line:#20304A;
    --text:#EAF1FA;
    --muted:#8A99AF;
    --soft:#B7C4D6;
    --accent:#FF9900;
    --ok:#35D6A0;
    --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
    --sans:system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI",Meiryo,sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{
    font-family:var(--sans);
    color:var(--text);
    background:var(--ink);
    min-height:100%;
    display:grid;
    place-items:center;
    padding:28px 20px;
    line-height:1.5;
    -webkit-font-smoothing:antialiased;
  }
  body::before{
    content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
    background:
      radial-gradient(680px 420px at 82% -8%, rgba(255,153,0,.16), transparent 60%),
      radial-gradient(720px 520px at -6% 108%, rgba(53,214,160,.12), transparent 60%),
      radial-gradient(900px 700px at 50% 50%, rgba(32,48,74,.35), transparent 70%);
  }
  .panel{
    position:relative;z-index:1;
    width:min(660px,100%);
    background:linear-gradient(180deg,rgba(20,30,48,.72),rgba(12,19,32,.82));
    border:1px solid var(--line);
    border-radius:18px;
    padding:clamp(26px,5vw,44px);
    box-shadow:0 30px 80px -40px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.04);
    backdrop-filter:blur(6px);
  }
  .panel::before{
    content:"";position:absolute;left:clamp(26px,5vw,44px);right:clamp(26px,5vw,44px);top:0;height:1px;
    background:linear-gradient(90deg,transparent,var(--accent),transparent);opacity:.6;
  }

  .eyebrow{
    display:inline-flex;align-items:center;gap:9px;
    font-family:var(--mono);font-size:12px;letter-spacing:.2em;text-transform:uppercase;
    color:var(--muted);
  }
  .status-dot{width:9px;height:9px;border-radius:50%;background:var(--ok);
    box-shadow:0 0 0 0 rgba(53,214,160,.55);animation:beat 2.4s ease-out infinite}
  .eyebrow b{color:var(--ok);font-weight:600}

  h1{
    margin:20px 0 0;
    font-size:clamp(1.55rem,4.6vw,2.5rem);
    line-height:1.16;letter-spacing:-.02em;font-weight:700;
  }
  h1 .amp{color:var(--accent)}
  .lead{
    margin-top:16px;max-width:52ch;
    color:var(--soft);font-size:clamp(.95rem,2.4vw,1.05rem);
  }

  .route{
    display:flex;flex-wrap:wrap;align-items:center;gap:8px 9px;
    margin:30px 0 6px;
  }
  .route .node{
    font-family:var(--mono);font-size:12.5px;color:var(--muted);
    padding:8px 12px;border:1px solid var(--line);border-radius:9px;
    background:rgba(255,255,255,.015);white-space:nowrap;
    opacity:0;transform:translateY(7px);animation:rise .55s cubic-bezier(.2,.7,.2,1) both;
  }
  .route .arrow{
    color:var(--line);font-family:var(--mono);font-size:15px;
    opacity:0;animation:rise .55s ease both;
  }
  .route .here{
    color:var(--ink);background:var(--accent);border-color:var(--accent);font-weight:700;
    box-shadow:0 0 0 0 rgba(255,153,0,.5);
  }
  .route .here.lit{animation:rise .55s ease both, ring 1.4s ease-out .1s 1}
  .route :nth-child(1){animation-delay:.05s}
  .route :nth-child(2){animation-delay:.13s}
  .route :nth-child(3){animation-delay:.21s}
  .route :nth-child(4){animation-delay:.29s}
  .route :nth-child(5){animation-delay:.37s}
  .route :nth-child(6){animation-delay:.45s}
  .route :nth-child(7){animation-delay:.53s}
  .route :nth-child(8){animation-delay:.61s}
  .route :nth-child(9){animation-delay:.69s}
  .route :nth-child(10){animation-delay:.77s}
  .route :nth-child(11){animation-delay:.85s}

  .meta{
    display:grid;grid-template-columns:repeat(2,1fr);gap:1px;
    margin-top:30px;border:1px solid var(--line);border-radius:12px;overflow:hidden;
    background:var(--line);
  }
  .meta > div{background:var(--panel);padding:15px 16px}
  .meta dt{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
  .meta dd{margin-top:5px;font-size:14.5px;font-weight:600}
  .meta dd small{color:var(--muted);font-weight:400;font-size:12px}

  .foot{
    display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;
    margin-top:26px;padding-top:18px;border-top:1px solid var(--line);
    font-family:var(--mono);font-size:12px;color:var(--muted);
  }
  .foot .tag{color:var(--ok)}
  .foot #clock{margin-left:auto;color:var(--soft)}

  @media (max-width:430px){
    .meta{grid-template-columns:1fr}
  }
  @media (prefers-reduced-motion:reduce){
    *{animation:none !important}
    .route .node,.route .arrow{opacity:1;transform:none}
  }

  @keyframes rise{to{opacity:1;transform:none}}
  @keyframes beat{
    0%{box-shadow:0 0 0 0 rgba(53,214,160,.5)}
    70%{box-shadow:0 0 0 10px rgba(53,214,160,0)}
    100%{box-shadow:0 0 0 0 rgba(53,214,160,0)}
  }
  @keyframes ring{
    0%{box-shadow:0 0 0 0 rgba(255,153,0,.55)}
    100%{box-shadow:0 0 0 16px rgba(255,153,0,0)}
  }
</style>
</head>
<body>
  <main class="panel">
    <span class="eyebrow"><span class="status-dot"></span>DEPLOYMENT · <b>稼働中 LIVE</b></span>

    <h1>このページは、あなたが構築した<br><span class="amp">サーバー</span>から届いています。</h1>

    <p class="lead">Amazon EC2 の上で動く nginx が、いま HTTP でこのページを配信しています。ネットワークからサーバーまで、自分の手でつないだ経路が通った証拠です。お疲れ様でした。</p>

    <div class="route" aria-label="リクエストの経路: users から Internet Gateway、Public Subnet、Security Group、EC2 上の nginx を経てこのページへ">
      <span class="node">users</span>
      <span class="arrow">&rsaquo;</span>
      <span class="node">Internet Gateway</span>
      <span class="arrow">&rsaquo;</span>
      <span class="node">Public Subnet</span>
      <span class="arrow">&rsaquo;</span>
      <span class="node">Security Group</span>
      <span class="arrow">&rsaquo;</span>
      <span class="node">EC2 · nginx</span>
      <span class="arrow">&rsaquo;</span>
      <span class="node here lit">このページ</span>
    </div>

    <dl class="meta">
      <div><dt>Region</dt><dd>ap-northeast-1 <small>東京</small></dd></div>
      <div><dt>Network</dt><dd>Amazon VPC <small>10.0.0.0/16</small></dd></div>
      <div><dt>Compute</dt><dd>Amazon EC2</dd></div>
      <div><dt>Web server</dt><dd>nginx</dd></div>
    </dl>

    <div class="foot">
      <span class="tag">200 OK</span>
      <span>GET /</span>
      <span>port 80</span>
      <span id="clock">--:--:--</span>
    </div>
  </main>

  <script>
    function two(n){return (n<10?'0':'')+n;}
    function tick(){
      var d=new Date();
      var el=document.getElementById('clock');
      if(el){el.textContent=two(d.getHours())+':'+two(d.getMinutes())+':'+two(d.getSeconds());}
    }
    tick(); setInterval(tick,1000);
  </script>
</body>
</html>
HTMLEOF
```

> 💡 手動で入れたい場合は、EC2 Instance Connect でインスタンスに接続し、上記の各コマンドを（先頭に `sudo` を付けて）順に実行してください。

## ▶️ 5. 実行方法（動作確認）

### 5.1. パブリックIPの確認

EC2 コンソールで対象インスタンスを選択し、「パブリック IPv4 アドレス」を確認します。

### 5.2. ブラウザでアクセス

```
http://<パブリックIPv4アドレス>
```

実行例:

```
http://203.0.113.10
→ 「このページは、あなたが構築したサーバーから届いています。」のページが表示されれば成功
```

> ⚠️ `https://` ではなく `http://` でアクセスしてください（本演習では 80 番ポートのみ許可しています）。

## 📘 6. 各コンポーネントの説明

- **VPC（`10.0.0.0/16`）**：AWS 上に用意した専用のプライベートネットワーク。この中にサブネットやリソースを配置します。
- **パブリックサブネット（`10.0.0.0/24`）**：VPC を区切ったネットワークの一区画。ルートテーブルで IGW への経路を持つため「パブリック」になります。
- **インターネットゲートウェイ（IGW）**：VPC とインターネットをつなぐ出入口。VPC にアタッチして使います。
- **ルートテーブル**：通信の経路を決める表。`0.0.0.0/0 → IGW` を設定することで、サブネットからインターネットへ出られるようになります。
- **セキュリティグループ**：インスタンス単位の仮想ファイアウォール。ここで HTTP・80 を許可することで、外部からの Web アクセスを受け付けます。
- **EC2 インスタンス（nginx）**：Web サーバー本体。nginx は EC2 の上で動くソフトウェアです（EC2 の外にある独立した機器ではありません）。

## 📂 リソース構成

```
Region: ap-northeast-1
└── VPC (10.0.0.0/16)
    ├── Internet Gateway（VPCにアタッチ）
    ├── Route Table（0.0.0.0/0 → IGW）
    └── Public Subnet (10.0.0.0/24)
        └── Security Group（インバウンド HTTP:80 許可）
            └── EC2 インスタンス（nginx 稼働）
```

## 🧹 後片付け（重要）

料金が発生し続けないよう、演習が終わったら**依存関係の逆順**で削除します。

1. EC2 インスタンスを終了（Terminate）する
2. インターネットゲートウェイを VPC からデタッチして削除する
3. サブネットを削除する
4. セキュリティグループを削除する
5. VPC を削除する（関連するルートテーブルもあわせて整理する）
6. 使わなくなった IAM アクセスキーは、AWS コンソールで無効化・削除しておく

## 🔧 トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| ブラウザでページが表示されない（タイムアウト） | セキュリティグループで HTTP・80 が許可されていない | 手順 4.6 でインバウンドに HTTP:80 を追加する |
| ブラウザでページが表示されない（タイムアウト） | ルートテーブルに `0.0.0.0/0 → IGW` が無い／サブネット未関連付け | 手順 4.4・4.5 を確認する |
| ブラウザでページが表示されない | IGW が VPC にアタッチされていない | 手順 4.3 で IGW を VPC にアタッチする |
| インスタンスにパブリックIPが無い | 起動時に「パブリックIP自動割り当て」が無効 | 手順 4.7 で有効にして起動し直す |
| ページが表示されない（IPは通る） | nginx が起動していない | インスタンスに接続し `systemctl status nginx` を確認、`systemctl enable --now nginx` で起動 |
| `https://` でアクセスできない | 443 番ポートを許可していない | `http://` でアクセスする（本演習は 80 番のみ） |

## 📚 参考資料

- Amazon VPC ドキュメント
- Amazon EC2 ドキュメント
- nginx ドキュメント

## 📝 補足・メモ

特になし。
