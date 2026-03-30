#!/usr/bin/env python3
"""
Piano MP3/MIDI to PDF Converter
合并了 piano_transcription_inference (MP3->MIDI) 和 MuseScore (MIDI->PDF) 的功能。
支持单个文件或批量转换。
"""

import argparse
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Tuple

try:
    from piano_transcription_inference import PianoTranscription, load_audio, sample_rate
    PIANO_TRANSCRIPTION_AVAILABLE = True
except ImportError:
    PIANO_TRANSCRIPTION_AVAILABLE = False
    PianoTranscription = None
    load_audio = None
    sample_rate = None

def check_musescore(musescore_path: str) -> bool:
    try:
        subprocess.run([musescore_path, "--version"], capture_output=True, text=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def convert_mp3_to_midi(mp3_path: str, midi_path: str, use_gpu: bool = False) -> bool:
    if not PIANO_TRANSCRIPTION_AVAILABLE:
        print("错误: piano_transcription_inference 库未安装。请使用 'pip install piano_transcription_inference' 安装。")
        return False

    if not os.path.exists(mp3_path):
        print(f"错误: 输入文件不存在: {mp3_path}")
        return False

    try:
        print(f"  正在加载音频: {mp3_path}")
        audio, _ = load_audio(mp3_path, sr=sample_rate, mono=True)

        device = 'cuda' if use_gpu else 'cpu'
        print(f"  使用设备: {device}")

        transcriptor = PianoTranscription(device=device)

        print("  正在转谱（可能需要几分钟）...")
        transcriptor.transcribe(audio, midi_path)

        print(f"  MIDI 文件已保存至: {midi_path}")
        return True
    except Exception as e:
        print(f"  MP3 转 MIDI 失败: {e}")
        return False

def convert_midi_to_pdf(midi_path: str, pdf_path: str, musescore_path: str = "musescore3") -> bool:
    if not os.path.exists(midi_path):
        print(f"错误: MIDI 文件不存在: {midi_path}")
        return False

    cmd = [musescore_path, midi_path, "-o", pdf_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"  PDF 生成成功: {pdf_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  MuseScore 执行失败: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"  错误: 找不到 MuseScore 可执行文件: {musescore_path}")
        return False

def get_output_path(input_file: str, output_dir: str, new_ext: str) -> str:
    base = os.path.splitext(os.path.basename(input_file))[0]
    return os.path.join(output_dir, base + new_ext)

def process_single_file(input_file: str,
                        output_dir: str,
                        musescore_path: str,
                        use_gpu: bool,
                        keep_midi: bool,
                        midi_only: bool,
                        pdf_only: bool) -> Tuple[bool, Optional[str]]:
    input_file = os.path.abspath(input_file)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    ext = os.path.splitext(input_file)[1].lower()

    if pdf_only:
        if ext not in ['.mid', '.midi']:
            print(f"错误: --pdf-only 模式下，输入文件必须是 MIDI 文件，但得到: {input_file}")
            return False, None
        pdf_path = get_output_path(input_file, output_dir, '.pdf')
        success = convert_midi_to_pdf(input_file, pdf_path, musescore_path)
        return success, pdf_path if success else None

    if ext in ['.mid', '.midi']:
        pdf_path = get_output_path(input_file, output_dir, '.pdf')
        success = convert_midi_to_pdf(input_file, pdf_path, musescore_path)
        return success, pdf_path if success else None

    if ext == '.mp3':
        midi_path = get_output_path(input_file, output_dir, '.mid')
        print(f"步骤 1/2: MP3 转 MIDI")
        success_midi = convert_mp3_to_midi(input_file, midi_path, use_gpu)
        if not success_midi:
            return False, None

        if midi_only:
            print(f"仅生成 MIDI 文件，跳过 PDF 转换。")
            return True, None

        print(f"步骤 2/2: MIDI 转 PDF")
        pdf_path = get_output_path(input_file, output_dir, '.pdf')
        success_pdf = convert_midi_to_pdf(midi_path, pdf_path, musescore_path)

        if not keep_midi and success_pdf:
            try:
                os.remove(midi_path)
                print(f"  已删除中间 MIDI 文件: {midi_path}")
            except OSError:
                pass

        return success_pdf, pdf_path if success_pdf else None

    print(f"跳过不支持的文件格式: {input_file}")
    return False, None

def batch_process(input_path: str,
                  output_dir: str,
                  musescore_path: str,
                  use_gpu: bool,
                  keep_midi: bool,
                  midi_only: bool,
                  pdf_only: bool) -> None:
    input_path = os.path.abspath(input_path)

    if os.path.isdir(input_path):
        supported_exts = ['.mp3', '.mid', '.midi']
        files_to_process: List[str] = []
        for root, _, files in os.walk(input_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in supported_exts:
                    files_to_process.append(os.path.join(root, file))

        if not files_to_process:
            print(f"在目录 {input_path} 中未找到支持的文件（{', '.join(supported_exts)}）。")
            return

        print(f"找到 {len(files_to_process)} 个文件待处理。")
        success_count = 0
        for i, file in enumerate(files_to_process, 1):
            print(f"\n[{i}/{len(files_to_process)}] 处理: {file}")
            success, _ = process_single_file(
                file, output_dir, musescore_path, use_gpu, keep_midi, midi_only, pdf_only
            )
            if success:
                success_count += 1

        print(f"\n批量处理完成: {success_count}/{len(files_to_process)} 个文件成功。")

    elif os.path.isfile(input_path):
        print(f"处理单个文件: {input_path}")
        success, pdf_path = process_single_file(
            input_path, output_dir, musescore_path, use_gpu, keep_midi, midi_only, pdf_only
        )
        if success:
            if pdf_path:
                print(f"转换成功！PDF 文件: {pdf_path}")
            else:
                print("转换成功！")
        else:
            print("转换失败。")
            sys.exit(1)
    else:
        print(f"错误: 输入路径不存在: {input_path}")
        sys.exit(1)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ScoreForge: 将钢琴 MP3 或 MIDI 文件转换为 PDF 乐谱（通过 MIDI 中间格式）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s input.mp3                     # 单个 MP3 文件 -> MIDI + PDF
  %(prog)s input.mid                     # 单个 MIDI 文件 -> PDF
  %(prog)s my_music_folder/              # 批量处理文件夹内所有 MP3/MIDI
  %(prog)s input.mp3 -o output_dir/      # 指定输出目录
  %(prog)s input.mp3 --midi-only         # 只生成 MIDI，不生成 PDF
  %(prog)s input.mid --pdf-only          # 假设输入是 MIDI，直接转 PDF（跳过格式检查）
        """
    )

    parser.add_argument("input", help="输入文件或目录路径（支持 .mp3, .mid, .midi）")
    parser.add_argument("-o", "--output", default=".",
                        help="输出目录（默认为当前目录）")
    parser.add_argument("--musescore-path", default="musescore3",
                        help="MuseScore 可执行文件路径（默认为 'musescore3'）")
    parser.add_argument("--use-gpu", action="store_true",
                        help="使用 GPU 加速 MP3 转 MIDI（需要 CUDA）")
    parser.add_argument("--keep-midi", action="store_true", default=True,
                        help="保留中间生成的 MIDI 文件（默认保留）")
    parser.add_argument("--no-keep-midi", action="store_false", dest="keep_midi",
                        help="不保留中间生成的 MIDI 文件")
    parser.add_argument("--midi-only", action="store_true",
                        help="只生成 MIDI 文件，不转换为 PDF")
    parser.add_argument("--pdf-only", action="store_true",
                        help="假设输入是 MIDI 文件，直接转换为 PDF（跳过 MP3 转 MIDI）")

    args = parser.parse_args()

    if not args.pdf_only and not args.midi_only:
        if not check_musescore(args.musescore_path):
            print(f"警告: 无法运行 MuseScore ({args.musescore_path})。PDF 生成将失败。")
            print("请确保 MuseScore 已安装并可通过命令行访问，或使用 --musecore-path 指定路径。")
            print("继续执行可能会在 PDF 转换步骤失败。")

    if not args.pdf_only:
        if not PIANO_TRANSCRIPTION_AVAILABLE:
            print("错误: piano_transcription_inference 库未安装。")
            print("请使用以下命令安装: pip install piano_transcription_inference")
            print("或者使用 --pdf-only 模式直接转换 MIDI 文件。")
            sys.exit(1)

    batch_process(
        input_path=args.input,
        output_dir=args.output,
        musescore_path=args.musescore_path,
        use_gpu=args.use_gpu,
        keep_midi=args.keep_midi,
        midi_only=args.midi_only,
        pdf_only=args.pdf_only
    )

if __name__ == "__main__":
    main()