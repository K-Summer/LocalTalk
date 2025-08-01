import requests
import gradio as gr
import time
import os
from datetime import datetime


def generate_completion(prompt, model="monika:latest"):
    start_time = time.time()
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    data = {"model": model, "prompt": prompt, "stream": False}

    response = requests.post(url, headers=headers, json=data)
    elapsed = time.time() - start_time
    return response.json().get("response", ""), elapsed


def tts_service(text):
    start_time = time.time()
    tts_url = "http://localhost:9880"
    response = requests.get(
        tts_url,
        params={
            "refer_wav_path": "参考音频",
            "prompt_text": "参考文本",
            "prompt_language": "zh",
            "text": text,
            "text_language": "zh",
        },
    )

    elapsed = time.time() - start_time
    if response.status_code == 200:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_file = f"output_audio_{timestamp}.wav"
        with open(audio_file, "wb") as f:
            f.write(response.content)
        return audio_file, elapsed
    else:
        raise gr.Error(f"语音合成服务错误: {response.text}")


def typewriter_effect(text, delay=0.03):
    """实现打字机效果"""
    for i in range(len(text) + 1):
        yield text[:i]
        time.sleep(delay)


def chat_with_monica(input_text):
    time_log = []
    total_start = time.time()

    # 生成回复
    gen_start = time.time()
    completion, gen_elapsed = generate_completion(input_text)
    time_log.append(f"{gen_elapsed:.2f}秒")

    monica_response = f"LocalTalk：{completion}"

    # 生成语音
    tts_start = time.time()
    audio_file, tts_elapsed = tts_service(completion)
    time_log.append(f"{tts_elapsed:.2f}秒")

    # 总耗时
    total_elapsed = time.time() - total_start
    time_log.append(f"{total_elapsed:.2f}秒")

    return monica_response, audio_file, time_log


# 创建Gradio界面
with gr.Blocks(title="LocalTalk聊天助手") as demo:
    gr.Markdown(
        """
    # LocalTalk聊天助手
    """
    )

    with gr.Row():
        with gr.Column():
            user_input = gr.Textbox(label="您的消息", placeholder="请输入您想说的话...")
            with gr.Row():
                submit_btn = gr.Button("发送", variant="primary")
                show_time = gr.Checkbox(label="显示耗时统计", value=True)

        with gr.Column():
            chat_output = gr.Textbox(label="对话记录", lines=6, interactive=False)
            audio_output = gr.Audio(
                label="LocalTalk的回复", autoplay=True, visible=False
            )

            with gr.Row(visible=True) as time_row:
                gen_time = gr.Textbox(label="文本生成耗时", interactive=False)
                tts_time = gr.Textbox(label="语音合成耗时", interactive=False)
                total_time = gr.Textbox(label="总耗时", interactive=False)

    # 用于存储中间状态
    full_response = gr.State()
    audio_state = gr.State()
    time_state = gr.State()

    def toggle_time_visibility(show):
        return gr.Row.update(visible=show)

    def process_input(input_text):
        # 首先生成完整回复
        monica_response, audio_file, time_log = chat_with_monica(input_text)
        return monica_response, audio_file, time_log, gr.Audio(visible=True)

    def stream_response(monica_response, audio_file, time_log, show):
        if monica_response is None:
            yield "错误：未收到回复", gr.Audio(visible=False), "", "", ""
            return

        # 应用打字机效果
        for partial_text in typewriter_effect(monica_response):
            yield partial_text + "\n\n(正在输入...)", gr.Audio(
                visible=False
            ), "", "", ""

        # 最后显示完整内容
        time_display = (time_log[0], time_log[1], time_log[2]) if show else ("", "", "")
        yield monica_response, gr.Audio(value=audio_file, visible=True), *time_display

    # 显示/隐藏耗时统计
    show_time.change(fn=toggle_time_visibility, inputs=show_time, outputs=time_row)

    # 设置按钮点击事件
    submit_btn.click(
        fn=process_input,
        inputs=user_input,
        outputs=[full_response, audio_state, time_state, audio_output],
    ).then(
        fn=stream_response,
        inputs=[full_response, audio_state, time_state, show_time],
        outputs=[chat_output, audio_output, gen_time, tts_time, total_time],
    )

    # 设置回车键提交
    user_input.submit(
        fn=process_input,
        inputs=user_input,
        outputs=[full_response, audio_state, time_state, audio_output],
    ).then(
        fn=stream_response,
        inputs=[full_response, audio_state, time_state, show_time],
        outputs=[chat_output, audio_output, gen_time, tts_time, total_time],
    )

# 启动应用
if __name__ == "__main__":
    # 清理旧的音频文件
    for file in os.listdir():
        if file.startswith("output_audio_") and file.endswith(".wav"):
            try:
                os.remove(file)
            except:
                pass
    demo.launch(share=True, server_name="0.0.0.0", server_port=9976, pwa=True)
