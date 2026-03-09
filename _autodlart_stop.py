import requests
import json

def autodl_remote_power_off(instance_uuid: str, token: str) -> dict:
    # API配置
    url = "https://www.autodl.art/api/v1/adl_dev/dev/instance/pro/power_off"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    body = {
        "instance_uuid": instance_uuid,
    }
    
    # 发送请求
    try:
        response = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(body),
            timeout=10
        )
        response.raise_for_status()  # 抛出HTTP错误
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # 请替换为你的实际信息
    YOUR_INSTANCE_UUID = "*****"
    YOUR_AUTODL_TOKEN = "*****"
    
    # 关机
    print("正在尝试关机...")
    gpu_result = autodl_remote_power_off(
        instance_uuid=YOUR_INSTANCE_UUID,
        token=YOUR_AUTODL_TOKEN
    )
    print("有卡模式开机结果:", gpu_result)