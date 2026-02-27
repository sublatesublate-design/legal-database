import streamlit as st
import sqlite3
import pandas as pd
import subprocess
import os
import time
from pathlib import Path
from update_checker import UpdateChecker
import config

# 页面配置
st.set_page_config(
    page_title="法律数据库管理中心",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义样式
st.markdown("""
<style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# 辅助函数
def get_db_stats():
    """获取数据库统计信息"""
    if not Path("legal_database.db").exists():
        return None
    
    conn = sqlite3.connect("legal_database.db")
    try:
        df = pd.read_sql_query("SELECT category, COUNT(*) as count FROM laws GROUP BY category", conn)
        total = df['count'].sum()
        return df, total
    finally:
        conn.close()

def run_script(script_name, args=None):
    """运行 Python 脚本并捕获输出"""
    cmd = ["python", script_name]
    if args:
        cmd.extend(args)
    
    # 在 Windows 上，子进程输出可能是 GBK。使用 errors='replace' 防止崩溃。
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    return process

def migrate_db():
    """确保数据库表结构是最新的"""
    if not Path("legal_database.db").exists():
        return
    conn = sqlite3.connect("legal_database.db")
    cursor = conn.cursor()
    try:
        # 添加 is_amendment 列
        try:
            cursor.execute("ALTER TABLE laws ADD COLUMN is_amendment INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # 添加 base_law_title 列
        try:
            cursor.execute("ALTER TABLE laws ADD COLUMN base_law_title TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()
    finally:
        conn.close()

# 启动时运行迁移
migrate_db()

# --- 侧边栏 ---
st.sidebar.title("🛠️ 管理面板")
st.sidebar.image("https://img.icons8.com/wired/128/000000/law.png", width=100)
st.sidebar.divider()

selected_category = st.sidebar.selectbox("选择法律分类", list(config.CATEGORIES.keys()))
check_pages = st.sidebar.slider("检查最近页数", 1, 10, 1)

# --- 主界面 ---
st.title("⚖️ 国家法律法规数据库管理系统")
st.write("欢迎使用法律数据库自动化工具。在这里您可以检查更新、下载新法规并同步数据。")

# 统计概览
stats = get_db_stats()
if stats:
    df_stats, total_count = stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总计入库法律", f"{total_count} 条")
    with col2:
        st.metric("覆盖分类", f"{len(df_stats)} 个")
    with col3:
        st.metric("最近同步", time.strftime("%Y-%m-%d"))
    
    # 简单的柱状图
    st.bar_chart(df_stats.set_index('category'))

st.divider()

# 功能区
tab1, tab2, tab3, tab4 = st.tabs(["🔍 查新与更新", "📥 批量同步", "🔄 全库深度更新", "📈 数据库浏览"])

with tab1:
    st.subheader(f"检查 [{selected_category}] 的最新变动")
    col_btn, col_info = st.columns([1, 3])
    
    if col_btn.button("开始检查更新"):
        with st.status("正在访问国家法律法规数据库...", expanded=True) as status:
            checker = UpdateChecker()
            new_laws = checker.check_for_updates(selected_category, max_pages=check_pages)
            if new_laws:
                status.update(label=f"检查完成：发现 {len(new_laws)} 个新法律!", state="complete")
                st.session_state['new_laws'] = new_laws
            else:
                status.update(label="检查完成：暂无更新", state="complete")
                st.session_state['new_laws'] = []

    if 'new_laws' in st.session_state and st.session_state['new_laws']:
        st.success(f"发现以下 {len(st.session_state['new_laws'])} 条新法规，建议同步：")
        new_df = pd.DataFrame(st.session_state['new_laws'])
        st.table(new_df[['title', 'publish_date']])
    elif 'new_laws' in st.session_state:
        st.info("目前所有法律已是最新。")

with tab2:
    st.subheader("一键同步操作")
    st.warning("注意：这将启动自动化浏览器，可能需要几分钟时间。")
    
    col1, col2 = st.columns(2)
    
    if col1.button("1. 下载新文件 (Zip)"):
        with st.expander("下载日志", expanded=True):
            log_area = st.empty()
            process = run_script("batch_downloader.py", ["--category", selected_category, "--max-pages", str(check_pages)])
            full_log = ""
            for line in process.stdout:
                full_log += line
                log_area.text(full_log[-2000:]) # 仅保留最后2000字
            process.wait()
            st.success("文件下载完成！")

    if col2.button("2. 处理与入库 (Sync)"):
        with st.expander("处理日志", expanded=True):
            log_area = st.empty()
            process = run_script("process_downloads.py")
            full_log = ""
            for line in process.stdout:
                full_log += line
                log_area.text(full_log[-2000:])
            process.wait()
            st.success("数据转换并入库完成！")

with tab3:
    st.subheader("全库深度更新 (修复+补充)")
    st.info("此功能将遍历所有分类和所有法律状态，重新抓取正文，确保库内数据与官网严格一致。")
    
    col_full, col_empty = st.columns([1, 2])
    if col_full.button("🚀 启动全库深度扫描"):
        with st.expander("实时更新日志", expanded=True):
            log_area = st.empty()
            # 运行全量下载
            process_dl = run_script("batch_downloader.py", ["--max-pages", "50"]) # 限制页数避免无限运行，或者按需调整
            full_log = "--- 开始全量下载 ---\n"
            for line in process_dl.stdout:
                full_log += line
                log_area.text(full_log[-2000:])
            process_dl.wait()
            
            st.write("--- 开始全量入库 ---")
            process_sync = run_script("process_downloads.py")
            for line in process_sync.stdout:
                full_log += line
                log_area.text(full_log[-2000:])
            process_sync.wait()
            st.success("全库深度同步已完成！")

with tab4:
    st.subheader("已入库数据预览")
    if Path("legal_database.db").exists():
        conn = sqlite3.connect("legal_database.db")
        query = """
            SELECT title, publish_date, category, status, is_amendment, base_law_title 
            FROM laws 
            ORDER BY last_updated DESC LIMIT 100
        """
        df_laws = pd.read_sql_query(query, conn)
        
        # 格式化显示
        def format_title(row):
            if row['is_amendment']:
                return f"📝 {row['title']} (针对: {row['base_law_title']})"
            return row['title']
        
        df_laws['显示标题'] = df_laws.apply(format_title, axis=1)
        st.dataframe(df_laws[['显示标题', 'publish_date', 'category', 'status']], use_container_width=True)
        conn.close()
    else:
        st.error("数据库尚未建立，请先执行同步流程。")

# 页脚
st.divider()
st.caption("Powered by Antigravity Legal-DB Hub")
