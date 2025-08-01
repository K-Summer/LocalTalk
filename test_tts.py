import requests

# 文本转语音服务的URL
tts_url = "http://localhost:9880"

def test_tts_service(text):
    tts_response = requests.get(tts_url, params={
        "refer_wav_path": "参考音频",
        "prompt_text": "参考文本",
        "prompt_language": "zh",
        "text": text,
        "text_language": "zh"
    })
    
    if tts_response.status_code == 200:
        with open("output_audio.wav", "wb") as f:
            f.write(tts_response.content)
        print("音频文件已成功保存为 output_audio.wav")
    else:
        print(f"Error in TTS service: {tts_response.text}")

# 测试文本
test_text = "这是一次语音测试。"
test_tts_service(test_text)
