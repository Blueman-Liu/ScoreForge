#!/usr/bin/env python3
"""
ScoreForge: 钢琴音频/MIDI 转 PDF 乐谱
合并了 piano_transcription_inference (音频->MIDI) 和 MuseScore (MIDI->PDF) 的功能。
支持多种音频格式（MP3, WAV, FLAC, OGG 等）和 MIDI 文件。
支持单个文件或批量转换。
"""

import argparse
import os
import sys
import subprocess
import tempfile
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import concurrent.futures

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # 回退：简单的进度显示
    def tqdm(iterable, *args, **kwargs):
        return iterable

try:
    from piano_transcription_inference import PianoTranscription, load_audio, sample_rate
    PIANO_TRANSCRIPTION_AVAILABLE = True
except ImportError:
    PIANO_TRANSCRIPTION_AVAILABLE = False
    PianoTranscription = None
    load_audio = None
    sample_rate = None

SUPPORTED_AUDIO_EXTS = ['.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a', '.wma']


class ProcessingStatus(Enum):
    """处理状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProcessingOptions:
    """处理选项数据类"""
    output_dir: str
    musescore_path: str = "musescore3"
    use_gpu: bool = False
    keep_midi: bool = True
    midi_only: bool = False
    pdf_only: bool = False


@dataclass
class FileResult:
    """单个文件处理结果"""
    input_file: str
    status: ProcessingStatus
    midi_path: Optional[str] = None
    pdf_path: Optional[str] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    
    @property
    def success(self) -> bool:
        return self.status == ProcessingStatus.SUCCESS


@dataclass
class BatchResult:
    """批量处理结果"""
    total_files: int
    successful: int
    failed: int
    skipped: int
    results: List[FileResult]
    total_time: float
    
    @property
    def success_rate(self) -> float:
        return self.successful / self.total_files if self.total_files > 0 else 0.0


def calculate_optimal_workers(use_gpu: bool, file_count: int) -> int:
    """计算最优工作进程数"""
    if use_gpu:
        # GPU模式：限制为1，避免显存竞争
        return 1
    else:
        # CPU模式：使用CPU核心数，但不超过文件数，也不超过8（避免资源耗尽）
        cpu_count = os.cpu_count() or 4
        return min(cpu_count, file_count, 8)

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

    if ext in SUPPORTED_AUDIO_EXTS:
        midi_path = get_output_path(input_file, output_dir, '.mid')
        print(f"步骤 1/2: 音频转 MIDI")
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


def process_file_parallel(input_file: str, options: ProcessingOptions) -> FileResult:
    """并行处理单个文件（在子进程中运行）"""
    start_time = time.time()
    input_file = os.path.abspath(input_file)
    output_dir = os.path.abspath(options.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成唯一的临时文件名
    temp_id = str(uuid.uuid4())[:8]
    
    try:
        ext = os.path.splitext(input_file)[1].lower()
        
        # 检查文件是否存在
        if not os.path.exists(input_file):
            return FileResult(
                input_file=input_file,
                status=ProcessingStatus.FAILED,
                error=f"文件不存在: {input_file}",
                processing_time=time.time() - start_time
            )
        
        # PDF-only模式
        if options.pdf_only:
            if ext not in ['.mid', '.midi']:
                return FileResult(
                    input_file=input_file,
                    status=ProcessingStatus.FAILED,
                    error=f"--pdf-only 模式下，输入文件必须是 MIDI 文件，但得到: {input_file}",
                    processing_time=time.time() - start_time
                )
            pdf_path = get_output_path(input_file, output_dir, '.pdf')
            success = convert_midi_to_pdf(input_file, pdf_path, options.musescore_path)
            return FileResult(
                input_file=input_file,
                status=ProcessingStatus.SUCCESS if success else ProcessingStatus.FAILED,
                pdf_path=pdf_path if success else None,
                processing_time=time.time() - start_time
            )
        
        # MIDI文件处理
        if ext in ['.mid', '.midi']:
            pdf_path = get_output_path(input_file, output_dir, '.pdf')
            success = convert_midi_to_pdf(input_file, pdf_path, options.musescore_path)
            return FileResult(
                input_file=input_file,
                status=ProcessingStatus.SUCCESS if success else ProcessingStatus.FAILED,
                pdf_path=pdf_path if success else None,
                processing_time=time.time() - start_time
            )
        
        # 音频文件处理
        if ext in SUPPORTED_AUDIO_EXTS:
            midi_path = get_output_path(input_file, output_dir, f'.{temp_id}.mid')
            success_midi = convert_mp3_to_midi(input_file, midi_path, options.use_gpu)
            if not success_midi:
                return FileResult(
                    input_file=input_file,
                    status=ProcessingStatus.FAILED,
                    error="音频转MIDI失败",
                    processing_time=time.time() - start_time
                )
            
            # 如果只生成MIDI
            if options.midi_only:
                final_midi_path = get_output_path(input_file, output_dir, '.mid')
                shutil.move(midi_path, final_midi_path)
                return FileResult(
                    input_file=input_file,
                    status=ProcessingStatus.SUCCESS,
                    midi_path=final_midi_path,
                    processing_time=time.time() - start_time
                )
            
            # MIDI转PDF
            pdf_path = get_output_path(input_file, output_dir, '.pdf')
            success_pdf = convert_midi_to_pdf(midi_path, pdf_path, options.musescore_path)
            
            # 清理临时MIDI文件
            if not options.keep_midi and success_pdf:
                try:
                    os.remove(midi_path)
                except OSError:
                    pass
            
            return FileResult(
                input_file=input_file,
                status=ProcessingStatus.SUCCESS if success_pdf else ProcessingStatus.FAILED,
                midi_path=midi_path if options.keep_midi else None,
                pdf_path=pdf_path if success_pdf else None,
                processing_time=time.time() - start_time
            )
        
        # 不支持的文件格式
        return FileResult(
            input_file=input_file,
            status=ProcessingStatus.SKIPPED,
            error=f"跳过不支持的文件格式: {input_file}",
            processing_time=time.time() - start_time
        )
        
    except Exception as e:
        return FileResult(
            input_file=input_file,
            status=ProcessingStatus.FAILED,
            error=f"处理异常: {str(e)}",
            processing_time=time.time() - start_time
        )


def batch_process_parallel(
    files: List[str],
    options: ProcessingOptions,
    max_workers: Optional[int] = None,
    verbose: bool = False
) -> BatchResult:
    """批量并行处理文件"""
    start_time = time.time()
    
    if not files:
        return BatchResult(
            total_files=0,
            successful=0,
            failed=0,
            skipped=0,
            results=[],
            total_time=0.0
        )
    
    # 计算工作进程数
    if max_workers is None:
        max_workers = calculate_optimal_workers(options.use_gpu, len(files))
    
    # 确保至少1个工作进程
    max_workers = max(1, min(max_workers, len(files)))
    
    if verbose:
        print(f"开始并行处理 {len(files)} 个文件，使用 {max_workers} 个工作进程")
    
    results: List[FileResult] = []
    
    # 使用ProcessPoolExecutor进行并行处理
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_file = {
            executor.submit(process_file_parallel, file, options): file
            for file in files
        }
        
        # 收集结果（带进度条）
        if TQDM_AVAILABLE:
            # 使用tqdm进度条
            futures = tqdm(
                concurrent.futures.as_completed(future_to_file),
                total=len(files),
                desc="处理进度",
                unit="文件"
            )
        else:
            # 简单进度显示
            futures = concurrent.futures.as_completed(future_to_file)
            print(f"处理进度: 0/{len(files)}", end="", flush=True)
        
        completed = 0
        for future in futures:
            file = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
                
                # 更新进度
                completed += 1
                if not TQDM_AVAILABLE:
                    print(f"\r处理进度: {completed}/{len(files)}", end="", flush=True)
                
                # 详细输出
                if verbose and TQDM_AVAILABLE:
                    if result.success:
                        tqdm.write(f"✓ {os.path.basename(file)}")
                    elif result.status == ProcessingStatus.SKIPPED:
                        tqdm.write(f"⊘ {os.path.basename(file)}: {result.error}")
                    else:
                        tqdm.write(f"✗ {os.path.basename(file)}: {result.error}")
                        
            except Exception as e:
                # 捕获任务执行异常
                results.append(FileResult(
                    input_file=file,
                    status=ProcessingStatus.FAILED,
                    error=f"任务执行异常: {str(e)}",
                    processing_time=0.0
                ))
                completed += 1
                if not TQDM_AVAILABLE:
                    print(f"\r处理进度: {completed}/{len(files)}", end="", flush=True)
    
    if not TQDM_AVAILABLE:
        print()  # 换行
    
    # 统计结果
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
    skipped = sum(1 for r in results if r.status == ProcessingStatus.SKIPPED)
    
    total_time = time.time() - start_time
    
    return BatchResult(
        total_files=len(files),
        successful=successful,
        failed=failed,
        skipped=skipped,
        results=results,
        total_time=total_time
    )


def batch_process(input_path: str,
                  output_dir: str,
                  musescore_path: str,
                  use_gpu: bool,
                  keep_midi: bool,
                  midi_only: bool,
                  pdf_only: bool,
                  parallel: bool = True,
                  workers: Optional[int] = None) -> None:
    input_path = os.path.abspath(input_path)

    if os.path.isdir(input_path):
        supported_exts = SUPPORTED_AUDIO_EXTS + ['.mid', '.midi']
        files_to_process: List[str] = []
        for root, _, files in os.walk(input_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in supported_exts:
                    files_to_process.append(os.path.join(root, file))

        if not files_to_process:
            print(f"在目录 {input_path} 中未找到支持的文件（{', '.join(supported_exts)}）。")
            return

        print(f"找到 {len(files_to_process)} 个文件待处理。")
        
        if parallel:
            # 并行处理
            options = ProcessingOptions(
                output_dir=output_dir,
                musescore_path=musescore_path,
                use_gpu=use_gpu,
                keep_midi=keep_midi,
                midi_only=midi_only,
                pdf_only=pdf_only
            )
            result = batch_process_parallel(
                files=files_to_process,
                options=options,
                max_workers=workers,
                verbose=True
            )
            print(f"\n批量处理完成: {result.successful}/{result.total_files} 个文件成功。")
            if result.failed > 0:
                print(f"失败: {result.failed} 个文件")
            if result.skipped > 0:
                print(f"跳过: {result.skipped} 个文件")
        else:
            # 串行处理（原有逻辑）
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
  %(prog)s input.wav                     # 单个音频文件 -> MIDI + PDF（支持 .mp3, .wav, .flac, .ogg 等）
  %(prog)s input.mid                     # 单个 MIDI 文件 -> PDF
  %(prog)s my_music_folder/              # 批量处理文件夹内所有音频/MIDI
  %(prog)s input.flac -o output_dir/     # 指定输出目录
  %(prog)s input.ogg --midi-only         # 只生成 MIDI，不生成 PDF
  %(prog)s input.mid --pdf-only          # 假设输入是 MIDI，直接转 PDF（跳过格式检查）
        """
    )

    parser.add_argument("input", help=f"输入文件或目录路径（支持 {', '.join(SUPPORTED_AUDIO_EXTS + ['.mid', '.midi'])}）")
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
    parser.add_argument("--parallel", action="store_true", default=True,
                        help="启用并行处理（默认启用）")
    parser.add_argument("--no-parallel", action="store_false", dest="parallel",
                        help="禁用并行处理，使用串行处理")
    parser.add_argument("--workers", type=int, default=None,
                        help="并行处理的工作进程数（默认自动计算）")

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
        pdf_only=args.pdf_only,
        parallel=args.parallel,
        workers=args.workers
    )

if __name__ == "__main__":
    main()