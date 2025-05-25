import streamlit as st
from components.navigation import show_navigation

# 设置页面配置
st.set_page_config(
    page_title="MP4转M3U8工具",
    page_icon="🎬",
    layout="wide"
)

def main():
    # 显示导航菜单
    show_navigation()
    
    st.title("🎬 MP4转M3U8工具")
    
    st.markdown("""
    ### 👋 欢迎使用MP4转M3U8工具！
    
    这是一个强大的视频转换工具，可以帮助你将MP4视频转换为HLS格式（M3U8）。
    
    #### ✨ 主要功能：
    
    1. 🔄 **视频转换**
       - 支持多种编码器（CPU、GPU加速）
       - 支持多种分辨率输出
       - 支持视频加密
       - 自动生成多清晰度版本
    
    2. 📺 **在线预览**
       - 支持在线播放转换后的视频
       - 支持清晰度切换
       - 支持视频缩略图
    
    #### 🚀 开始使用：
    
    请在左侧边栏选择需要使用的功能：
    - 🔄 视频转换：将MP4文件转换为M3U8格式
    - 📺 视频预览：预览已转换的视频文件
    
    #### 💡 使用提示：
    
    - 确保已安装FFmpeg
    - 建议使用硬件加速以获得更快的转换速度
    - 可以根据需要选择不同的清晰度
    - 支持视频加密保护
    """)

if __name__ == "__main__":
    main() 
