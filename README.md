# LocalTalk - 本地AI语音助手

**LocalTalk** 是一个开源的本地AI语音助手系统，让您能够在自己的计算机上运行一个完全私密的AI伴侣。基于先进的Ollama大语言模型和GPT-SoVITS语音克隆技术，LocalTalk提供真实自然的对话体验，所有数据处理都在您的设备本地完成，确保100%隐私安全。

## ✨ 核心特性

- **完全本地运行**：所有AI处理在您的计算机上进行，无需云端服务
- **个性化语音克隆**：使用GPT-SoVITS技术克隆特定人物的声音
- **多模型支持**：自由选择本地安装的Ollama语言模型
- **实时对话体验**：流畅的聊天界面与打字机效果回复
- **一键配置向导**：简单直观的初始设置流程
- **跨平台支持**：兼容Windows、macOS和Linux系统
- **隐私保护**：所有对话数据完全保留在本地设备

## 🚀 快速开始

### 系统要求
- Python 3.8 或更高版本
- 至少8GB RAM（推荐16GB+）
- 支持CUDA的NVIDIA GPU（推荐）或仅CPU模式

### 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/K-Summer/LocalTalk.git
cd LocalTalk
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate    # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 安装必备服务：
```bash
# 安装Ollama（根据您的系统）
# Windows: https://ollama.com/download
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.com/install.sh | sh

# 下载基础模型
ollama pull qwen2.5vl:latest
```

5. 启动应用：
```bash
python aic_tts.py
```

首次运行会自动打开配置向导，引导您完成设置。

## ⚙️ 配置指南

声邻使用简单的INI格式配置文件（`config.ini`），包含以下关键设置：

```ini
[API]
ollama_url = http://localhost:11434/api/generate
tts_url = http://localhost:9880
default_model = qwen2.5vl:latest

[TTS]
reference_wav = /path/to/your/voice_sample.wav
prompt_text = 你好，我是莫妮卡，很高兴为您服务...
prompt_language = zh
text_language = zh
```

### 推荐语音样本
- 时长：10-30秒清晰语音
- 格式：WAV或MP3
- 内容：与参考文本完全匹配
- 质量：无背景噪音，单一说话人

## 🗣️ 使用指南

1. **聊天界面**：
   - 在文本框中输入您的问题或对话
   - 按Enter或点击"发送"按钮
   - 莫妮卡会以文字和语音形式回复

2. **模型选择**：
   - 从下拉菜单选择不同语言模型
   - 点击"刷新模型"获取最新安装的模型

3. **语音设置**：
   - 在配置页面调整语音克隆参数
   - 可随时更换参考音频和文本


## 🤝 贡献指南


常见贡献方式：
- 报告Bug或提出新功能建议
- 改进文档和翻译
- 优化代码性能
- 添加对新模型的支持

## 📜 开源许可

LocalTalk采用 [MIT 许可证](LICENSE) 发布，您可以自由地：
- 使用、复制和修改软件
- 用于个人或商业目的
- 分发软件副本

唯一的限制是需保留原始版权声明和许可声明。

## ❓ 常见问题

**Q: 为什么我的语音生成速度慢？**  
A: 首次生成需要加载模型到内存，后续请求会更快。确保使用GPU加速可显著提升速度。

**Q: 如何提高语音质量？**  
A: 1) 使用更高质量的参考音频 2) 增加参考音频时长 3) 确保参考文本与音频内容完全匹配

**Q: 支持哪些语言？**  
A: 当前主要支持中文、英文和日文。GPT-SoVITS支持更多语言，可在配置中修改语言代码。

**Q: 需要互联网连接吗？**  
A: 仅首次下载模型时需要联网，之后可完全离线运行。

---
  
*隐私优先 · 本地智能 · 个性体验*