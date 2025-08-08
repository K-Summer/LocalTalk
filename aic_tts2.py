import requests
import re
import gradio as gr
import time
import os
import sys
import configparser
from datetime import datetime
import threading

# ======================
# 全局状态管理类
# ======================
class AppState:
    def __init__(self):
        self.config_file = "config.ini"
        self.first_run = not os.path.exists(self.config_file)
        self.config = None
        self.audio_generated = threading.Event()
        self.audio_file_path = None
        self.tts_error = None
        self.tts_elapsed = None
        self.audio_ready = False
        
    def load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            return None

        config = configparser.ConfigParser()
        config.read(self.config_file)

        self.config = {
            "API": {
                "ollama_url": config.get("API", "ollama_url", fallback=""),
                "tts_url": config.get("API", "tts_url", fallback=""),
                "default_model": config.get("API", "default_model", fallback="qwen2.5vl:latest"),
            },
            "TTS": {
                "reference_wav": config.get("TTS", "reference_wav", fallback=""),
                "prompt_text": config.get("TTS", "prompt_text", fallback=""),
                "prompt_language": config.get("TTS", "prompt_language", fallback="zh"),
                "text_language": config.get("TTS", "text_language", fallback="zh"),
                "enable_tts": config.get("TTS", "enable_tts", fallback="True"),
            },
        }
        return self.config

    def save_config(self, config_data):
        """保存配置文件"""
        config = configparser.ConfigParser()
        config["API"] = {
            "ollama_url": config_data["API"]["ollama_url"],
            "tts_url": config_data["API"]["tts_url"],
            "default_model": config_data["API"]["default_model"],
        }
        config["TTS"] = {
            "reference_wav": config_data["TTS"]["reference_wav"],
            "prompt_text": config_data["TTS"]["prompt_text"],
            "prompt_language": config_data["TTS"]["prompt_language"],
            "text_language": config_data["TTS"]["text_language"],
            "enable_tts": config_data["TTS"]["enable_tts"],
        }

        with open(self.config_file, "w") as f:
            config.write(f)

        self.config = config_data
        return True

    def check_config(self):
        """检查必要配置是否完整"""
        if not self.config:
            return ["配置文件未加载"]

        required_fields = [
            ("API", "ollama_url", "Ollama API地址"),
            ("API", "tts_url", "TTS服务地址"),
            ("TTS", "reference_wav", "参考音频路径"),
            ("TTS", "prompt_text", "参考文本"),
        ]

        missing = []
        for section, key, name in required_fields:
            if not self.config[section].get(key, "").strip():
                missing.append(f"{name} ({section}.{key})")

        return missing

    def reset_audio_state(self):
        """重置音频相关状态"""
        self.audio_generated.clear()
        self.audio_file_path = None
        self.tts_error = None
        self.tts_elapsed = None
        self.audio_ready = False


# 初始化应用状态
app_state = AppState()
app_state.load_config()

# ======================
# API 服务函数
# ======================
def get_ollama_models():
    """获取本地安装的Ollama模型列表"""
    if not app_state.config or not app_state.config["API"].get("ollama_url"):
        return ["qwen2.5vl:latest"]

    try:
        base_url = app_state.config["API"]["ollama_url"].replace("/api/generate", "")
        models_url = f"{base_url}/api/tags"
        response = requests.get(models_url, timeout=10)
        response.raise_for_status()
        models_data = response.json()
        return [model["name"] for model in models_data.get("models", [])]
    except Exception as e:
        print(f"获取模型列表失败: {str(e)}")
        return ["qwen2.5vl:latest", "llama3:latest", "mistral:latest"]

def generate_completion(prompt, model=None):
    """生成文本回复"""
    if not app_state.config or not app_state.config["API"].get("ollama_url"):
        raise gr.Error("Ollama API地址未配置！请先完成配置")

    if not model:
        model = app_state.config["API"].get("default_model", "qwen2.5vl:latest")

    start_time = time.time()
    url = app_state.config["API"]["ollama_url"]
    headers = {"Content-Type": "application/json"}
    data = {"model": model, "prompt": prompt, "stream": False}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        elapsed = time.time() - start_time
        
        raw_response = response.json().get("response", "")
        # 移除<think></think>标签及其内容
        cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)
        
        return cleaned_response, elapsed, model
    except Exception as e:
        raise gr.Error(f"生成回复时出错: {str(e)}")

def tts_service(text):
    """调用TTS服务生成语音"""
    if not app_state.config:
        raise gr.Error("配置未加载，无法进行语音合成")

    missing = app_state.check_config()
    if missing:
        raise gr.Error(f"配置不完整，无法进行语音合成。缺少: {', '.join(missing)}")

    start_time = time.time()
    tts_url = app_state.config["API"]["tts_url"]

    try:
        response = requests.get(
            tts_url,
            params={
                "refer_wav_path": app_state.config["TTS"]["reference_wav"],
                "prompt_text": app_state.config["TTS"]["prompt_text"],
                "prompt_language": app_state.config["TTS"]["prompt_language"],
                "text": text,
                "text_language": app_state.config["TTS"]["text_language"],
            },
            timeout=300,
        )

        response.raise_for_status()
        elapsed = time.time() - start_time

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_file = f"output_audio_{timestamp}.wav"
        with open(audio_file, "wb") as f:
            f.write(response.content)
        return audio_file, elapsed
    except Exception as e:
        raise gr.Error(f"语音合成失败: {str(e)}")

# ======================
# 聊天处理函数
# ======================
def typewriter_effect(text, delay=0.03):
    """实现打字机效果"""
    for i in range(len(text) + 1):
        yield text[:i]
        time.sleep(delay)

def generate_audio_in_thread(text):
    """在后台线程中生成语音"""
    try:
        audio_file, elapsed = tts_service(text)
        app_state.audio_file_path = audio_file
        app_state.tts_elapsed = f"{elapsed:.2f}秒"
        app_state.audio_generated.set()
        return audio_file, elapsed
    except Exception as e:
        app_state.tts_error = str(e)
        app_state.audio_generated.set()
        return None, str(e)

def chat_with_monica(input_text, model):
    """处理用户输入并生成Monica的回复"""
    app_state.reset_audio_state()

    missing = app_state.check_config()
    if missing:
        raise gr.Error(f"配置不完整，无法聊天。缺少: {', '.join(missing)}")

    # 生成文本回复
    completion, gen_elapsed, used_model = generate_completion(input_text, model)
    monica_response = f"LocalTalk（使用 {used_model}）：{completion}"
    time_log = [f"{gen_elapsed:.2f}秒"]

    # 检查是否启用了语音生成
    enable_tts = app_state.config["TTS"].get("enable_tts", "True").lower() == "true"

    if enable_tts:
        threading.Thread(
            target=generate_audio_in_thread, args=(completion,), daemon=True
        ).start()
    else:
        app_state.audio_generated.set()

    return monica_response, time_log

def stream_response(monica_response, time_log, show):
    """流式响应生成器，包含打字机效果和语音状态更新"""
    if monica_response is None:
        yield "错误：未收到回复", "", ""
        return

    # 初始化时间显示
    gen_time_display = time_log[0] if show else ""
    tts_time_display = ""
    
    # 应用打字机效果
    for partial_text in typewriter_effect(monica_response):
        # 检查语音状态
        audio_status = ""
        enable_tts = app_state.config["TTS"].get("enable_tts", "True").lower() == "true"

        if enable_tts:
            if app_state.audio_generated.is_set():
                if app_state.audio_file_path:
                    audio_status = "🔊 语音就绪"
                    tts_time_display = app_state.tts_elapsed if app_state.tts_elapsed else ""
                    if not app_state.audio_ready:
                        app_state.audio_ready = True
                elif app_state.tts_error:
                    audio_status = f"❌ 语音生成失败: {app_state.tts_error}"
            else:
                audio_status = "⏳ 正在生成语音..."
        else:
            audio_status = "🔇 语音功能已禁用"

        # 更新显示文本
        display_text = f"{partial_text}\n\n{audio_status}"
        yield display_text, gen_time_display, tts_time_display

    # 最终显示状态
    final_text = monica_response
    if enable_tts:
        if app_state.tts_error:
            final_text += f"\n\n语音生成失败: {app_state.tts_error}"
        elif app_state.audio_generated.is_set() and not app_state.audio_file_path:
            final_text += "\n\n语音生成失败: 未知错误"

    # 确保语音合成时间已更新
    if enable_tts and app_state.audio_generated.is_set() and app_state.audio_file_path and app_state.tts_elapsed:
        tts_time_display = app_state.tts_elapsed
    
    yield final_text, gen_time_display, tts_time_display

def get_audio_component():
    """只在音频就绪时返回音频组件"""
    if app_state.audio_ready and app_state.audio_file_path:
        return gr.Audio(value=app_state.audio_file_path, autoplay=True, visible=True)
    return gr.Audio(visible=False)

# ======================
# 界面创建函数
# ======================
def create_config_wizard():
    """创建配置向导界面"""
    with gr.Blocks(title="配置向导") as wizard:
        gr.Markdown("# 🧙‍♂️ 欢迎使用LocalTalk配置向导")
        gr.Markdown("首次使用需要完成以下配置，请根据您的环境填写相应信息")

        with gr.Accordion("1. Ollama API 设置", open=True):
            gr.Markdown(
                """
            ### 什么是 Ollama API?
            Ollama 是一个本地运行大型语言模型的工具，您需要先安装并启动 Ollama 服务。
            
            **安装步骤:**
            1. 访问 [Ollama 官网](https://ollama.com/) 下载并安装
            2. 安装后运行命令: `ollama serve`
            3. 下载模型: `ollama pull qwen2.5vl:latest`
            
            **API 地址格式:** `http://<您的IP地址>:11434/api/generate`
            - 如果在本机运行: `http://localhost:11434/api/generate`
            - 如果在远程服务器运行: `http://服务器IP:11434/api/generate`
            """
            )
            ollama_url = gr.Textbox(
                label="Ollama API 地址",
                placeholder="例如: http://localhost:11434/api/generate",
            )

            gr.Markdown("### 默认模型设置")
            default_model = gr.Textbox(
                label="默认模型",
                placeholder="例如: qwen2.5vl:latest",
                value="qwen2.5vl:latest",
            )
            gr.Markdown("💡 提示: 安装更多模型后，可以在聊天界面中选择使用")

        with gr.Accordion("2. TTS 服务设置", open=True):
            gr.Markdown(
                """
            ### 什么是 TTS 服务?
            TTS (Text-to-Speech) 服务将文本转换为语音，您需要部署 GPT-SoVITS 语音克隆服务。
            
            **部署步骤:**
            1. 从 [GPT-SoVITS 仓库](https://github.com/RVC-Boss/GPT-SoVITS) 克隆项目
            2. 按照项目说明安装依赖并启动服务
            3. 默认服务地址: `http://localhost:9880`
            
            **服务地址格式:** `http://<您的IP地址>:9880`
            - 如果在本机运行: `http://localhost:9880`
            - 如果在远程服务器运行: `http://服务器IP:9880`
            """
            )
            tts_url = gr.Textbox(
                label="TTS 服务地址", placeholder="例如: http://localhost:9880"
            )

        with gr.Accordion("3. 语音克隆设置", open=True):
            gr.Markdown(
                """
            ### 语音克隆参考设置
            为了让LocalTalk拥有独特的声音，您需要提供一段参考音频和对应的参考文本。
            
            **要求:**
            - 参考音频时长 10-30 秒
            - 清晰无背景噪音
            - 参考文本需与音频内容完全一致
            """
            )

            with gr.Row():
                with gr.Column():
                    reference_wav = gr.Textbox(
                        label="参考音频文件路径",
                        placeholder="例如: C:/voice_samples/monica.wav",
                    )
                    gr.Markdown("💡 提示: 右键文件选择'复制为路径'获取完整路径")

                with gr.Column():
                    prompt_text = gr.Textbox(
                        label="参考文本",
                        placeholder="例如: 你好，我是LocalTalk，很高兴为您服务...",
                        lines=3,
                    )

            gr.Markdown(
                """
            **语言设置:**
            - 参考文本语言: 音频使用的语言代码 (zh-中文, en-英文, jp-日文)
            - 合成文本语言: 您希望LocalTalk使用的语言
            """
            )

            with gr.Row():
                prompt_lang = gr.Dropdown(
                    label="参考文本语言", choices=["zh", "en", "jp"], value="zh"
                )
                text_lang = gr.Dropdown(
                    label="合成文本语言", choices=["zh", "en", "jp"], value="zh"
                )

            # 添加语音生成开关
            enable_tts = gr.Checkbox(
                label="启用语音生成功能",
                value=True,
                info="如果禁用此选项，聊天时将不会生成语音",
            )

        # 配置验证和保存
        status = gr.Textbox(
            label="配置状态", interactive=False, value="请填写所有必要配置项"
        )
        save_btn = gr.Button("✅ 保存配置并启动", variant="primary")

        def validate_and_save_config(
            ollama, tts, ref_wav, p_text, p_lang, t_lang, d_model, tts_enabled
        ):
            # 验证必要字段
            errors = []
            if not ollama.strip():
                errors.append("Ollama API地址")
            if not tts.strip():
                errors.append("TTS服务地址")
            if not ref_wav.strip():
                errors.append("参考音频路径")
            if not p_text.strip():
                errors.append("参考文本")

            if errors:
                return f"❌ 配置不完整，请填写: {', '.join(errors)}"

            # 验证文件路径
            if not os.path.exists(ref_wav):
                return f"❌ 参考音频文件不存在: {ref_wav}"

            # 保存配置
            config_data = {
                "API": {"ollama_url": ollama, "tts_url": tts, "default_model": d_model},
                "TTS": {
                    "reference_wav": ref_wav,
                    "prompt_text": p_text,
                    "prompt_language": p_lang,
                    "text_language": t_lang,
                    "enable_tts": str(tts_enabled),
                },
            }

            if app_state.save_config(config_data):
                return "✅ 配置保存成功！应用将在3秒后重启..."
            else:
                return "❌ 配置保存失败"

        save_btn.click(
            validate_and_save_config,
            inputs=[
                ollama_url,
                tts_url,
                reference_wav,
                prompt_text,
                prompt_lang,
                text_lang,
                default_model,
                enable_tts,
            ],
            outputs=status,
        )

        # 保存成功后重启应用
        def restart_application(status_msg):
            if status_msg.startswith("✅"):
                time.sleep(3)
                os.execl(sys.executable, sys.executable, *sys.argv)
            return status_msg

        status.change(fn=restart_application, inputs=status, outputs=status)

    return wizard

def create_chat_interface():
    """创建聊天界面"""
    model_list = get_ollama_models() if app_state.config else ["qwen2.5vl:latest"]
    default_model = app_state.config["API"]["default_model"] if app_state.config else "qwen2.5vl:latest"

    with gr.Blocks(title="LocalTalk") as chat_interface:
        # 显示配置状态
        config_status = gr.Markdown()

        def update_config_status():
            missing = app_state.check_config()
            if missing:
                return f"⚠️ **聊天功能不可用**，缺少必要配置: {', '.join(missing)}\n请前往'配置'页面进行设置"
            else:
                enable_tts = app_state.config["TTS"].get("enable_tts", "True").lower() == "true"
                tts_status = "启用" if enable_tts else "禁用"
                return f"✅ **所有配置已设置**，可以开始聊天！\n语音功能: {tts_status}"

        config_status.value = update_config_status()

        gr.Markdown(
            """
        # 💬 开始聊天吧
        """
        )

        with gr.Row():
            with gr.Column():
                # 模型选择下拉框
                model_selector = gr.Dropdown(
                    label="选择语言模型",
                    choices=model_list,
                    value=default_model,
                    interactive=not bool(app_state.check_config()),
                )

                user_input = gr.Textbox(
                    label="您的消息",
                    placeholder="请输入您想说的话...",
                    interactive=not bool(app_state.check_config()),
                )

                with gr.Row():
                    submit_btn = gr.Button(
                        "发送", variant="primary", interactive=not bool(app_state.check_config())
                    )
                    show_time = gr.Checkbox(label="显示耗时统计", value=True)

            with gr.Column():
                chat_output = gr.Textbox(
                    label="对话记录",
                    lines=10,
                    interactive=False,
                    elem_classes=["monica-chat"],
                )
                audio_output = gr.Audio(
                    label="LocalTalk的语音回复",
                    autoplay=True,
                    visible=False,
                    elem_classes=["monica-voice"],
                )

            with gr.Row(visible=True) as time_row:
                gen_time = gr.Textbox(
                    label="文本生成耗时",
                    interactive=False,
                    elem_classes=["time-stats"],
                )
                tts_time = gr.Textbox(
                    label="语音合成耗时",
                    interactive=False,
                    elem_classes=["time-stats"],
                )

        # 用于存储中间状态
        full_response = gr.State()
        time_state = gr.State()

        def toggle_time_visibility(show):
            return gr.Row.update(visible=show)

        # 显示/隐藏耗时统计
        show_time.change(fn=toggle_time_visibility, inputs=show_time, outputs=time_row)

        # 设置按钮点击事件
        submit_btn.click(
            fn=chat_with_monica,
            inputs=[user_input, model_selector],
            outputs=[full_response, time_state],
        ).then(
            fn=stream_response,
            inputs=[full_response, time_state, show_time],
            outputs=[chat_output, gen_time, tts_time],
        ).then(
            fn=get_audio_component,
            inputs=[],
            outputs=audio_output
        )

        # 设置回车键提交
        user_input.submit(
            fn=chat_with_monica,
            inputs=[user_input, model_selector],
            outputs=[full_response, time_state],
        ).then(
            fn=stream_response,
            inputs=[full_response, time_state, show_time],
            outputs=[chat_output, gen_time, tts_time],
        ).then(
            fn=get_audio_component,
            inputs=[],
            outputs=audio_output
        )

    return chat_interface

def create_config_editor():
    """创建配置编辑器界面"""
    # 确保配置已加载
    if not app_state.config:
        app_state.load_config()
    
    # 如果配置仍然为空，使用默认值
    config = app_state.config or {
        "API": {"ollama_url": "", "tts_url": "", "default_model": "qwen2.5vl:latest"},
        "TTS": {"reference_wav": "", "prompt_text": "", "prompt_language": "zh", "text_language": "zh", "enable_tts": "True"}
    }

    with gr.Blocks(title="配置管理") as config_editor:
        gr.Markdown("## ⚙️ 系统配置管理")
        gr.Markdown("您可以在此修改应用配置参数")

        # 显示当前配置
        gr.Markdown("### 当前配置:")
        with gr.Row():
            with gr.Column():
                gr.Markdown("#### API 设置")
                ollama_url = gr.Textbox(
                    label="Ollama API地址", value=config["API"].get("ollama_url", "")
                )
                tts_url = gr.Textbox(
                    label="TTS服务地址", value=config["API"].get("tts_url", "")
                )
                default_model = gr.Textbox(
                    label="默认模型",
                    value=config["API"].get("default_model", "qwen2.5vl:latest"),
                )
            with gr.Column():
                gr.Markdown("#### TTS 设置")
                reference_wav = gr.Textbox(
                    label="参考音频路径", value=config["TTS"].get("reference_wav", "")
                )
                prompt_text = gr.Textbox(
                    label="参考文本", value=config["TTS"].get("prompt_text", "")
                )
                with gr.Row():
                    prompt_lang = gr.Dropdown(
                        label="参考文本语言",
                        choices=["zh", "en", "jp"],
                        value=config["TTS"].get("prompt_language", "zh"),
                    )
                    text_lang = gr.Dropdown(
                        label="合成文本语言",
                        choices=["zh", "en", "jp"],
                        value=config["TTS"].get("text_language", "zh"),
                    )

                # 添加语音生成开关
                enable_tts = gr.Checkbox(
                    label="启用语音生成功能",
                    value=config["TTS"].get("enable_tts", "True").lower() == "true",
                    info="如果禁用此选项，聊天时将不会生成语音",
                )

        # 保存按钮
        save_btn = gr.Button("💾 保存配置", variant="primary")
        status = gr.Textbox(label="保存状态", interactive=False)

        def save_current_config(
            ollama, tts, ref_wav, p_text, p_lang, t_lang, d_model, tts_enabled
        ):
            config_data = {
                "API": {"ollama_url": ollama, "tts_url": tts, "default_model": d_model},
                "TTS": {
                    "reference_wav": ref_wav,
                    "prompt_text": p_text,
                    "prompt_language": p_lang,
                    "text_language": t_lang,
                    "enable_tts": str(tts_enabled),
                },
            }

            if app_state.save_config(config_data):
                return "✅ 配置保存成功！"
            else:
                return "❌ 配置保存失败"

        save_btn.click(
            save_current_config,
            inputs=[
                ollama_url,
                tts_url,
                reference_wav,
                prompt_text,
                prompt_lang,
                text_lang,
                default_model,
                enable_tts,
            ],
            outputs=status,
        )

    return config_editor

# ======================
# 主应用入口
# ======================
def launch_application():
    """启动应用程序"""
    # 清理旧的音频文件
    for file in os.listdir():
        if file.startswith("output_audio_") and file.endswith(".wav"):
            try:
                os.remove(file)
            except:
                pass

    # 创建主应用界面
    with gr.Blocks(
        theme=gr.themes.Soft(),
        css="""
        .monica-chat {font-size: 16px !important} 
        .time-stats {width: 100px !important}
        .monica-voice {max-height: 100px !important}
        """,
    ) as main_app:
        # 根据是否首次运行显示不同界面
        if app_state.first_run or not app_state.config or app_state.check_config():
            gr.Markdown("# 🚀 欢迎使用LocalTalk")
            with gr.Tabs():
                with gr.TabItem("初始配置", id="wizard"):
                    wizard = create_config_wizard()
        else:
            gr.Markdown("# 💬 LocalTalk")
            with gr.Tabs():
                with gr.TabItem("聊天", id="chat"):
                    chat_interface = create_chat_interface()
                with gr.TabItem("配置管理", id="config"):
                    config_editor = create_config_editor()

    # 启动应用
    main_app.launch(
        server_name="0.0.0.0",
        server_port=9976,
        share=False,
        inbrowser=False,
        show_error=True,
        pwa=True,
    )

# 主程序入口
if __name__ == "__main__":
    launch_application()