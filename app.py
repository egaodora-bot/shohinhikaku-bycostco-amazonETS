import datetime
import sqlite3
import pandas as pd
import streamlit as st

# データベースの初期化
DB_NAME = "database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
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
  # SELECT句を正しく記述するように修正
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
        "💡 まだ価格データが登録されていません。左側のメニューから「商品・価格の登録」を選んでデータを追加してください。"
    )
  else:
    # 商品ごとの横並び（ピボットテーブル風）表示
    st.markdown(
        "##### 📊 店舗別・商品別の単位単価一覧（左右に店舗ごとの単価を比較）"
    )

    # 単位あたり価格を店舗ごとに横並びにする
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
  st.markdown("#### 📝 商品・価格の新規登録 / 更新")

  conn = sqlite3.connect(DB_NAME)
  products_df = pd.read_sql("SELECT * FROM products", conn)
  conn.close()

  product_names = (
      products_df["name"].tolist() if not products_df.empty else []
  )

  with st.form("register_form"):
    st.markdown("##### 1. 商品情報")
    is_new_product = st.checkbox("新しい商品を追加する")

    if is_new_product or not product_names:
      new_prod_name = st.text_input(
          "商品名（例: メリーズパンツ Lサイズ、洗剤〇〇など）"
      )
      category = st.selectbox(
          "カテゴリ",
          ["日用品（消耗品）", "食品・飲料", "家電・ガジェット", "その他"],
      )
      unit_name = st.text_input(
          "単位の基準（例: ml, g, 個, m, 枚 など）", value="個"
      )
    else:
      selected_prod = st.selectbox("既存商品から選択", product_names)

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
      conn = sqlite3.connect(DB_NAME)
      cursor = conn.cursor()

      if is_new_product or not product_names:
        cursor.execute(
            "INSERT INTO products (name, category, unit_name) VALUES (?, ?,"
            " ?)",
            (new_prod_name, category, unit_name),
        )
        conn.commit()
        product_id = cursor.lastrowid
        u_name = unit_name
      else:
        product_id = products_df[products_df["name"] == selected_prod][
            "id"
        ].values[0]
        u_name = products_df[products_df["name"] == selected_prod][
            "unit_name"
        ].values[0]

      unit_price = total_price / total_capacity if total_capacity > 0 else 0
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
          f"✨ 保存完了！ 1{u_name}あたり **{unit_price:.2f}円** で横並び表に反映されました"
          "！"
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
