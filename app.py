import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import uuid
import re
import cloudinary
import cloudinary.uploader

# ==========================================
# 0. ページ設定
# ==========================================
st.set_page_config(page_title="PM Request App", layout="wide")

# ==========================================
# Cloudinary 初期設定
# ==========================================
cloudinary.config(
    cloud_name = st.secrets["cloudinary"]["cloud_name"],
    api_key = st.secrets["cloudinary"]["api_key"],
    api_secret = st.secrets["cloudinary"]["api_secret"],
    secure = True
)

# ==========================================
# 1. データベース・アップロード初期設定
# ==========================================
@st.cache_resource
def get_db():
    """Firebaseの初期化とDB接続"""
    if not firebase_admin._apps:
        cert_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cert_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

def upload_file(uploaded_file):
    """Cloudinaryへファイルをアップロード"""
    if uploaded_file is None:
        return None
    response = cloudinary.uploader.upload(uploaded_file)
    return response.get('secure_url')

# ==========================================
# 2. メインアプリ（シンプル・完全無料構成）
# ==========================================
db = get_db()

st.title("🛠️ PM依頼アプリ")
user_id = st.text_input("あなたの担当者ID（または識別名）を入力してください", "野口")
st.divider()

tab1, tab2 = st.tabs(["📝 依頼する", "🔧 対応する"])

# ------------------------------------------
# タブ1: 依頼者画面
# ------------------------------------------
with tab1:
    st.subheader("新規依頼フォーム")
    with st.form("request_form"):
        title = st.text_input("依頼のタイトル（必須）")
        description = st.text_area("詳細（任意）")
        uploaded_file = st.file_uploader("写真やファイルを添付（任意）", type=["jpg", "png", "pdf", "xlsx", "csv"])
        
        if st.form_submit_button("依頼を送信"):
            if not title.strip():
                st.error("⚠️ タイトルを入力してください。")
            else:
                file_url = None
                if uploaded_file:
                    with st.spinner("ファイルをアップロード中..."):
                        file_url = upload_file(uploaded_file)
                
                doc_ref = db.collection('requests').document()
                doc_ref.set({
                    'title': title,
                    'description': description,
                    'status': 'approved',
                    'requester_email': user_id,
                    'attachment_url': file_url,
                    'created_at': firestore.SERVER_TIMESTAMP
                })
                
                st.success("✅ 依頼を送信しました！「対応する」タブに反映されます。")

# ------------------------------------------
# タブ2: PM画面（作業担当）
# ------------------------------------------
with tab2:
    st.subheader("対応待ち・対応中のタスク一覧")
    docs_approved = db.collection('requests').where(filter=FieldFilter('status', '==', 'approved')).stream()
    docs_in_progress = db.collection('requests').where(filter=FieldFilter('status', '==', 'in_progress')).stream()
    
    all_tasks = [{"id": d.id, **d.to_dict()} for d in docs_approved] + [{"id": d.id, **d.to_dict()} for d in docs_in_progress]
    
    if not all_tasks:
        st.info("現在、対応待ちのタスクはありません。")
        
    for req in all_tasks:
        status_text = "🟡 未着手" if req['status'] == 'approved' else "🔵 対応中"
        with st.container(border=True):
            st.write(f"**{req.get('title')}** （{status_text}）- 依頼者: {req.get('requester_email')}")
            st.write(f"詳細: {req.get('description', 'なし')}")
            if req.get('attachment_url'):
                st.markdown(f"[📎 添付ファイルを確認する]({req['attachment_url']})")
            
            if req['status'] == 'approved':
                if st.button("🚀 作業を開始する", key=f"start_{req['id']}"):
                    db.collection('requests').document(req['id']).update({'status': 'in_progress', 'assignee_email': user_id})
                    st.rerun()
                    
            elif req['status'] == 'in_progress':
                if st.button("🏁 作業を完了する", key=f"complete_{req['id']}"):
                    db.collection('requests').document(req['id']).update({'status': 'completed', 'updated_at': firestore.SERVER_TIMESTAMP})
                    st.success("タスク完了！")
                    st.rerun()