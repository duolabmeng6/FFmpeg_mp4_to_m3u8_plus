import streamlit as st

def show_navigation():
    with st.sidebar:
        st.title("🎯 功能导航")
        st.page_link("main.py", label="主页", icon="🏠")
        st.page_link("pages/1_convert.py", label="视频转换", icon="🔄")
        st.page_link("pages/2_preview.py", label="视频预览", icon="📺") 
