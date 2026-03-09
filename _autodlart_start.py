import requests
import json

def autodl_remote_power_on(instance_uuid: str, token: str, power_mode: str = "gpu") -> dict:
    # 校验参数
    if power_mode not in ["gpu", "non_gpu"]:
        raise ValueError("power_mode只能是'gpu'或'non_gpu'")
    
    # API配置
    url = "https://www.autodl.art/api/v1/adl_dev/dev/instance/pro/power_on"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    body = {
        "instance_uuid": instance_uuid,
        "payload": power_mode
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
    
    # 有卡模式开机（GPU）
    print("正在尝试有卡模式开机...")
    gpu_result = autodl_remote_power_on(
        instance_uuid=YOUR_INSTANCE_UUID,
        token=YOUR_AUTODL_TOKEN,
        power_mode="gpu"
    )
    print("有卡模式开机结果:", gpu_result)