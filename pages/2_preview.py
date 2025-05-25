import streamlit as st
import os
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import socket
from components.navigation import show_navigation

# 设置页面配置
st.set_page_config(
    page_title="MP4转M3U8 - 预览",
    page_icon="🎥",
    layout="wide"
)

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_http_server():
    """启动支持CORS的HTTP服务器"""
    port = 8000
    while is_port_in_use(port):
        port += 1
    
    server = HTTPServer(('localhost', port), CORSHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return port

class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
        
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

# 在全局范围启动HTTP服务器
HTTP_SERVER_PORT = start_http_server()

def main():
    # 显示导航菜单
    show_navigation()
    
    st.title("📺 视频预览")
    
    # 扫描output目录
    output_dirs = []
    if os.path.exists("output"):
        output_dirs = [d for d in os.listdir("output") if os.path.isdir(os.path.join("output", d))]
    
    if not output_dirs:
        st.warning("⚠️ 还没有任何转换好的视频")
        return
    
    # 获取查询参数
    video_path = st.query_params.get("video", None)
    
    if video_path:
        # 显示播放器
        show_player(video_path)
    else:
        # 显示视频列表
        show_video_list(output_dirs)

def show_player(video_dir):
    """显示视频播放器"""
    # 获取视频信息
    master_playlist = os.path.join(video_dir, "master.m3u8")
    thumbnail_path = os.path.join(video_dir, "thumbnail.jpg")
    if st.button("⬅️ 返回列表"):
        st.query_params.clear()
        st.rerun()
    # 显示视频标题
    st.title(f"🎬 正在播放: {os.path.basename(video_dir)}")
    
    # 显示可用的清晰度
    available_resolutions = []
    resolution_map = {
        "4k": "4K (3840x2160)",
        "2k": "2K (2560x1440)",
        "1080p": "1080P (1920x1080)",
        "720p": "720P (1280x720)",
        "480p": "480P (854x480)",
        "360p": "360P (640x360)",
        "raw": "原始分辨率"
    }
    
    for subdir in os.listdir(video_dir):
        if os.path.isdir(os.path.join(video_dir, subdir)) and subdir in resolution_map:
            available_resolutions.append((subdir, resolution_map[subdir]))
    
    # 按清晰度排序
    resolution_order = {"4k": 0, "2k": 1, "1080p": 2, "720p": 3, "480p": 4, "360p": 5, "raw": 6}
    available_resolutions.sort(key=lambda x: resolution_order.get(x[0], 999))
    
    # 创建清晰度选择的按钮组
    st.write("### 📊 选择清晰度")
    resolution_cols = st.columns(len(available_resolutions))
    
    # 初始化当前清晰度
    if 'current_resolution' not in st.session_state:
        st.session_state.current_resolution = None
    
    for i, (res_key, display_name) in enumerate(available_resolutions):
        with resolution_cols[i]:
            button_style = "primary" if st.session_state.current_resolution == res_key else "secondary"
            if st.button(display_name, key=f"res_{res_key}", type=button_style):
                st.session_state.current_resolution = res_key
                st.rerun()
    
    # 显示播放器
    if os.path.exists(master_playlist):
                # 添加返回按钮


        # 确定要播放的播放列表
        current_resolution = st.session_state.get('current_resolution')
        if current_resolution:
            playlist_path = os.path.join(video_dir, current_resolution, "playlist.m3u8")
        else:
            playlist_path = master_playlist

        # 生成视频播放器的HTML代码
        player_html = f"""
        <div style="width: 100%; padding-top: 56.25%; position: relative; background: #000; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <video 
                id="player" 
                controls 
                style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain;"
                poster="http://localhost:{HTTP_SERVER_PORT}/{thumbnail_path if os.path.exists(thumbnail_path) else ''}"
            >
                <source src="http://localhost:{HTTP_SERVER_PORT}/{playlist_path}" type="application/x-mpegURL">
                您的浏览器不支持HTML5视频播放
            </video>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <script>
            function initPlayer() {{
                const video = document.getElementById('player');
                if (!video) return;
                
                const videoSrc = 'http://localhost:{HTTP_SERVER_PORT}/{playlist_path}';
                
                if (Hls.isSupported()) {{
                    const hls = new Hls({{
                        debug: false,
                        enableWorker: true,
                        lowLatencyMode: true,
                        backBufferLength: 90
                    }});
                    
                    hls.loadSource(videoSrc);
                    hls.attachMedia(video);
                    hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                        video.play().catch(function(error) {{
                            console.log("播放器自动播放失败:", error);
                        }});
                    }});
                    
                    hls.on(Hls.Events.ERROR, function(event, data) {{
                        if (data.fatal) {{
                            switch(data.type) {{
                                case Hls.ErrorTypes.NETWORK_ERROR:
                                    console.log("网络错误，尝试恢复...");
                                    hls.startLoad();
                                    break;
                                case Hls.ErrorTypes.MEDIA_ERROR:
                                    console.log("媒体错误，尝试恢复...");
                                    hls.recoverMediaError();
                                    break;
                                default:
                                    console.log("无法恢复的错误:", data);
                                    hls.destroy();
                                    break;
                            }}
                        }}
                    }});
                }}
                else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                    video.src = videoSrc;
                }}
            }}

            // 确保DOM加载完成后初始化播放器
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initPlayer);
            }} else {{
                initPlayer();
            }}
        </script>
        <style>
            #player::-webkit-media-controls-panel {{
                background: rgba(0, 0, 0, 0.6);
            }}
            #player::-webkit-media-controls-play-button,
            #player::-webkit-media-controls-timeline,
            #player::-webkit-media-controls-current-time-display,
            #player::-webkit-media-controls-time-remaining-display,
            #player::-webkit-media-controls-mute-button,
            #player::-webkit-media-controls-toggle-closed-captions-button,
            #player::-webkit-media-controls-volume-slider {{
                color: #fff;
            }}
            #player::-webkit-media-controls-timeline {{
                background: rgba(255, 255, 255, 0.2);
                border-radius: 2px;
                height: 4px;
            }}
            #player:focus {{
                outline: none;
            }}
            #player:hover {{
                box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
            }}
        </style>
        """
        st.components.v1.html(player_html, height=800)
        

def show_video_list(output_dirs):
    """显示视频列表"""
    # 获取目录及其创建时间
    dir_times = []
    for dir_name in output_dirs:
        video_dir = os.path.join("output", dir_name)
        try:
            dir_time = datetime.fromtimestamp(os.path.getctime(video_dir))
            dir_times.append((dir_name, dir_time))
        except:
            dir_times.append((dir_name, datetime.fromtimestamp(0)))  # 如果获取时间失败，设为最早时间
    
    # 按创建时间倒序排序
    dir_times.sort(key=lambda x: x[1], reverse=True)
    sorted_dirs = [d[0] for d in dir_times]
    
    # 创建多列布局
    cols = st.columns(3)
    col_index = 0
    
    for dir_name in sorted_dirs:
        video_dir = os.path.join("output", dir_name)
        thumbnail_path = os.path.join(video_dir, "thumbnail.jpg")
        master_playlist = os.path.join(video_dir, "master.m3u8")
        
        # 获取文件夹创建时间
        try:
            dir_time = datetime.fromtimestamp(os.path.getctime(video_dir))
            formatted_time = dir_time.strftime("%Y-%m-%d %H:%M:%S")
        except:
            formatted_time = "未知时间"
            
        # 获取可用的清晰度
        available_resolutions = []
        resolution_map = {
            "4k": "4K",
            "2k": "2K",
            "1080p": "1080P",
            "720p": "720P",
            "480p": "480P",
            "360p": "360P",
            "raw": "原始分辨率"
        }
        
        for subdir in os.listdir(video_dir):
            if os.path.isdir(os.path.join(video_dir, subdir)) and subdir in resolution_map:
                available_resolutions.append(resolution_map[subdir])
        
        resolutions_text = " / ".join(sorted(available_resolutions)) if available_resolutions else "未知清晰度"
        
        with cols[col_index]:
            # 创建一个带边框的容器
            with st.container():
                st.markdown('<div class="video-item">', unsafe_allow_html=True)
                
                # 显示缩略图
                if os.path.exists(thumbnail_path):
                    st.image(thumbnail_path, width=280)
                else:
                    st.markdown("""
                        <div style="
                            width: 280px;
                            height: 158px;
                            background-color: #2d2d2d;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            border-radius: 5px;
                            color: #ffffff;
                            font-size: 16px;
                            margin-bottom: 10px;
                        ">
                            <div style="text-align: center;">
                                <div style="font-size: 24px; margin-bottom: 5px;">🎬</div>
                                <div>无封面预览</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                
                # 显示视频信息
                st.markdown(f"**📂 {dir_name}**")
                st.markdown(f"⏰ {formatted_time}")
                st.markdown(f"🎯 {resolutions_text}")
                
                # 添加预览按钮
                if st.button(f"▶️ 预览播放", key=f"play_{dir_name}"):
                    video_path = os.path.join("output", dir_name)
                    st.query_params["video"] = video_path
                    st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("---")
        
        # 更新列索引
        col_index = (col_index + 1) % 3

if __name__ == "__main__":
    main() 
