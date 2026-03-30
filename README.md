# ScoreForge

将钢琴 MP3 或 MIDI 文件转换为 PDF 乐谱的命令行工具。支持单个文件或批量转换。

## 功能特性

- **多格式输入**：支持 `.mp3`、`.mid`、`.midi` 文件
- **批量处理**：可处理整个目录内的所有支持文件
- **智能转换**：
  - MP3 → MIDI → PDF（通过 AI 转谱）
  - MIDI → PDF（直接转换）
- **灵活选项**：GPU 加速、输出目录、中间文件保留等
- **用户友好**：清晰的进度提示和错误处理

## 系统要求

- Python 3.6+
- MuseScore 3（乐谱渲染引擎）
- piano_transcription_inference（MP3 转 MIDI）

## 安装

### 1. 安装 MuseScore

**Ubuntu/Debian：**
```bash
sudo apt install musescore3
```

**macOS：**
```bash
brew install musescore
```

**Windows：**
从 [MuseScore 官网](https://musescore.org/) 下载安装程序。

### 2. 安装 Python 依赖

```bash
pip install piano_transcription_inference
```

或者使用提供的 requirements 文件：
```bash
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
# 查看帮助
python3 scoreforge.py --help

# 单个 MP3 文件转换为 PDF
python3 scoreforge.py input.mp3

# 单个 MIDI 文件转换为 PDF
python3 scoreforge.py input.mid

# 批量处理目录
python3 scoreforge.py /path/to/music_folder/
```

### 高级选项

```bash
# 指定输出目录
python3 scoreforge.py input.mp3 -o ./output_pdfs/

# 使用 GPU 加速（需要 CUDA）
python3 scoreforge.py input.mp3 --use-gpu

# 只生成 MIDI 文件（不转 PDF）
python3 scoreforge.py input.mp3 --midi-only

# 假设输入是 MIDI，直接转 PDF（跳过格式检查）
python3 scoreforge.py input.mid --pdf-only

# 转换后删除中间生成的 MIDI 文件
python3 scoreforge.py input.mp3 --no-keep-midi

# 自定义 MuseScore 路径
python3 scoreforge.py input.mid --musescore-path /usr/bin/musescore3
```

## 示例

```bash
# 转换单个钢琴 MP3 文件
python3 scoreforge.py "月光奏鸣曲.mp3"

# 批量转换整个文件夹，输出到指定目录
python3 scoreforge.py ./钢琴曲/ -o ./乐谱/

# 仅生成 MIDI 文件（用于进一步编辑）
python3 scoreforge.py recording.mp3 --midi-only

# 使用现有 MIDI 文件生成 PDF
python3 scoreforge.py existing.mid --pdf-only
```

## 依赖说明

### Python 包依赖
- `piano_transcription_inference`：钢琴转谱 AI 模型
- `torch`（通过 piano_transcription_inference 自动安装）

### 系统依赖
- `musescore3`：乐谱渲染和 PDF 生成

## 工作流程

```
MP3 输入
    ↓
piano_transcription_inference（AI 转谱）
    ↓
MIDI 文件
    ↓
MuseScore（乐谱渲染）
    ↓
PDF 输出
```

## 故障排除

### 常见问题

**Q: 提示 "piano_transcription_inference 库未安装"**
A: 运行 `pip install piano_transcription_inference`

**Q: 提示 "无法运行 MuseScore"**
A: 确保 MuseScore 已安装且命令行可用，或使用 `--musescore-path` 指定路径

**Q: 转换速度慢**
A: MP3 转 MIDI 是 CPU 密集型操作，可使用 `--use-gpu` 加速（需要 CUDA）

**Q: 生成的 PDF 质量不佳**
A: 转谱质量取决于音频清晰度和复杂度，简单钢琴曲效果更好

## 许可证

本项目仅供学习和个人使用。请尊重版权，仅转换您拥有合法权利的音频文件。

## 相关项目

- [piano_transcription_inference](https://github.com/bytedance/piano_transcription_inference)
- [MuseScore](https://musescore.org/)