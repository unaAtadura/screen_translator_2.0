from zai import ZhipuAiClient
import base64

client = ZhipuAiClient(api_key="")  # 填写您自己的APIKey

img_path = "google.png"
with open(img_path, "rb") as img_file:
    img_base = base64.b64encode(img_file.read()).decode("utf-8")

response = client.chat.completions.create(
    model="glm-4.6v-flash",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": img_base
                    }
                },
                {
                    "type": "text",
                    "text": "请识别图片中的所有文字，保持原始格式和顺序，不要添加任何解释或说明。"
                }
            ]
        }
    ],
    thinking={
        "type": "disabled"
    }
)
print(response.choices[0].message)