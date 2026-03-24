from zai import ZhipuAiClient

client = ZhipuAiClient(api_key="")  # 填写您自己的 APIKey
response = client.chat.completions.create(
    model="glm-4.6v-flash",  # 填写需要调用的模型名称
    messages=[
        {
            "content": "请将以下文本翻译成中文:\n\nGive me a torch, I am not for this ambling;Being but heavy I will bear the light.",
            "role": "user"
        }
    ],
    thinking={
        "type": "disabled"
    }
)
print(response.choices[0].message)