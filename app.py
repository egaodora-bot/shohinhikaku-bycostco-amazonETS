import datetime
import sqlite3
import pandas as pd
import streamlit as st

# データベースの初期化と定番商品の初期登録
DB_NAME = "database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            unit_name TEXT
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            store_type TEXT,
            store_name TEXT,
            total_price REAL,
            total_capacity REAL,
            unit_price REAL,
            is_sale INTEGER,
            updated_at TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)

  # 定番日用品の初期データ（まだデータがない場合のみ自動追加）
  default_products = [
      ("トイレットペーパー", "日用品（消耗品）", "m"),
      ("ティッシュペーパー", "日用品（消耗品）", "箱"),
      ("洗濯用液体洗剤", "日用品（消耗品）", "ml"),
      ("食器用洗剤", "日用品（消耗品）", "ml"),
      ("お米 (5kg)", "食品・飲料", "kg"),
  ]
  for p_name, p_cat, p_unit in default_products:
    cursor.execute(
        """
            INSERT OR IGNORE INTO products (name, category, unit_name) 
            VALUES (?, ?, ?)
        """,
        (p_name, p_cat, p_unit),
    )

  conn.commit()
  conn.close()


init_db()

st.set_page_config(
    page_title="買い物価格比較 & 底値DB", page_icon="🛒", layout="wide"
)

st.markdown("### 🛒 買い物価格比較 & 底値DB")
st.caption(
    "リポジトリ: `shohinhikaku-bycostco-amazonETS` | 周辺店舗・コストコ・Amazon"
    " 比較"
)

# サイドバー：メニュー選択
menu = st.sidebar.selectbox(
    "メニュー", ["価格比較・検索", "商品・価格の登録", "店舗マスタ設定"]
)

# --- ① 価格比較・検索画面 ---
if menu == "価格比較・検索":
  st.markdown("#### 🔍 店舗横並び・単位単価チェック")

  conn = sqlite3.connect(DB_NAME)
  query = """
        SELECT 
            p.id as product_id, 
            p.name as 商品名, 
            p.category as カテゴリ, 
            p.unit_name as 単位,
            pr.store_name as 店舗名, 
            pr.total_price as 総額, 
            pr.unit_price as 単位あたり価格, 
            pr.is_sale as 特売フラグ, 
            pr.updated_at as 更新日
        FROM prices pr
        JOIN products p ON pr.product_id = p.id
    """
  df = pd.read_sql(query, conn)
  conn.close()

  if df.empty:
    st.info(
        "💡 まだ価格データが登録されていません。左側のメニューから「商品・価格の登録」を行ってください。"
    )
  else:
    st.markdown(
        "##### 📊 店舗別・商品別の単位単価一覧（左右に店舗ごとの単価を比較）"
    )

    pivot_price = df.pivot_table(
        index=["商品名", "単位"],
        columns="店舗名",
        values="単位あたり価格",
        aggfunc="min",
    )

    st.dataframe(pivot_price, use_container_width=True)
    st.caption("※数値は「1単位あたり」の価格です。空欄はその店舗での価格データが未登録のものです。")

    st.markdown("##### 💡 商品ごとの詳細比較")
    target_product = st.selectbox("詳細を見たい商品を選択", df["商品名"].unique())
    prod_df = df[df["商品名"] == target_product].sort_values("単位あたり価格")

    st.table(
        prod_df[[
            "店舗名",
            "総額",
            "単位あたり価格",
            "特売フラグ",
            "更新日",
        ]]
    )

    if not prod_df.empty:
      min_row = prod_df.iloc[0]
      st.success(
          f"🏆 **現在の最安値:** 【{min_row['店舗名']}】 で **1{min_row['単位']}あたり"
          f" {min_row['単位あたり価格']:.2f} 円** です！ (総額: {min_row['総額']}円)"
      )

# --- ② 商品・価格の登録画面 ---
elif menu == "商品・価格の登録":
  st.markdown("#### 📝 価格の登録（自由入力・自動登録対応）")
  st.write(
      "既存の定番商品を選ぶか、新しい商品名をそのまま入力してください。登録がない商品は自動で追加されます。"
  )

  conn = sqlite3.connect(DB_NAME)
  products_df = pd.read_sql("SELECT * FROM products", conn)
  conn.close()

  product_names = (
      products_df["name"].tolist() if not products_df.empty else []
  )

  with st.form("register_form"):
    st.markdown("##### 1. 商品の選択 または 入力")
    # セレクトボックスと自由入力を組み合わせる（セレクトボックスにないものは新規追加扱いに）
    input_product_name = st.selectbox(
        "商品名（リストから選択、または下に新しい名前を入力）",
        ["-- 新規商品を直接入力する --"] + product_names,
    )

    new_prod_name = st.text_input(
        "※上で「-- 新規商品を直接入力する --」を選んだ場合は、こちらに商品名を入力",
        placeholder="例: メリーズパンツ Lサイズ",
    )

    col1, col2 = st.columns(2)
    with col1:
      category = st.selectbox(
          "カテゴリ",
          ["日用品（消耗品）", "食品・飲料", "家電・ガジェット", "その他"],
      )
    with col2:
      unit_name = st.text_input(
          "単位の基準（例: ml, g, 個, m, 箱 など）", value="個"
      )

    st.markdown("##### 2. 店舗と価格情報")
    store_type = st.selectbox("店舗タイプ", ["コストコ", "近隣店舗", "Amazon"])

    if store_type == "コストコ":
      store_name = st.selectbox(
          "コストコ店舗",
          [
              "コストコ つくば倉庫店",
              "コストコ 壬生倉庫店",
              "コストコ その他",
          ],
      )
    elif store_type == "近隣店舗":
      store_name = st.text_input(
          "近隣店舗名（例: ウエルシア 古河店、カインズ 結城店など）"
      )
    else:
      store_name = "Amazon（定期おトク便）"

    total_price = st.number_input(
        "購入総額（税込・円）", min_value=0.0, step=10.0
    )
    total_capacity = st.number_input(
        "そのときの総容量・数量（例: 44個入りなら '44'、1500mlなら"
        " '1500'）",
        min_value=0.1,
        step=1.0,
        value=1.0,
    )

    is_sale = st.checkbox("特売品 / セール価格である")

    submitted = st.form_submit_button("データベースに保存して比較表を更新")

    if submitted:
      # 登録する商品名の決定
      target_name = (
          new_prod_name.strip()
          if input_product_name == "-- 新規商品を直接入力する --"
          else input_product_name
      )

      if not target_name:
        st.error("⚠️ 商品名を入力するか、選択してください。")
      else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 商品が既存か確認し、なければ自動登録
        cursor.execute("SELECT id, unit_name FROM products WHERE name = ?", (target_name,))
        row = cursor.fetchone()

        if row:
          product_id = row[0]
          u_name = row[1]
        else:
          cursor.execute(
              "INSERT INTO products (name, category, unit_name) VALUES (?, ?,"
              " ?)",
              (target_name, category, unit_name),
          )
          conn.commit()
          product_id = cursor.lastrowid
          u_name = unit_name

        unit_price = (
            total_price / total_capacity if total_capacity > 0 else 0
        )
        today = datetime.date.today().isoformat()

        cursor.execute(
            """
                    INSERT INTO prices (product_id, store_type, store_name, total_price, total_capacity, unit_price, is_sale, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
            (
                product_id,
                store_type,
                store_name,
                total_price,
                total_capacity,
                unit_price,
                1 if is_sale else 0,
                today,
            ),
        )
        conn.commit()
        conn.close()
        st.success(
            f"✨ 「{target_name}」の価格を保存しました！ (1{u_name}あたり"
            f" **{unit_price:.2f}円**)"
        )

# --- ③ 店舗マスタ設定画面 ---
elif menu == "店舗マスタ設定":
  st.markdown("#### ⚙️ 店舗エリア・周辺店舗の設定")
  st.write(
      "よく利用するエリアの店舗（コストコ各店や周辺のドラッグストア・スーパーなど）を自由に登録して比較軸を増やせます。"
  )
  st.text_input("自宅・基準となる地域の住所（例: 茨城県古河市...）")
  st.success(
      "お気に入りの周辺店舗を登録しておくことで、価格比較の際に左右の列として表示されやすくなります。"
  )
