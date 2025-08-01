import requests
import gradio as gr
import time
import os
import sys
import configparser
from datetime import datetime
import webbrowser
import threading

# 配置文件路径
CONFIG_FILE = "config.ini"
CONFIG = None
FIRST_RUN = not os.path.exists(CONFIG_FILE)

def load_config():
    """加载配置文件"""
    global CONFIG
    if not os.path.exists(CONFIG_FILE):
        return None
    
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    CONFIG = {
        "API": {
            "ollama_url": config.get("API", "ollama_url", fallback=""),
            "tts_url": config.get("API", "tts_url", fallback=""),
            "default_model": config.get("API", "default_model", fallback="monika:latest")
        },
        "TTS": {
            "reference_wav": config.get("TTS", "reference_wav", fallback=""),
            "prompt_text": config.get("TTS", "prompt_text", fallback=""),
            "prompt_language": config.get("TTS", "prompt_language", fallback="zh"),
            "text_language": config.get("TTS", "text_language", fallback="zh")
        }
    }
    return CONFIG

def save_config(config_data):
    """保存配置文件"""
    config = configparser.ConfigParser()
    config["API"] = {
        "ollama_url": config_data["API"]["ollama_url"],
        "tts_url": config_data["API"]["tts_url"],
        "default_model": config_data["API"]["default_model"]
    }
    config["TTS"] = {
        "reference_wav": config_data["TTS"]["reference_wav"],
        "prompt_text": config_data["TTS"]["prompt_text"],
        "prompt_language": config_data["TTS"]["prompt_language"],
        "text_language": config_data["TTS"]["text_language"]
    }
    
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)
    
    global CONFIG
    CONFIG = config_data
    return True

def check_config():
    """检查必要配置是否完整"""
    if not CONFIG:
        return ["配置文件未加载"]
    
    required_fields = [
        ("API", "ollama_url", "Ollama API地址"),
        ("API", "tts_url", "TTS服务地址"),
        ("TTS", "reference_wav", "参考音频路径"),
        ("TTS", "prompt_text", "参考文本")
    ]
    
    missing = []
    for section, key, name in required_fields:
        if not CONFIG[section].get(key, "").strip():
            missing.append(f"{name} ({section}.{key})")
    
    return missing

def get_ollama_models():
    """获取本地安装的Ollama模型列表"""
    if not CONFIG or not CONFIG["API"].get("ollama_url"):
        return ["qwen2.5vl:latest"]
    
    try:
        # 构建获取模型列表的URL
        base_url = CONFIG["API"]["ollama_url"].replace("/api/generate", "")
        models_url = f"{base_url}/api/tags"
        
        response = requests.get(models_url, timeout=10)
        response.raise_for_status()
        
        models_data = response.json()
        return [model["name"] for model in models_data.get("models", [])]
    except Exception as e:
        print(f"获取模型列表失败: {str(e)}")
        # 返回默认模型列表
        return ["qwen2.5vl:latest", "llama3:latest", "mistral:latest"]

def generate_completion(prompt, model=None):
    if not CONFIG or not CONFIG["API"].get("ollama_url"):
        raise gr.Error("Ollama API地址未配置！请先完成配置")
    
    # 如果没有指定模型，使用配置中的默认模型
    if not model:
        model = CONFIG["API"].get("default_model", "qwen2.5vl:latest")
    
    start_time = time.time()
    url = CONFIG["API"]["ollama_url"]
    headers = {"Content-Type": "application/json"}
    data = {"model": model, "prompt": prompt, "stream": False}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        elapsed = time.time() - start_time
        return response.json().get("response", ""), elapsed, model
    except Exception as e:
        raise gr.Error(f"生成回复时出错: {str(e)}")

def tts_service(text):
    if not CONFIG:
        raise gr.Error("配置未加载，无法进行语音合成")
    
    missing = check_config()
    if missing:
        raise gr.Error(f"配置不完整，无法进行语音合成。缺少: {', '.join(missing)}")
    
    start_time = time.time()
    tts_url = CONFIG["API"]["tts_url"]
    
    try:
        response = requests.get(tts_url, params={
            "refer_wav_path": CONFIG["TTS"]["reference_wav"],
            "prompt_text": CONFIG["TTS"]["prompt_text"],
            "prompt_language": CONFIG["TTS"]["prompt_language"],
            "text": text,
            "text_language": CONFIG["TTS"]["text_language"]
        }, timeout=30)
        
        response.raise_for_status()
        elapsed = time.time() - start_time
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_file = f"output_audio_{timestamp}.wav"
        with open(audio_file, "wb") as f:
            f.write(response.content)
        return audio_file, elapsed
    except Exception as e:
        raise gr.Error(f"语音合成失败: {str(e)}")

def typewriter_effect(text, delay=0.03):
    """实现打字机效果"""
    for i in range(len(text)+1):
        yield text[:i]
        time.sleep(delay)

def chat_with_monica(input_text, model):
    missing = check_config()
    if missing:
        raise gr.Error(f"配置不完整，无法聊天。缺少: {', '.join(missing)}")
    
    time_log = []
    total_start = time.time()
    
    # 生成回复
    completion, gen_elapsed, used_model = generate_completion(input_text, model)
    time_log.append(f"{gen_elapsed:.2f}秒")
    
    monica_response = f"莫妮卡（使用 {used_model}）：{completion}"
    
    # 生成语音
    audio_file, tts_elapsed = tts_service(completion)
    time_log.append(f"{tts_elapsed:.2f}秒")
    
    # 总耗时
    total_elapsed = time.time() - total_start
    time_log.append(f"{total_elapsed:.2f}秒")
    
    return monica_response, audio_file, time_log

def open_browser():
    """等待Gradio启动后打开浏览器"""
    time.sleep(5)
    webbrowser.open("http://localhost:9976")

def create_config_wizard():
    """创建配置向导界面"""
    with gr.Blocks(title="配置向导") as wizard:
        gr.Markdown("# 🧙‍♂️ 欢迎使用莫妮卡聊天助手配置向导")
        gr.Markdown("首次使用需要完成以下配置，请根据您的环境填写相应信息")
        
        with gr.Accordion("1. Ollama API 设置", open=True):
            gr.Markdown("""
            ### 什么是 Ollama API?
            Ollama 是一个本地运行大型语言模型的工具，您需要先安装并启动 Ollama 服务。
            
            **安装步骤:**
            1. 访问 [Ollama 官网](https://ollama.com/) 下载并安装
            2. 安装后运行命令: `ollama serve`
            3. 下载模型: `ollama pull qwen2.5vl:latest`
            
            **API 地址格式:** `http://<您的IP地址>:11434/api/generate`
            - 如果在本机运行: `http://localhost:11434/api/generate`
            - 如果在远程服务器运行: `http://服务器IP:11434/api/generate`
            """)
            ollama_url = gr.Textbox(
                label="Ollama API 地址",
                placeholder="例如: http://localhost:11434/api/generate"
            )
            
            gr.Markdown("### 默认模型设置")
            default_model = gr.Textbox(
                label="默认模型",
                placeholder="例如: qwen2.5vl:latest",
                value="qwen2.5vl:latest"
            )
            gr.Markdown("💡 提示: 安装更多模型后，可以在聊天界面中选择使用")
        
        with gr.Accordion("2. TTS 服务设置", open=True):
            gr.Markdown("""
            ### 什么是 TTS 服务?
            TTS (Text-to-Speech) 服务将文本转换为语音，您需要部署 GPT-SoVITS 语音克隆服务。
            
            **部署步骤:**
            1. 从 [GPT-SoVITS 仓库](https://github.com/RVC-Boss/GPT-SoVITS) 克隆项目
            2. 按照项目说明安装依赖并启动服务
            3. 默认服务地址: `http://localhost:9880`
            
            **服务地址格式:** `http://<您的IP地址>:9880`
            - 如果在本机运行: `http://localhost:9880`
            - 如果在远程服务器运行: `http://服务器IP:9880`
            """)
            tts_url = gr.Textbox(
                label="TTS 服务地址",
                placeholder="例如: http://localhost:9880"
            )
        
        with gr.Accordion("3. 语音克隆设置", open=True):
            gr.Markdown("""
            ### 语音克隆参考设置
            为了让莫妮卡拥有独特的声音，您需要提供一段参考音频和对应的参考文本。
            
            **要求:**
            - 参考音频时长 10-30 秒
            - 清晰无背景噪音
            - 参考文本需与音频内容完全一致
            """)
            
            with gr.Row():
                with gr.Column():
                    reference_wav = gr.Textbox(
                        label="参考音频文件路径",
                        placeholder="例如: C:/voice_samples/monica.wav"
                    )
                    gr.Markdown("💡 提示: 右键文件选择'复制为路径'获取完整路径")
                
                with gr.Column():
                    prompt_text = gr.Textbox(
                        label="参考文本",
                        placeholder="例如: 你好，我是莫妮卡，很高兴为您服务...",
                        lines=3
                    )
            
            gr.Markdown("""
            **语言设置:**
            - 参考文本语言: 音频使用的语言代码 (zh-中文, en-英文, jp-日文)
            - 合成文本语言: 您希望莫妮卡使用的语言
            """)
            
            with gr.Row():
                prompt_lang = gr.Dropdown(
                    label="参考文本语言",
                    choices=["zh", "en", "jp"],
                    value="zh"
                )
                text_lang = gr.Dropdown(
                    label="合成文本语言",
                    choices=["zh", "en", "jp"],
                    value="zh"
                )
        
        # 配置验证和保存
        status = gr.Textbox(label="配置状态", interactive=False, value="请填写所有必要配置项")
        save_btn = gr.Button("✅ 保存配置并启动", variant="primary")
        
        def validate_and_save_config(
            ollama, tts, ref_wav, p_text, p_lang, t_lang, d_model
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
                "API": {
                    "ollama_url": ollama,
                    "tts_url": tts,
                    "default_model": d_model
                },
                "TTS": {
                    "reference_wav": ref_wav,
                    "prompt_text": p_text,
                    "prompt_language": p_lang,
                    "text_language": t_lang
                }
            }
            
            if save_config(config_data):
                return "✅ 配置保存成功！应用将在3秒后重启..."
            else:
                return "❌ 配置保存失败，请检查文件权限"
        
        save_btn.click(
            validate_and_save_config,
            inputs=[ollama_url, tts_url, reference_wav, prompt_text, prompt_lang, text_lang, default_model],
            outputs=status
        )
        
        # 保存成功后重启应用
        def restart_application(status_msg):
            if status_msg.startswith("✅"):
                time.sleep(3)
                # 重启应用
                os.execl(sys.executable, sys.executable, *sys.argv)
            return status_msg
        
        status.change(
            fn=restart_application,
            inputs=status,
            outputs=status
        )

    return wizard

def create_chat_interface():
    """创建聊天界面"""
    # 获取模型列表
    model_list = get_ollama_models() if CONFIG else ["monika:latest"]
    default_model = CONFIG["API"]["default_model"] if CONFIG else "monika:latest"
    
    with gr.Blocks(title="莫妮卡聊天助手") as chat_interface:
        # 显示配置状态
        config_status = gr.Markdown()
        
        def update_config_status():
            missing = check_config()
            if missing:
                return f"⚠️ **聊天功能不可用**，缺少必要配置: {', '.join(missing)}\n请前往'配置'页面进行设置"
            else:
                return "✅ **所有配置已设置**，可以开始聊天！"
        
        config_status.value = update_config_status()
        
        gr.Markdown("""
        # 💬 莫妮卡聊天助手
        """)
        
        with gr.Row():
            with gr.Column():
                # 模型选择下拉框
                model_selector = gr.Dropdown(
                    label="选择语言模型",
                    choices=model_list,
                    value=default_model,
                    interactive=not bool(check_config())
                )
                
                user_input = gr.Textbox(
                    label="您的消息",
                    placeholder="请输入您想说的话...",
                    interactive=not bool(check_config())
                )
                
                with gr.Row():
                    submit_btn = gr.Button("发送", variant="primary", interactive=not bool(check_config()))
                    show_time = gr.Checkbox(label="显示耗时统计", value=True)
                    refresh_models = gr.Button("🔄 刷新模型列表", size="sm")
            
            with gr.Column():
                chat_output = gr.Textbox(
                    label="对话记录",
                    lines=10,
                    interactive=False,
                    elem_classes=["monica-chat"]
                )
                audio_output = gr.Audio(
                    label="莫妮卡的语音回复",
                    autoplay=True,
                    visible=False,
                    elem_classes=["monica-voice"]
                )
                
                with gr.Row(visible=True) as time_row:
                    gen_time = gr.Textbox(
                        label="文本生成耗时",
                        interactive=False,
                        elem_classes=["time-stats"]
                    )
                    tts_time = gr.Textbox(
                        label="语音合成耗时",
                        interactive=False,
                        elem_classes=["time-stats"]
                    )
                    total_time = gr.Textbox(
                        label="总耗时",
                        interactive=False,
                        elem_classes=["time-stats"]
                    )
        
        # 用于存储中间状态
        full_response = gr.State()
        audio_state = gr.State()
        time_state = gr.State()
        
        def toggle_time_visibility(show):
            return gr.Row.update(visible=show)
        
        def refresh_model_list():
            """刷新模型列表"""
            new_models = get_ollama_models()
            return gr.Dropdown.update(choices=new_models)
        
        def process_input(input_text, selected_model):
            # 检查配置
            missing = check_config()
            if missing:
                raise gr.Error(f"配置不完整，无法聊天。缺少: {', '.join(missing)}")
                
            # 首先生成完整回复
            monica_response, audio_file, time_log = chat_with_monica(input_text, selected_model)
            return monica_response, audio_file, time_log, gr.Audio(visible=True)
        
        def stream_response(monica_response, audio_file, time_log, show):
            if monica_response is None:
                yield "错误：未收到回复", gr.Audio(visible=False), "", "", ""
                return
                
            # 应用打字机效果
            for partial_text in typewriter_effect(monica_response):
                yield partial_text + "\n\n(正在输入...)", gr.Audio(visible=False), "", "", ""
            
            # 最后显示完整内容
            time_display = (
                (time_log[0], time_log[1], time_log[2]) 
                if show else ("", "", "")
            )
            yield monica_response, gr.Audio(value=audio_file, visible=True), *time_display
        
        # 显示/隐藏耗时统计
        show_time.change(
            fn=toggle_time_visibility,
            inputs=show_time,
            outputs=time_row
        )
        
        # 刷新模型列表
        refresh_models.click(
            fn=refresh_model_list,
            outputs=model_selector
        )
        
        # 设置按钮点击事件
        submit_btn.click(
            fn=process_input,
            inputs=[user_input, model_selector],
            outputs=[full_response, audio_state, time_state, audio_output]
        ).then(
            fn=stream_response,
            inputs=[full_response, audio_state, time_state, show_time],
            outputs=[chat_output, audio_output, gen_time, tts_time, total_time]
        )
        
        # 设置回车键提交
        user_input.submit(
            fn=process_input,
            inputs=[user_input, model_selector],
            outputs=[full_response, audio_state, time_state, audio_output]
        ).then(
            fn=stream_response,
            inputs=[full_response, audio_state, time_state, show_time],
            outputs=[chat_output, audio_output, gen_time, tts_time, total_time]
        )
    
    return chat_interface

def create_config_editor():
    """创建配置编辑器界面"""
    with gr.Blocks(title="配置管理") as config_editor:
        gr.Markdown("## ⚙️ 系统配置管理")
        gr.Markdown("您可以在此修改应用配置参数")
        
        # 显示当前配置
        gr.Markdown("### 当前配置:")
        with gr.Row():
            with gr.Column():
                gr.Markdown("#### API 设置")
                ollama_url = gr.Textbox(
                    label="Ollama API地址",
                    value=CONFIG["API"].get("ollama_url", "")
                )
                tts_url = gr.Textbox(
                    label="TTS服务地址",
                    value=CONFIG["API"].get("tts_url", "")
                )
                default_model = gr.Textbox(
                    label="默认模型",
                    value=CONFIG["API"].get("default_model", "qwen2.5vl:latest")
                )
            with gr.Column():
                gr.Markdown("#### TTS 设置")
                reference_wav = gr.Textbox(
                    label="参考音频路径",
                    value=CONFIG["TTS"].get("reference_wav", "")
                )
                prompt_text = gr.Textbox(
                    label="参考文本",
                    value=CONFIG["TTS"].get("prompt_text", "")
                )
                with gr.Row():
                    prompt_lang = gr.Dropdown(
                        label="参考文本语言",
                        choices=["zh", "en", "jp"],
                        value=CONFIG["TTS"].get("prompt_language", "zh")
                    )
                    text_lang = gr.Dropdown(
                        label="合成文本语言",
                        choices=["zh", "en", "jp"],
                        value=CONFIG["TTS"].get("text_language", "zh")
                    )
        
        # 保存按钮
        save_btn = gr.Button("💾 保存配置", variant="primary")
        status = gr.Textbox(label="保存状态", interactive=False)
        
        def save_current_config(
            ollama, tts, ref_wav, p_text, p_lang, t_lang, d_model
        ):
            config_data = {
                "API": {
                    "ollama_url": ollama,
                    "tts_url": tts,
                    "default_model": d_model
                },
                "TTS": {
                    "reference_wav": ref_wav,
                    "prompt_text": p_text,
                    "prompt_language": p_lang,
                    "text_language": t_lang
                }
            }
            
            if save_config(config_data):
                return "✅ 配置保存成功！"
            else:
                return "❌ 配置保存失败"
        
        save_btn.click(
            save_current_config,
            inputs=[ollama_url, tts_url, reference_wav, prompt_text, prompt_lang, text_lang, default_model],
            outputs=status
        )
    
    return config_editor

# 主应用
with gr.Blocks(theme=gr.themes.Soft(), css=".monica-chat {font-size: 16px !important} .time-stats {width: 100px !important}") as main_app:
    # 加载配置
    config_loaded = load_config()
    
    # 根据是否首次运行显示不同界面
    if FIRST_RUN or not config_loaded or check_config():
        gr.Markdown("# 🚀 欢迎使用莫妮卡聊天助手")
        with gr.Tabs():
            with gr.TabItem("初始配置", id="wizard"):
                wizard = create_config_wizard()
    else:
        gr.Markdown("# 💬 莫妮卡聊天助手")
        with gr.Tabs():
            with gr.TabItem("聊天", id="chat"):
                chat_interface = create_chat_interface()
            with gr.TabItem("配置管理", id="config"):
                config_editor = create_config_editor()

# 启动应用
if __name__ == "__main__":
    # 清理旧的音频文件
    for file in os.listdir():
        if file.startswith("output_audio_") and file.endswith(".wav"):
            try:
                os.remove(file)
            except:
                pass
    
    # 在后台线程中打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 启动应用
    main_app.launch(
        server_name="0.0.0.0", 
        server_port=9976,
        share=False,
        inbrowser=False,
        show_error=True
    )