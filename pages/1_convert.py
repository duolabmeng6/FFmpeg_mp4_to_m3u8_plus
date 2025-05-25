import streamlit as st
import os
import subprocess
import platform
import re
import shutil
import json
from datetime import datetime
import time
import glob
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import socket
import traceback
from components.navigation import show_navigation

# 设置页面配置
st.set_page_config(
    page_title="MP4转M3U8 - 转换",
    page_icon="🎬",
    layout="wide"
)

# 从main2.py复制所需的函数
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

def get_video_info(input_file):
    """获取视频信息"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            input_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"ffprobe failed: {result.stderr}")
        
        info = json.loads(result.stdout)
        return info
    except Exception as e:
        st.error(f"获取视频信息失败: {str(e)}")
        return None

def check_system_environment():
    """检查系统环境并返回可用的编码器信息"""
    env_info = {
        "ffmpeg_installed": False,
        "ffmpeg_version": None,
        "nvidia_gpu": False,
        "intel_qsv": False,
        "videotoolbox": False,
        "cpu_info": None,
        "os_info": platform.system()
    }
    
    # 检查FFmpeg是否安装
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        env_info["ffmpeg_installed"] = True
        try:
            # 获取FFmpeg版本
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            version_match = re.search(r'ffmpeg version (\S+)', result.stdout)
            if version_match:
                env_info["ffmpeg_version"] = version_match.group(1)
            
            # 检查可用的编码器
            encoders = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
            env_info["nvidia_gpu"] = 'h264_nvenc' in encoders.stdout
            env_info["intel_qsv"] = 'h264_qsv' in encoders.stdout
            env_info["videotoolbox"] = 'h264_videotoolbox' in encoders.stdout
        except Exception as e:
            st.error(f"检查FFmpeg信息时出错: {str(e)}")
    
    # 获取CPU信息
    try:
        if platform.system() == "Darwin":  # macOS
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True)
            env_info["cpu_info"] = result.stdout.strip()
        elif platform.system() == "Linux":
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        env_info["cpu_info"] = line.split(':')[1].strip()
                        break
        elif platform.system() == "Windows":
            result = subprocess.run(['wmic', 'cpu', 'get', 'name'], capture_output=True, text=True)
            env_info["cpu_info"] = result.stdout.split('\n')[1].strip()
    except Exception as e:
        env_info["cpu_info"] = "无法获取CPU信息"
    
    return env_info

def main():
    # 显示导航菜单
    show_navigation()
    
    st.title("🎬 MP4转M3U8 FFmpeg命令生成器")
    
    # 初始化session_state
    if 'video_encoder' not in st.session_state:
        st.session_state.video_encoder = 'copy'
    if 'resolutions' not in st.session_state:
        st.session_state.resolutions = ["1920x1080"]
    if 'audio_encoder' not in st.session_state:
        st.session_state.audio_encoder = 'copy'
    if 'audio_bitrate' not in st.session_state:
        st.session_state.audio_bitrate = '128k'
    if 'segment_time' not in st.session_state:
        st.session_state.segment_time = '6'
    if 'encryption_enabled' not in st.session_state:
        st.session_state.encryption_enabled = False
   
    # 检查系统环境
    env_info = check_system_environment()
    
    # 显示系统环境信息
    st.header("🖥️ 系统环境检测")
    col1, col2 = st.columns(2)
    
    with col1:
        if env_info["ffmpeg_installed"]:
            st.success(f"✅ FFmpeg 已安装 (版本: {env_info['ffmpeg_version']})")
        else:
            st.error("❌ FFmpeg 未安装，请先安装FFmpeg")
            st.markdown("""
            **安装指南：**
            - Mac: `brew install ffmpeg`
            - Linux: `sudo apt install ffmpeg` 或 `sudo yum install ffmpeg`
            - Windows: 访问 [FFmpeg官网](https://ffmpeg.org/download.html) 下载
            """)
            return
        
        st.info(f"💻 CPU: {env_info['cpu_info']}")
        st.info(f"🖥️ 操作系统: {env_info['os_info']}")
    
    with col2:
        encoders_available = []
        if env_info["nvidia_gpu"]:
            encoders_available.append("✅ NVIDIA GPU加速可用 (h264_nvenc)")
        else:
            encoders_available.append("❌ NVIDIA GPU加速不可用")
            
        if env_info["intel_qsv"]:
            encoders_available.append("✅ Intel 核显加速可用 (h264_qsv)")
        else:
            encoders_available.append("❌ Intel 核显加速不可用")
            
        if env_info["videotoolbox"]:
            encoders_available.append("✅ Mac 硬件加速可用 (h264_videotoolbox)")
        else:
            encoders_available.append("❌ Mac 硬件加速不可用")
            
        for encoder_info in encoders_available:
            st.info(encoder_info)
    
    st.markdown("---")
    
    # 文件设置
    st.header("📁 文件设置")
    col1, col2 = st.columns(2)
    with col1:
        input_file = st.text_input(
            "输入文件路径",
            value="input.mp4",
            help="要转换的MP4视频文件路径",
            key="input_file"
        )
        
        # 添加获取视频信息按钮
        if st.button("获取视频信息", key="get_video_info"):
            if os.path.exists(input_file):
                video_info = get_video_info(input_file)
                if video_info:
                    st.success("✅ 成功获取视频信息")
                    # 显示视频信息
                    video_stream = None
                    audio_stream = None
                    if 'streams' in video_info:
                        for stream in video_info['streams']:
                            if stream.get('codec_type') == 'video':
                                video_stream = stream
                                st.info("📹 视频流信息：")
                                st.json({
                                    '编码器': stream.get('codec_name', 'N/A'),
                                    '分辨率': f"{stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}",
                                    '帧率': stream.get('r_frame_rate', 'N/A'),
                                    '码率': f"{int(int(stream.get('bit_rate', 0))/1000)}kbps" if stream.get('bit_rate') else 'N/A',
                                    '时长': f"{float(stream.get('duration', 0)):.2f}秒" if stream.get('duration') else 'N/A'
                                })
                            elif stream.get('codec_type') == 'audio':
                                audio_stream = stream
                                st.info("🔊 音频流信息：")
                                st.json({
                                    '编码器': stream.get('codec_name', 'N/A'),
                                    '采样率': f"{stream.get('sample_rate', 'N/A')}Hz",
                                    '声道数': stream.get('channels', 'N/A'),
                                    '码率': f"{int(int(stream.get('bit_rate', 0))/1000)}kbps" if stream.get('bit_rate') else 'N/A'
                                })
                    
                    # 添加推荐参数分析
                    st.info("🎯 推荐转码参数：")
                    
                    # 视频推荐
                    if video_stream:
                        video_codec = video_stream.get('codec_name', '').lower()
                        video_height = video_stream.get('height', 0)
                        video_bitrate = int(video_stream.get('bit_rate', 0))
                        
                        # 视频编码器推荐
                        st.write("📹 视频编码推荐：")
                        if video_codec == 'h264':
                            st.success("✅ 当前视频已经是H.264编码，建议选择'直接复制'模式以获得最快的转换速度")
                            st.session_state.video_encoder = 'copy'
                        else:
                            st.warning(f"⚠️ 当前视频编码为{video_codec}，建议重新编码为H.264以获得最佳兼容性")
                            # 根据系统环境自动选择最佳编码器
                            if env_info["nvidia_gpu"]:
                                st.session_state.video_encoder = 'h264_nvenc'
                                st.success("✅ 已自动选择NVIDIA硬件加速(h264_nvenc)，可大幅提升转码速度")
                            elif env_info["videotoolbox"]:
                                st.session_state.video_encoder = 'h264_videotoolbox'
                                st.success("✅ 已自动选择Mac硬件加速(h264_videotoolbox)，可大幅提升转码速度")
                            elif env_info["intel_qsv"]:
                                st.session_state.video_encoder = 'h264_qsv'
                                st.success("✅ 已自动选择Intel硬件加速(h264_qsv)，可大幅提升转码速度")
                            else:
                                st.session_state.video_encoder = 'libx264'
                                st.info("ℹ️ 未检测到硬件加速，使用CPU编码(libx264)")
                        
                        # 分辨率推荐
                        st.write("📏 分辨率推荐：")
                        resolutions_to_set = []
                        if video_height >= 2160:
                            resolutions_to_set = ["3840x2160", "2560x1440", "1920x1080", "1280x720"]
                            st.info("ℹ️ 检测到4K视频，建议同时生成2K、1080p和720p版本")
                        elif video_height >= 1440:
                            resolutions_to_set = ["2560x1440", "1920x1080", "1280x720"]
                            st.info("ℹ️ 检测到2K视频，建议同时生成1080p和720p版本")
                        elif video_height >= 1080:
                            resolutions_to_set = ["1920x1080", "1280x720"]
                            st.info("ℹ️ 检测到1080p视频，建议同时生成720p版本")
                        elif video_height >= 720:
                            resolutions_to_set = ["1280x720"]
                            st.info("ℹ️ 检测到720p视频，建议保持当前分辨率")
                        else:
                            resolutions_to_set = ["原始分辨率"]
                            st.warning("⚠️ 视频分辨率较低，建议保持原始分辨率")
                        
                        if st.session_state.video_encoder != 'copy':
                            st.session_state.resolutions = resolutions_to_set
                            
                            # 设置推荐码率
                            for resolution in resolutions_to_set:
                                bitrate_key = f"video_bitrate_{resolution}"
                                if resolution == "3840x2160":
                                    st.session_state[bitrate_key] = "15000k"
                                elif resolution == "2560x1440":
                                    st.session_state[bitrate_key] = "9000k"
                                elif resolution == "1920x1080":
                                    st.session_state[bitrate_key] = "4500k"
                                elif resolution == "1280x720":
                                    st.session_state[bitrate_key] = "2500k"
                                elif resolution == "原始分辨率":
                                    st.session_state[bitrate_key] = f"{int(video_bitrate/1000)}k"
                        
                        # 码率信息显示
                        st.write("💾 码率信息：")
                        current_bitrate_mbps = video_bitrate / 1000000
                        if current_bitrate_mbps > 0:
                            st.info(f"ℹ️ 当前视频码率约为{current_bitrate_mbps:.1f}Mbps")
                    
                    # 音频推荐
                    if audio_stream:
                        audio_codec = audio_stream.get('codec_name', '').lower()
                        audio_bitrate = int(audio_stream.get('bit_rate', 0))
                        
                        st.write("🔊 音频编码推荐：")
                        if audio_codec == 'aac':
                            st.success("✅ 当前音频已经是AAC编码，已自动选择'直接复制'模式")
                            st.session_state.audio_encoder = 'copy'
                        else:
                            st.warning(f"⚠️ 当前音频编码为{audio_codec}，已自动设置转换为AAC以获得最佳兼容性")
                            st.session_state.audio_encoder = 'aac'
                            
                            # 设置音频码率
                            current_audio_bitrate_kbps = audio_bitrate / 1000
                            if current_audio_bitrate_kbps > 256:
                                st.session_state.audio_bitrate = '192k'
                            elif current_audio_bitrate_kbps < 64:
                                st.session_state.audio_bitrate = '128k'
                            else:
                                st.session_state.audio_bitrate = f"{int(current_audio_bitrate_kbps)}k"
                    
                    # HLS分片建议
                    st.write("🎬 HLS分片建议：")
                    if video_stream and video_stream.get('duration'):
                        duration = float(video_stream.get('duration'))
                        if duration < 60:  # 小于1分钟
                            st.session_state.segment_time = '2'
                            st.info("ℹ️ 视频较短，已自动设置2秒的分片时长")
                        elif duration < 300:  # 小于5分钟
                            st.session_state.segment_time = '5'
                            st.info("ℹ️ 视频时长适中，已自动设置5秒的分片时长")
                        else:  # 大于5分钟
                            st.session_state.segment_time = '10'
                            st.info("ℹ️ 视频较长，已自动设置10秒的分片时长")
                    
                    st.success("✅ 已根据视频分析自动设置最佳参数，您可以根据需要手动调整")
                    st.markdown("---")
                else:
                    st.error("❌ 无法获取视频信息")
            else:
                st.error("❌ 文件不存在")
    with col2:
        # 生成默认输出目录名：output/年月日_时间戳
        timestamp = int(time.time())
        default_output_dir = os.path.join("output", datetime.now().strftime('%Y%m%d_') + str(timestamp))
        output_dir = st.text_input(
            "输出目录",
            value=default_output_dir,
            help="M3U8文件和分片的输出目录",
            key="output_dir"
        )
        output_name = st.text_input(
            "输出文件名",
            value="playlist",
            help="输出的M3U8播放列表文件名（不含扩展名）",
            key="output_name"
        )

    # 编码设置
    st.header("🎯 编码设置")
    col1, col2 = st.columns(2)
    
    # 视频设置
    with col1:
        st.subheader("📹 视频设置")
        
        # 定义所有编码器选项和描述
        encoder_descriptions = {
            "copy": "直接复制 (保持原始视频流，不重新编码)",
            "libx264": "H.264软件编码 (CPU编码，兼容性最好)",
            "h264_nvenc": "H.264 NVIDIA硬件加速 (N卡加速)",
            "h264_qsv": "H.264 Intel硬件加速 (Intel核显加速)",
            "h264_videotoolbox": "H.264 Mac硬件加速 (Mac系统加速)"
        }
        
        # 生成系统兼容性提示
        compatibility_notes = []
        if env_info["nvidia_gpu"]:
            compatibility_notes.append("✅ 您的系统支持NVIDIA GPU加速编码")
        if env_info["intel_qsv"]:
            compatibility_notes.append("✅ 您的系统支持Intel核显加速编码")
        if env_info["videotoolbox"]:
            compatibility_notes.append("✅ 您的系统支持Mac硬件加速编码")
            
        video_encoder = st.selectbox(
            "视频编码器",
            options=[
                "copy",
                "libx264",
                "h264_nvenc",
                "h264_qsv",
                "h264_videotoolbox"
            ],
            index=0 if st.session_state.video_encoder == 'copy' else list(encoder_descriptions.keys()).index(st.session_state.video_encoder),
            help=f"""
            选择视频处理方式：
            * 直接复制：不对视频进行重新编码，保持原始质量，速度最快
            * H.264软件编码：使用CPU进行编码，兼容性最好，但速度较慢
            * NVIDIA硬件加速：使用NVIDIA显卡加速编码，需要N卡
            * Intel硬件加速：使用Intel核显加速编码，需要Intel CPU
            * Mac硬件加速：使用Mac系统硬件加速，仅支持Mac
            
            系统兼容性检测：
            {chr(10).join(compatibility_notes) if compatibility_notes else "❗ 未检测到支持的硬件加速"}
            
            推荐选择：
            * 如果原视频已经是H.264编码：选择"直接复制"最快
            * 如果需要调整分辨率或码率：
              - 有NVIDIA显卡：优先选择"NVIDIA硬件加速"
              - 有Intel核显：优先选择"Intel硬件加速"
              - 使用Mac：优先选择"Mac硬件加速"
              - 以上都不支持：使用"H.264软件编码"
            """,
            key="video_encoder",
            format_func=lambda x: encoder_descriptions[x]
        )

        # 添加编码器说明
        if video_encoder == "copy":
            st.info("""
            ℹ️ 您选择了直接复制模式：
            * 不会重新编码视频，保持原始视频质量
            * 转换速度最快，不会占用CPU/GPU
            * 适用于：原视频已经是H.264编码，只需要切片
            * 注意：如果原视频编码不兼容，可能需要选择重新编码
            """)
        else:
            st.info("""
            ℹ️ 您选择了重新编码模式：
            * 会对视频进行重新编码，可以调整分辨率和码率
            * 转换时间取决于视频大小和编码设置
            * 适用于：需要调整视频质量或确保兼容性
            * 建议：优先选择硬件加速，可大幅提升转换速度
            """)

        if video_encoder != "copy":
            resolutions = st.multiselect(
                "分辨率",
                options=[
                    "原始分辨率",
                    "3840x2160",
                    "2560x1440",
                    "1920x1080",
                    "1280x720", 
                    "854x480",
                    "640x360"
                ],
                default=st.session_state.resolutions,
                help="选择一个或多个输出视频分辨率",
                key="resolutions",
                format_func=lambda x: {
                    "原始分辨率": "保持原始分辨率",
                    "3840x2160": "4K",
                    "2560x1440": "2K",
                    "1920x1080": "1080p",
                    "1280x720": "720p",
                    "854x480": "480p",
                    "640x360": "360p"
                }[x]
            )

            if not resolutions:
                st.warning("请至少选择一个输出分辨率")
                return

            # 根据分辨率设置码率选项
            bitrate_settings = {
                "3840x2160": {
                    "options": ["30000k", "20000k", "15000k", "12000k"],
                    "help": "4K视频推荐码率：12-30 Mbps"
                },
                "2560x1440": {
                    "options": ["15000k", "12000k", "9000k", "6000k"],
                    "help": "2K视频推荐码率：6-15 Mbps"
                },
                "1920x1080": {
                    "options": ["8000k", "6000k", "4500k", "3000k"],
                    "help": "1080p视频推荐码率：3-8 Mbps"
                },
                "1280x720": {
                    "options": ["4000k", "3000k", "2500k", "2000k"],
                    "help": "720p视频推荐码率：2-4 Mbps"
                },
                "854x480": {
                    "options": ["2500k", "2000k", "1500k", "1000k"],
                    "help": "480p视频推荐码率：1-2.5 Mbps"
                },
                "640x360": {
                    "options": ["1500k", "1000k", "800k", "500k"],
                    "help": "360p视频推荐码率：0.5-1.5 Mbps"
                },
                "原始分辨率": {
                    "options": ["8000k", "6000k", "4000k", "2000k"],
                    "help": "请根据实际分辨率选择合适的码率"
                }
            }

            # 为每个选择的分辨率创建一个码率选择器
            video_bitrates = {}
            for resolution in resolutions:
                video_bitrates[resolution] = st.selectbox(
                    f"视频码率 ({resolution})",
                    options=bitrate_settings[resolution]["options"],
                    index=1,
                    help=bitrate_settings[resolution]["help"],
                    key=f"video_bitrate_{resolution}"
                )
                st.info(f"当前视频设置：{resolution} @ {video_bitrates[resolution]}/s")

    # 音频设置
    with col2:
        st.subheader("🔊 音频设置")
        audio_encoder = st.selectbox(
            "音频编码器",
            options=["copy", "aac"],
            index=0,
            help="""
            选择音频处理方式：
            * 直接复制：不对音频进行重新编码，保持原始音质
            * AAC编码：使用AAC编码器重新编码，可调整码率
            
            说明：
            * 直接复制模式：速度最快，无音质损失
            * AAC编码模式：可以压缩音频，减小文件体积
            * AAC编码广泛支持：iOS、Android、Web浏览器都能很好支持
            """,
            key="audio_encoder",
            format_func=lambda x: {
                "copy": "直接复制 (保持原始音频流，不重新编码)",
                "aac": "AAC编码 (通用格式，可调整音质)"
            }[x]
        )

        # 添加音频编码器说明
        if audio_encoder == "copy":
            st.info("""
            ℹ️ 您选择了音频直接复制模式：
            * 不会重新编码音频，保持原始音质
            * 转换速度最快，不会占用额外资源
            * 适用于：原音频质量合适，只需要切片
            * 注意：如果原音频编码不兼容，可能需要选择AAC编码
            """)
        else:
            st.info("""
            ℹ️ 您选择了AAC音频编码：
            * 会对音频进行重新编码，可以调整码率
            * AAC是目前最通用的音频编码格式
            * 建议码率：
                - 192k：适合高质量音乐
                - 128k：适合标准音质
                - 96k：适合中等音质
                - 64k：适合语音质量
                
            * 更高码率 = 更好音质，但文件更大
            """)

        if audio_encoder != "copy":
            audio_bitrate = st.selectbox(
                "音频码率",
                options=["192k", "128k", "96k", "64k"],
                index=1,
                help="""
                选择音频码率：
                * 192k：高质量音乐
                * 128k：标准音质（推荐）
                * 96k：中等音质
                * 64k：语音质量
                
                说明：码率越高，音质越好，文件也越大
                """,
                key="audio_bitrate"
            )
            st.info(f"当前音频设置：{audio_encoder.upper()} @ {audio_bitrate}/s")

    # HLS设置
    st.header("📺 HLS设置")
    col1, col2 = st.columns(2)
    
    with col1:
        segment_time = st.text_input(
            "分片时长(秒)",
            value=st.session_state.segment_time,
            help="每个TS分片的时长，建议2-10秒之间。短视频推荐2秒，中等视频推荐5秒，长视频推荐10秒。",
            key="segment_time"
        )
        try:
            segment_time_int = int(segment_time)
            if segment_time_int < 1 or segment_time_int > 10:
                st.warning("⚠️ 分片时长建议在1-10秒之间")
        except ValueError:
            st.error("❌ 请输入有效的数字")
        
        playlist_type = 'vod'

    with col2:
        encryption_enabled = st.checkbox(
            "启用加密",
            value=st.session_state.encryption_enabled,
            help="""
            是否启用HLS内容加密：
            * 使用AES-128加密算法保护视频内容
            * 加密后的视频需要密钥才能播放
            * 适用于需要内容保护的场景
            * 支持密钥轮换机制增强安全性
            
            说明：
            * 加密会自动生成密钥文件(enc.key)
            * 密钥信息文件(enc.keyinfo)包含密钥获取地址
            * 播放器需要能访问密钥文件才能播放
            * 建议将密钥文件部署在HTTPS服务器上
            """,
            key="encryption_enabled"
        )

        if encryption_enabled:
            key_rotation_period = st.number_input(
                "密钥轮换周期(分片数)",
                min_value=0,
                max_value=100,
                value=0,
                help="""
                设置密钥自动轮换的周期：
                * 0：禁用密钥轮换，使用固定密钥
                * 1-100：每隔指定数量的分片更换一次密钥
                
                说明：
                * 密钥轮换可以提高安全性
                * 轮换周期越短，安全性越高
                * 但过于频繁的轮换会增加服务器负载
                * 建议根据实际安全需求选择合适的周期
                """,
                key="key_rotation"
            )
            
            st.info("""
            ℹ️ 加密相关说明：
            * 启用加密后会在输出目录生成以下文件：
                - enc.key：加密密钥文件
                - enc.keyinfo：密钥信息文件
                - *.ts：加密后的视频分片
                - *.m3u8：包含密钥信息的播放列表
            
            * 部署注意事项：
                - 确保播放器能访问密钥文件
                - 建议使用HTTPS传输密钥
                - 可以通过访问控制限制密钥获取
                - 密钥文件请妥善保管
            """)

    # 转换信息
    st.header("📊 转换信息")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("分片时长", segment_time)
        if video_encoder != "copy":
            for resolution in resolutions:
                st.metric(f"视频码率 ({resolution})", video_bitrates[resolution])
        st.metric("视频编码器", video_encoder)
    with col2:
        st.metric("播放列表类型", playlist_type)
        if audio_encoder != "copy" and 'audio_bitrate' in locals():
            st.metric("音频码率", audio_bitrate)
        st.metric("音频编码器", audio_encoder)
        if encryption_enabled:
            st.metric("加密模式", "AES-128")
    
    # 命令生成
    st.header("🔧 生成的FFmpeg命令")
    
    if video_encoder != "copy" and not resolutions:
        st.error("请至少选择一个输出分辨率")
        return

    # 为每个分辨率生成一个命令
    for resolution in (resolutions if video_encoder != "copy" else ["原始分辨率"]):
        # 构建FFmpeg命令
        command_parts = ["ffmpeg", "-y", "-i", f'\"{input_file}\"']
        
        # 视频编码参数
        command_parts.extend(["-c:v", video_encoder])
        if video_encoder != "copy":
            if resolution != "原始分辨率":
                command_parts.extend(["-s", resolution])
            command_parts.extend(["-b:v", video_bitrates[resolution]])
            
            # 根据不同编码器添加特定参数
            if video_encoder == "libx264":
                command_parts.extend(["-preset", "fast"])
            elif "nvenc" in video_encoder:
                command_parts.extend([
                    "-preset", "p4",
                    "-rc", "cbr"
                ])
            elif "qsv" in video_encoder:
                command_parts.extend(["-preset", "medium"])
            elif "videotoolbox" in video_encoder:
                command_parts.extend(["-allow_sw", "1"])
        
        # 音频编码参数
        command_parts.extend(["-c:a", audio_encoder])
        if audio_encoder != "copy" and 'audio_bitrate' in locals():
            command_parts.extend(["-b:a", audio_bitrate])
        
        # 创建分辨率特定的输出目录
        resolution_dir = f"{output_dir}/{resolution.replace('x', 'p')}"
        
        # HLS参数
        command_parts.extend([
            "-f", "hls",
            "-hls_time", segment_time,
            "-hls_playlist_type", playlist_type,
            "-hls_segment_filename", f'"{resolution_dir}/segment_%03d.ts"'
        ])
        
        # 加密参数
        if encryption_enabled:
            key_file = os.path.join(resolution_dir, "enc.key")
            key_info_file = os.path.join(resolution_dir, "enc.keyinfo")
            command_parts.extend([
                "-hls_key_info_file", f'"{key_info_file}"',
                "-hls_enc", "1"
            ])
            if key_rotation_period > 0:
                command_parts.extend(["-hls_key_rotation_period", str(key_rotation_period)])
        
        # 输出文件
        output_path = f"{resolution_dir}/{output_name}.m3u8"
        command_parts.append(f'"{output_path}"')
        
        # 显示命令
        st.subheader(f"📺 {resolution} 转换命令")
        ffmpeg_command = " ".join(command_parts)
        st.code(ffmpeg_command, language="bash")

    # 使用说明
    st.info("""
    **使用说明：**
    1. 复制上面生成的FFmpeg命令
    2. 在终端/命令行中运行该命令
    3. 确保输入文件存在且FFmpeg已正确安装
    4. 输出目录会自动创建（如果不存在）
    5. 每个分辨率的输出文件将保存在各自的子目录中
    """)
    
    # 添加开始转换功能
    st.markdown("---")
    st.header("🚀 开始转换")
    
    # 创建一个容器来显示转换进度
    progress_container = st.empty()
    output_container = st.empty()
    
    if st.button("开始转换", type="primary"):
        if not os.path.exists(input_file):
            st.error("❌ 输入文件不存在，请检查文件路径")
            return
            
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 显示进度条
            progress_bar = progress_container.progress(0)
            status_text = output_container.empty()
            
            # 存储所有要执行的命令
            commands = []
            
            # 为每个分辨率生成命令
            for resolution in (resolutions if video_encoder != "copy" else ["原始分辨率"]):
                # 构建FFmpeg命令
                command_parts = ["ffmpeg", "-y", "-i", f'{input_file}']
                
                # 视频编码参数
                command_parts.extend(["-c:v", video_encoder])
                if video_encoder != "copy":
                    if resolution != "原始分辨率":
                        command_parts.extend(["-s", resolution])
                    command_parts.extend(["-b:v", video_bitrates[resolution]])
                    
                    # 根据不同编码器添加特定参数
                    if video_encoder == "libx264":
                        command_parts.extend(["-preset", "fast"])
                    elif "nvenc" in video_encoder:
                        command_parts.extend([
                            "-preset", "p4",
                            "-rc", "cbr"
                        ])
                    elif "qsv" in video_encoder:
                        command_parts.extend(["-preset", "medium"])
                    elif "videotoolbox" in video_encoder:
                        command_parts.extend(["-allow_sw", "1"])
                
                # 音频编码参数
                command_parts.extend(["-c:a", audio_encoder])
                if audio_encoder != "copy" and 'audio_bitrate' in locals():
                    command_parts.extend(["-b:a", audio_bitrate])
                
                # 创建分辨率特定的输出目录
                resolution_dir = f"{output_dir}/"
                if resolution == "原始分辨率":
                    resolution_dir += "raw"
                else:
                    # 映射分辨率到标准名称
                    resolution_map = {
                        "3840x2160": "4k",
                        "2560x1440": "2k",
                        "1920x1080": "1080p",
                        "1280x720": "720p",
                        "854x480": "480p",
                        "640x360": "360p"
                    }
                    resolution_dir += resolution_map.get(resolution, "raw")
                
                os.makedirs(resolution_dir, exist_ok=True)
                
                # HLS参数
                command_parts.extend([
                    "-f", "hls",
                    "-hls_time", segment_time,
                    "-hls_playlist_type", playlist_type,
                    "-hls_segment_filename", f'{resolution_dir}/segment_%03d.ts'
                ])
                
                # 加密参数
                if encryption_enabled:
                    key_file = os.path.join(resolution_dir, "enc.key")
                    key_info_file = os.path.join(resolution_dir, "enc.keyinfo")
                    command_parts.extend([
                        "-hls_key_info_file", key_info_file,
                        "-hls_enc", "1"
                    ])
                    if key_rotation_period > 0:
                        command_parts.extend(["-hls_key_rotation_period", str(key_rotation_period)])
                
                # 输出文件
                output_path = f"{resolution_dir}/{output_name}.m3u8"
                command_parts.append(output_path)
                
                commands.append(command_parts)
            
            # 执行所有命令
            total_commands = len(commands)
            for i, command_parts in enumerate(commands):
                # 更新进度条
                progress = (i / total_commands) * 100
                progress_bar.progress(int(progress))
                
                # 显示当前正在处理的分辨率
                resolution = resolutions[i] if video_encoder != "copy" else "原始分辨率"
                resolution_display = resolution
                if resolution != "原始分辨率":
                    resolution_map = {
                        "3840x2160": "4K (3840x2160)",
                        "2560x1440": "2K (2560x1440)",
                        "1920x1080": "1080P (1920x1080)",
                        "1280x720": "720P (1280x720)",
                        "854x480": "480P (854x480)",
                        "640x360": "360P (640x360)"
                    }
                    resolution_display = resolution_map.get(resolution, resolution)
                else:
                    resolution_display = "原始分辨率"
                
                status_text.info(f"⏳ 正在处理 {resolution_display} ... ({i+1}/{total_commands})")
                
                # 执行命令
                process = subprocess.Popen(
                    command_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1
                )
                
                # 创建日志显示区域
                log_area = st.empty()
                log_text = f"正在处理 {resolution_display}:\n\n"
                
                # 实时显示FFmpeg输出
                while True:
                    output = process.stderr.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        # 只显示包含进度信息的行
                        if "frame=" in output or "speed=" in output or "time=" in output:
                            log_text = f"正在处理 {resolution_display}:\n{output.strip()}"
                            log_area.code(log_text)
                
                # 检查命令执行结果
                if process.returncode != 0:
                    # 获取完整的错误输出
                    _, stderr = process.communicate()
                    raise Exception(f"处理 {resolution_display} 时出错：\n{stderr}")
                else:
                    log_area.success(f"✅ {resolution_display} 转换完成")
            
            # 完成所有转换后，生成主播放列表
            master_playlist_path = os.path.join(output_dir, "master.m3u8")
            with open(master_playlist_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write("#EXT-X-VERSION:3\n")
                
                # 为每个分辨率添加一个流
                for resolution in (resolutions if video_encoder != "copy" else ["原始分辨率"]):
                    if resolution == "原始分辨率":
                        resolution_name = "raw"
                        bandwidth = "2000000"  # 默认码率
                    else:
                        # 获取分辨率对应的目录名和推荐码率
                        resolution_map = {
                            "3840x2160": ("4k", "15000000"),
                            "2560x1440": ("2k", "9000000"),
                            "1920x1080": ("1080p", "4500000"),
                            "1280x720": ("720p", "2500000"),
                            "854x480": ("480p", "1000000"),
                            "640x360": ("360p", "500000")
                        }
                        resolution_name, bandwidth = resolution_map.get(resolution, ("raw", "2000000"))
                    
                    # 添加流信息
                    if resolution != "原始分辨率":
                        width, height = resolution.split("x")
                        f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={resolution}\n')
                    else:
                        f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth}\n')
                    
                    f.write(f'{resolution_name}/{output_name}.m3u8\n')

            # 完成所有转换
            progress_bar.progress(100)
            
            # 显示最终结果
            st.success("🎉 转换完成！")
            
            # 在转换成功后生成视频封面
            with st.spinner("⏳ 正在生成视频封面..."):
                thumbnail_path = os.path.join(output_dir, "thumbnail.jpg")
                try:
                    # 使用ffmpeg提取第一帧
                    thumbnail_cmd = [
                        'ffmpeg',
                        '-i', input_file,
                        '-vf', 'select=eq(n\\,0),scale=280:158:force_original_aspect_ratio=decrease,pad=280:158:(ow-iw)/2:(oh-ih)/2',
                        '-vframes', '1',
                        '-q:v', '2',  # 高质量
                        thumbnail_path
                    ]
                    result = subprocess.run(thumbnail_cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        if os.path.exists(thumbnail_path):
                            st.success("✅ 已生成视频封面")
                            # 显示生成的封面
                            st.image(thumbnail_path, caption="视频封面预览", width=280)
                        else:
                            st.warning("⚠️ 封面文件未生成")
                    else:
                        st.warning(f"⚠️ 生成视频封面失败: {result.stderr}")
                except Exception as e:
                    st.warning(f"⚠️ 生成视频封面失败: {str(e)}")
                    st.error(f"错误详情: {traceback.format_exc()}")
            
            # 显示最终结果
            st.success("🎉 转换完成！")
            st.info(f"📂 输出目录：{output_dir}")
            st.info("🎯 已生成以下分辨率：")
            for resolution in (resolutions if video_encoder != "copy" else ["原始分辨率"]):
                if resolution == "原始分辨率":
                    st.text("   ✓ 原始分辨率")
                else:
                    resolution_map = {
                        "3840x2160": "4K (3840x2160)",
                        "2560x1440": "2K (2560x1440)",
                        "1920x1080": "1080P (1920x1080)",
                        "1280x720": "720P (1280x720)",
                        "854x480": "480P (854x480)",
                        "640x360": "360P (640x360)"
                    }
                    st.text(f"   ✓ {resolution_map.get(resolution, resolution)}")
            
        except Exception as e:
            st.error(f"❌ 转换过程中出错: {str(e)}")
            if 'process' in locals():
                output, error = process.communicate()
                st.error(f"错误详情: {error}")

if __name__ == "__main__":
    main() 
