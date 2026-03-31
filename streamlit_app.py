#!/usr/bin/env python3
"""
ScoreForge Streamlit App
基于浏览器的钢琴音频/MIDI转PDF乐谱工具
"""

import streamlit as st
import os
import sys
import tempfile
import shutil
import time
from pathlib import Path
from typing import List, Optional, Tuple

# 导入 scoreforge 核心函数
from scoreforge import (
    SUPPORTED_AUDIO_EXTS,
    convert_mp3_to_midi,
    convert_midi_to_pdf,
    check_musescore,
    PIANO_TRANSCRIPTION_AVAILABLE,
)

# 页面配置
st.set_page_config(
    page_title="ScoreForge - 音频转乐谱",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6B7280;
        margin-bottom: 2rem;
    }
    .success-box {
        background-color: #D1FAE5;
        border: 1px solid #10B981;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #FEE2E2;
        border: 1px solid #EF4444;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #DBEAFE;
        border: 1px solid #3B82F6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = []
    if 'processing' not in st.session_state:
        st.session_state.processing = False


def get_temp_dir() -> Path:
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = tempfile.mkdtemp(prefix="scoreforge_")
    return Path(st.session_state.temp_dir)


def cleanup_temp_dir():
    if 'temp_dir' in st.session_state:
        temp_dir = Path(st.session_state.temp_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        del st.session_state.temp_dir


def process_uploaded_file(
    uploaded_file,
    output_dir: Path,
    musescore_path: str,
    use_gpu: bool,
    keep_midi: bool,
    midi_only: bool,
) -> dict:
    """处理单个上传的文件"""
    result = {
        'filename': uploaded_file.name,
        'success': False,
        'midi_path': None,
        'pdf_path': None,
        'error': None,
        'time': 0,
    }

    start_time = time.time()
    temp_dir = get_temp_dir()

    try:
        # 保存上传的文件到临时目录
        input_path = temp_dir / uploaded_file.name
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        ext = input_path.suffix.lower()

        # 处理 MIDI 文件
        if ext in ['.mid', '.midi']:
            pdf_path = output_dir / f"{input_path.stem}.pdf"
            success = convert_midi_to_pdf(str(input_path), str(pdf_path), musescore_path)
            if success:
                result['success'] = True
                result['pdf_path'] = str(pdf_path)
            else:
                result['error'] = "MIDI转PDF失败"
            result['time'] = time.time() - start_time
            return result

        # 处理音频文件
        if ext in SUPPORTED_AUDIO_EXTS:
            midi_path = output_dir / f"{input_path.stem}.mid"

            # 步骤1: 音频转MIDI
            with st.status(f"🎵 正在转谱: {uploaded_file.name}") as status:
                st.write("步骤 1/2: 音频转MIDI...")
                success_midi = convert_mp3_to_midi(str(input_path), str(midi_path), use_gpu)

                if not success_midi:
                    result['error'] = "音频转MIDI失败"
                    result['time'] = time.time() - start_time
                    return result

                result['midi_path'] = str(midi_path)

                if midi_only:
                    result['success'] = True
                    status.update(label=f"✅ {uploaded_file.name} (仅MIDI)", state="complete")
                    result['time'] = time.time() - start_time
                    return result

                # 步骤2: MIDI转PDF
                st.write("步骤 2/2: MIDI转PDF...")
                pdf_path = output_dir / f"{input_path.stem}.pdf"
                success_pdf = convert_midi_to_pdf(str(midi_path), str(pdf_path), musescore_path)

                if success_pdf:
                    result['success'] = True
                    result['pdf_path'] = str(pdf_path)
                    status.update(label=f"✅ {uploaded_file.name}", state="complete")
                else:
                    result['error'] = "MIDI转PDF失败"
                    status.update(label=f"❌ {uploaded_file.name}", state="error")

                if not keep_midi and success_pdf:
                    try:
                        os.remove(midi_path)
                        result['midi_path'] = None
                    except OSError:
                        pass

                result['time'] = time.time() - start_time
                return result

        result['error'] = f"不支持的文件格式: {ext}"
        result['time'] = time.time() - start_time
        return result

    except Exception as e:
        result['error'] = f"处理异常: {str(e)}"
        result['time'] = time.time() - start_time
        return result


def main():
    init_session_state()

    # 侧边栏
    with st.sidebar:
        st.image("images/readme-banner.png", use_container_width=True)
        st.title("ScoreForge")
        st.markdown("---")

        st.subheader("⚙️ 设置")

        # MuseScore 路径
        musescore_path = st.text_input(
            "MuseScore 路径",
            value="musescore3",
            help="MuseScore 可执行文件的路径，默认为 musescore3"
        )

        # 检查 MuseScore
        if check_musescore(musescore_path):
            st.success("✅ MuseScore 可用")
        else:
            st.error("❌ MuseScore 不可用")
            st.caption("PDF生成功能将不可用")

        # 检查 piano_transcription_inference
        if PIANO_TRANSCRIPTION_AVAILABLE:
            st.success("✅ 转谱引擎可用")
        else:
            st.error("❌ 转谱引擎不可用")
            st.caption("仅支持MIDI转PDF")

        st.markdown("---")

        # 高级选项
        with st.expander("🔧 高级选项"):
            use_gpu = st.checkbox(
                "使用GPU加速",
                value=False,
                help="需要CUDA支持，否则使用CPU"
            )
            keep_midi = st.checkbox(
                "保留MIDI文件",
                value=True,
                help="在输出中保留中间生成的MIDI文件"
            )
            midi_only = st.checkbox(
                "仅生成MIDI",
                value=False,
                help="只转谱为MIDI，不生成PDF"
            )

        st.markdown("---")
        st.caption("📌 支持格式: MP3, WAV, FLAC, OGG, AAC, M4A, WMA, MIDI")

    # 主内容区
    st.markdown('<p class="main-header">🎵 ScoreForge</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">将钢琴音频转换为PDF乐谱 | Audio to Sheet Music</p>', unsafe_allow_html=True)

    # 文件上传区
    st.subheader("📤 上传文件")
    uploaded_files = st.file_uploader(
        "选择音频或MIDI文件",
        type=[ext.lstrip('.') for ext in SUPPORTED_AUDIO_EXTS + ['.mid', '.midi']],
        accept_multiple_files=True,
        help="支持批量上传多个文件"
    )

    if uploaded_files:
        st.info(f"📁 已选择 {len(uploaded_files)} 个文件")

        # 显示文件列表
        with st.expander("📋 查看文件列表"):
            for f in uploaded_files:
                st.write(f"- {f.name} ({f.size / 1024:.1f} KB)")

    # 开始处理按钮
    col1, col2 = st.columns([1, 4])
    with col1:
        process_btn = st.button(
            "🚀 开始转换",
            type="primary",
            disabled=not uploaded_files or st.session_state.processing,
            use_container_width=True
        )

    # 处理文件
    if process_btn and uploaded_files:
        st.session_state.processing = True
        st.session_state.processed_files = []

        # 创建输出目录
        output_dir = Path(tempfile.mkdtemp(prefix="scoreforge_output_"))

        st.markdown("---")
        st.subheader("⏳ 处理进度")

        # 进度条
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"处理中: {uploaded_file.name} ({i+1}/{len(uploaded_files)})")

            result = process_uploaded_file(
                uploaded_file,
                output_dir,
                musescore_path,
                use_gpu,
                keep_midi,
                midi_only,
            )
            results.append(result)

            # 更新进度条
            progress_bar.progress((i + 1) / len(uploaded_files))

        status_text.text("✅ 处理完成!")
        st.session_state.processed_files = results
        st.session_state.output_dir = str(output_dir)
        st.session_state.processing = False

    # 显示结果（基于 session_state，确保 rerun 后仍然显示）
    if st.session_state.processed_files:
        results = st.session_state.processed_files

        st.markdown("---")
        st.subheader("📊 处理结果")

        # 统计
        success_count = sum(1 for r in results if r['success'])
        failed_count = sum(1 for r in results if not r['success'])
        total_time = sum(r['time'] for r in results)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ 成功", success_count)
        with col2:
            st.metric("❌ 失败", failed_count)
        with col3:
            st.metric("⏱️ 总耗时", f"{total_time:.1f}秒")

        # 详细结果
        for result in results:
            with st.container():
                if result['success']:
                    st.success(f"✅ {result['filename']}")

                    # PDF 下载按钮
                    if result['pdf_path'] and os.path.exists(result['pdf_path']):
                        with open(result['pdf_path'], "rb") as f:
                            st.download_button(
                                label=f"📥 下载 PDF: {Path(result['pdf_path']).name}",
                                data=f,
                                file_name=Path(result['pdf_path']).name,
                                mime="application/pdf",
                                key=f"pdf_{result['filename']}",
                            )

                    # MIDI 下载按钮
                    if result['midi_path'] and os.path.exists(result['midi_path']):
                        with open(result['midi_path'], "rb") as f:
                            st.download_button(
                                label=f"📥 下载 MIDI: {Path(result['midi_path']).name}",
                                data=f,
                                file_name=Path(result['midi_path']).name,
                                mime="audio/midi",
                                key=f"midi_{result['filename']}",
                            )
                else:
                    st.error(f"❌ {result['filename']}: {result['error']}")

    # 使用说明
    if not uploaded_files:
        st.markdown("---")
        st.subheader("📖 使用说明")

        with st.expander("如何使用？", expanded=True):
            st.markdown("""
            1. **上传文件**: 点击上方的文件上传区域，选择一个或多个音频/MIDI文件
            2. **配置选项**: 在左侧侧边栏中调整MuseScore路径和其他设置
            3. **开始转换**: 点击"开始转换"按钮
            4. **下载结果**: 转换完成后，点击下载按钮获取PDF和MIDI文件

            **支持的格式**:
            - 音频: MP3, WAV, FLAC, OGG, AAC, M4A, WMA
            - MIDI: .mid, .midi

            **注意事项**:
            - 音频转谱需要几分钟时间，请耐心等待
            - 需要安装 MuseScore 才能生成PDF
            - 本机没有GPU，使用CPU处理
            """)

        with st.expander("环境要求"):
            st.markdown("""
            - Python 3.7+
            - piano_transcription_inference
            - MuseScore 3.x
            - streamlit

            安装依赖:
            ```bash
            pip install -r requirements.txt
            ```

            运行应用:
            ```bash
            streamlit run streamlit_app.py
            ```
            """)


if __name__ == "__main__":
    main()
