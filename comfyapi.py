import os
import json
import time
import uuid
import random
import uvicorn
import requests
from typing import Optional
from urllib.parse import quote, unquote, urlparse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, Form, Response

# =============================================================================
# 全局变量
# =============================================================================

FIXED_SEED = None  # 固定种子模式下复用的种子值

# =============================================================================
# 1. 核心配置
# =============================================================================

class Config:
    # ---------- AutoDL 云端地址 ----------
    JUPYTER_URL     = "https://a*****"  #在autodl中jupyter的链接地址前面是a
    COMFYUI_API_URL = "https://u*****"  # 替换为你的ComfyUI公网地址，在autodl中comfyui的链接地址前面是u
    COMFYUI_PROMPT_URL  = f"{COMFYUI_API_URL}prompt"
    COMFYUI_HISTORY_URL = f"{COMFYUI_API_URL}history"
    COMFYUI_UPLOAD_URL  = f"{COMFYUI_API_URL}upload/image"

    # ---------- 本地后端地址 ----------
    BACKEND_HOST = "http://192.168.*.*:8000"

    # ---------- Jupyter 鉴权 Cookie ----------
    # 若图片无法显示，请在浏览器登录 Jupyter 后抓包替换
    JUPYTER_COOKIE = (
        '**********'
    )
    XSRF_TOKEN = "**********"

    # ---------- 工作流文件路径 ----------
    WORKFLOW_PATHS = {
        "z_image":   r".\workflows\Z-Image_双重采样工作流.json",
        "qwen_edit": r".\workflows\Qwen-Imag-Eedit-2511图像编辑.json",
    }

    # ---------- 种子参数名（兼容各类工作流节点） ----------
    SEED_PARAM_NAMES = ["seed", "noise_seed", "random_seed", "latent_seed"]

    # ---------- Z-Image 模型路径映射 ----------
    Z_IMAGE_BASE_MODELS = {
        1: "z_image_bf16.safetensors",
        2: "zib/moodyWildMix_v10Base50steps.safetensors",
        3: "zib/radianceZ_v10.safetensors",
    }
    Z_IMAGE_TURBO_MODELS = {
        1: "z_image_turbo_bf16.safetensors",
        2: "zit/moodyPornMix_zitV8.safetensors",
        3: "zit/pornmasterZImage_turboV1.safetensors",
        4: "zit/zImageTurboNSFW_43BF16Diffusion.safetensors",
    }

    # ---------- ComfyUI 输出目录（与云端一致） ----------
    COMFYUI_OUTPUT_DIR = "ComfyUI/output"

# =============================================================================
# 2. 工作流工具函数
# =============================================================================

def load_workflow(workflow_type: str) -> dict:
    """从本地 workflows 目录加载工作流 JSON，并确保包裹在 {"prompt": ...} 中"""
    path = Config.WORKFLOW_PATHS.get(workflow_type)
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"工作流文件不存在：{path}")
    with open(path, "r", encoding="utf-8") as f:
        workflow = json.load(f)
    if "prompt" not in workflow:
        workflow = {"prompt": workflow}
    return workflow

def save_workflow(workflow_type: str, workflow: dict):
    """将修改后的工作流保存回本地 JSON 文件"""
    path = Config.WORKFLOW_PATHS.get(workflow_type)
    if not path:
        raise FileNotFoundError(f"未找到工作流类型：{workflow_type}")
    # 保存的是 prompt 内层内容（与原始文件格式一致）
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow["prompt"], f, ensure_ascii=False, indent=2)

def replace_z_image_model(workflow: dict, base_model_id: int, turbo_model_id: int) -> dict:
    """替换 Z-Image 工作流中 UNETLoader 节点的 base / turbo 模型路径"""
    base_path  = Config.Z_IMAGE_BASE_MODELS.get(base_model_id)
    turbo_path = Config.Z_IMAGE_TURBO_MODELS.get(turbo_model_id)
    if not base_path or not turbo_path:
        raise ValueError(f"模型ID无效：base={base_model_id}, turbo={turbo_model_id}")

    for node_id, node in workflow["prompt"].items():
        if node.get("class_type") != "UNETLoader":
            continue
        current_name = node["inputs"].get("unet_name", "").lower()
        # 通过文件名关键词区分 base 和 turbo 节点
        if "turbo" in current_name:
            workflow["prompt"][node_id]["inputs"]["unet_name"] = turbo_path
        else:
            workflow["prompt"][node_id]["inputs"]["unet_name"] = base_path

    return workflow

def replace_prompt(workflow: dict, prompt_text: str, negative_prompt: str = "") -> dict:
    """
    ✅ 修复版：精准替换工作流中的正向/负向提示词
    
    识别规则（针对 Z-Image 文生图工作流）：
      正向节点：CLIPTextEncode 且 _meta.title == "正向"
      负向节点：CLIPTextEncode 且 _meta.title != "正向"（即 title="CLIP文本编码"）
    
    图生图工作流（Qwen）：
      TextEncodeQwenImageEditPlus 且 title="正向" 或 prompt="123444"
    """
    nodes = workflow.get("prompt", workflow)

    for node_id, node in nodes.items():
        class_type = node.get("class_type", "")
        meta       = node.get("_meta", {})
        title      = meta.get("title", "")
        inputs     = node.get("inputs", {})

        # ── 文生图：CLIPTextEncode 节点 ─────────────────────────────────────
        if class_type == "CLIPTextEncode":
            if title == "正向":
                # ✅ 核心修复：用 title 精准定位正向节点，直接覆盖（不再判断是否为空）
                nodes[node_id]["inputs"]["text"] = prompt_text
            else:
                # 负向节点：有传入负面提示词才替换，否则保留工作流默认值
                if negative_prompt:
                    nodes[node_id]["inputs"]["text"] = negative_prompt

        # ── 图生图：Qwen 图像编辑节点 ────────────────────────────────────────
        elif class_type == "TextEncodeQwenImageEditPlus":
            if title == "正向" or inputs.get("prompt") == "123444":
                nodes[node_id]["inputs"]["prompt"] = prompt_text

    return workflow

def replace_seed(workflow: dict, seed_mode: str, seed_value: int = None):
    """
    替换工作流中所有种子参数。
    返回：(修改后的 workflow, 最终使用的 seed 值)
    """
    global FIXED_SEED

    if seed_mode == "specify":
        final_seed = seed_value
        FIXED_SEED = final_seed
    elif seed_mode == "fixed":
        if FIXED_SEED is None:
            FIXED_SEED = random.randint(1, 999_999_999_999)
        final_seed = FIXED_SEED
    else:  # random
        final_seed = random.randint(1, 999_999_999_999)
        FIXED_SEED = None

    for seed_param in Config.SEED_PARAM_NAMES:
        for node_id, node in workflow["prompt"].items():
            if seed_param in node.get("inputs", {}):
                workflow["prompt"][node_id]["inputs"][seed_param] = final_seed

    return workflow, final_seed

def replace_resolution(workflow: dict, width: int, height: int) -> dict:
    """替换工作流中 EmptyLatentImage 节点的宽高"""
    for node_id, node in workflow["prompt"].items():
        if node.get("class_type") == "EmptyLatentImage":
            workflow["prompt"][node_id]["inputs"]["width"]  = width
            workflow["prompt"][node_id]["inputs"]["height"] = height
    return workflow

def upload_image_to_comfyui(image_file: UploadFile) -> str:
    """将前端上传的图片转发至 ComfyUI，返回云端文件名"""
    image_file.file.seek(0)
    file_bytes = image_file.file.read()
    files = {
        "image": (
            image_file.filename or "upload.png",
            file_bytes,
            image_file.content_type or "image/png",
        )
    }
    resp = requests.post(Config.COMFYUI_UPLOAD_URL, files=files, timeout=60)
    if resp.status_code == 200:
        return resp.json().get("name")
    raise Exception(f"图片上传失败 {resp.status_code}：{resp.text}")

def run_comfyui_workflow(workflow: dict) -> dict:
    """
    提交工作流到 ComfyUI 并轮询等待完成。
    返回：{"filename": str, "subfolder": str}
    """
    prompt_id = str(uuid.uuid4())
    payload = {
        "prompt_id": prompt_id,
        "prompt":    workflow["prompt"],
        "client_id": "comfyapi",
    }

    resp = requests.post(Config.COMFYUI_PROMPT_URL, json=payload, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"提交工作流失败 {resp.status_code}：{resp.text}")

    # 轮询历史记录，最长等待 5 分钟
    deadline = time.time() + 300
    while time.time() < deadline:
        hist_resp = requests.get(
            f"{Config.COMFYUI_HISTORY_URL}/{prompt_id}", timeout=10
        )
        if hist_resp.status_code == 200:
            history = hist_resp.json()
            if prompt_id in history and "outputs" in history[prompt_id]:
                for node_output in history[prompt_id]["outputs"].values():
                    if "images" in node_output:
                        img_info = node_output["images"][0]
                        return {
                            "filename":  img_info["filename"],
                            "subfolder": img_info.get("subfolder", ""),
                        }
        time.sleep(2)

    raise TimeoutError("生成超时（超过 5 分钟）")

# =============================================================================
# 3. 指令解析
# =============================================================================

def parse_user_command(command: str) -> dict:
    """
    解析前端构造的指令字符串，格式：
      文生图：<提示词>|base=1,turbo=2,种子随机,分辨率：1080x1920
      图生图：<提示词>|种子固定
    """
    command = command.strip()
    result = {
        "type":           "chat",
        "prompt":         "",
        "base_model_id":  1,
        "turbo_model_id": 1,
        "seed_mode":      "random",
        "seed_value":     None,
        "width":          1080,
        "height":         1920,
        "error":          "",
    }

    if not (command.startswith("文生图：") or command.startswith("图生图：")):
        return result

    result["type"] = "text2img" if command.startswith("文生图：") else "img2img"
    content = command.replace("文生图：", "").replace("图生图：", "").strip()

    prompt_part, param_part = content, ""
    if "|" in content:
        prompt_part, param_part = content.split("|", 1)
        prompt_part = prompt_part.strip()
        param_part  = param_part.strip()

    result["prompt"] = prompt_part

    if param_part:
        param_part = param_part.replace("，", ",").replace("模型：", "")
        for param in param_part.split(","):
            param = param.strip()
            if param.startswith("base="):
                try:
                    result["base_model_id"] = int(param[5:])
                except ValueError:
                    result["error"] = "base 模型ID 必须是数字（1-3）"
            elif param.startswith("turbo="):
                try:
                    result["turbo_model_id"] = int(param[6:])
                except ValueError:
                    result["error"] = "turbo 模型ID 必须是数字（1-4）"
            elif param.startswith("种子："):
                try:
                    result["seed_mode"]  = "specify"
                    result["seed_value"] = int(param[3:])
                except ValueError:
                    result["error"] = "种子必须是整数（如：种子：123456）"
            elif param == "种子固定":
                result["seed_mode"] = "fixed"
            elif param == "种子随机":
                result["seed_mode"] = "random"
            elif param.startswith("分辨率："):
                try:
                    w, h = param[4:].split("x")
                    result["width"], result["height"] = int(w), int(h)
                    if result["width"] % 2 or result["height"] % 2:
                        result["error"] = "分辨率宽高必须为偶数"
                except Exception:
                    result["error"] = "分辨率格式错误（示例：分辨率：1080x1920）"

    if result["base_model_id"] not in Config.Z_IMAGE_BASE_MODELS:
        result["error"] = "base 模型ID 超出范围（1-3）"
    if result["turbo_model_id"] not in Config.Z_IMAGE_TURBO_MODELS:
        result["error"] = "turbo 模型ID 超出范围（1-4）"

    return result

# =============================================================================
# 4. Agent 核心处理
# =============================================================================

def agent_handle(command: str, negative_prompt: str = "", image_file: Optional[UploadFile] = None) -> dict:
    """解析指令 → 修改工作流 → 调用 ComfyUI → 构造代理图片 URL → 返回结果"""
    parsed = parse_user_command(command)
    if parsed["error"]:
        return {"status": "error", "message": parsed["error"]}

    try:
        # ── 1. 加载工作流 ──────────────────────────────────────────────────────
        if parsed["type"] == "text2img":
            workflow = load_workflow("z_image")
            workflow = replace_z_image_model(
                workflow, parsed["base_model_id"], parsed["turbo_model_id"]
            )
        elif parsed["type"] == "img2img":
            workflow = load_workflow("qwen_edit")
        else:
            return {"status": "error", "message": "不支持的指令类型"}

        # ── 2. 替换提示词（含负面提示词）/ 种子 / 分辨率 ──────────────────────
        # ✅ 将前端传入的 negative_prompt 透传进去
        workflow = replace_prompt(workflow, parsed["prompt"], negative_prompt)
        workflow, final_seed = replace_seed(
            workflow, parsed["seed_mode"], parsed["seed_value"]
        )
        if parsed["type"] == "text2img":
            workflow = replace_resolution(workflow, parsed["width"], parsed["height"])

        # ── 3. 图生图：上传参考图并注入 LoadImage 节点 ─────────────────────────
        if parsed["type"] == "img2img":
            if not image_file:
                return {"status": "error", "message": "图生图模式必须上传图片"}
            uploaded_name = upload_image_to_comfyui(image_file)
            for node_id, node in workflow["prompt"].items():
                if node.get("class_type") == "LoadImage":
                    workflow["prompt"][node_id]["inputs"]["image"] = uploaded_name

        # ── 4. 提交工作流，等待生图完成 ────────────────────────────────────────
        img_info  = run_comfyui_workflow(workflow)
        img_name  = img_info["filename"]
        subfolder = img_info["subfolder"]

        # ── 5. 构造云端文件 URL ────────────────────────────────────────────────
        base_cloud_url = (
            f"{Config.JUPYTER_URL.rstrip('/')}/jupyter/files/{Config.COMFYUI_OUTPUT_DIR}"
        )
        if subfolder:
            target_url = f"{base_cloud_url}/{subfolder}/{img_name}?_xsrf={Config.XSRF_TOKEN}"
        else:
            target_url = f"{base_cloud_url}/{img_name}?_xsrf={Config.XSRF_TOKEN}"

        # ── 6. 代理 URL（前端展示用） ───────────────────────────────────────────
        preview_url = f"{Config.BACKEND_HOST}/proxy-image?url={quote(target_url)}"

        # ── 7. 构造返回消息 ────────────────────────────────────────────────────
        seed_tips = f"种子：{final_seed}（模式：{parsed['seed_mode']}）"
        if parsed["type"] == "text2img":
            base_name  = Config.Z_IMAGE_BASE_MODELS[parsed["base_model_id"]].split("/")[-1]
            turbo_name = Config.Z_IMAGE_TURBO_MODELS[parsed["turbo_model_id"]].split("/")[-1]
            seed_tips += f"\n生成模型：base={base_name} | turbo={turbo_name}"

        return {
            "status":      "success",
            "message":     f"✅ 生成成功！\n{seed_tips}",
            "preview_url": preview_url,
            "seed":        final_seed,
            "seed_mode":   parsed["seed_mode"],
        }

    except Exception as e:
        return {"status": "error", "message": f"❌ 生成失败：{str(e)}"}

# =============================================================================
# 5. FastAPI 路由
# =============================================================================

app = FastAPI(title="ComfyUI Agent", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/")
async def generate(
    command:         str                   = Form(...),
    negative_prompt: str                   = Form(""),
    image_file:      Optional[UploadFile]  = File(None),
):
    """
    主入口：前端 POST 到根路径。
    multipart/form-data 字段：
      - command          : 指令字符串（必填）
      - negative_prompt  : 负面提示词（选填，文生图有效）
      - image_file       : 图生图参考图（选填）
    """
    result = agent_handle(command, negative_prompt, image_file)
    return result

@app.get("/workflow/negative-prompt")
async def get_negative_prompt():
    """
    读取接口：前端初始化时调用，从工作流 JSON 中读取当前负面提示词，显示在页面上。
    """
    try:
        workflow = load_workflow("z_image")
        nodes = workflow["prompt"]
        for node_id, node in nodes.items():
            # 负向节点特征：CLIPTextEncode 且 title 不是"正向"
            if (
                node.get("class_type") == "CLIPTextEncode"
                and node.get("_meta", {}).get("title") != "正向"
            ):
                return {
                    "status":          "success",
                    "negative_prompt": node["inputs"].get("text", ""),
                }
        return {"status": "success", "negative_prompt": ""}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/workflow/negative-prompt")
async def save_negative_prompt(data: dict):
    """
    保存接口：用户点击"保存"按钮时调用，将负面提示词写回工作流 JSON 文件。
    请求体 JSON：{"negative_prompt": "..."}
    """
    try:
        negative_prompt = data.get("negative_prompt", "").strip()
        workflow = load_workflow("z_image")
        nodes = workflow["prompt"]

        saved = False
        for node_id, node in nodes.items():
            if (
                node.get("class_type") == "CLIPTextEncode"
                and node.get("_meta", {}).get("title") != "正向"
            ):
                nodes[node_id]["inputs"]["text"] = negative_prompt
                saved = True

        if not saved:
            return {"status": "error", "message": "未找到负向提示词节点"}

        save_workflow("z_image", workflow)
        return {"status": "success", "message": "✅ 负面提示词已保存到工作流文件"}
    except Exception as e:
        return {"status": "error", "message": f"保存失败：{str(e)}"}

@app.get("/proxy-image")
async def proxy_image(url: str):
    """
    图片代理路由：后端携带 Cookie 向 AutoDL Jupyter 发起下载，
    将原始图片字节流原封不动（含原始文件名）返回给前端。
    """
    target_url = unquote(url)
    headers = {
        "Cookie":     Config.JUPYTER_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":    Config.JUPYTER_URL,
    }
    try:
        resp = requests.get(target_url, headers=headers, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/png")
        filename = os.path.basename(urlparse(target_url).path) or "image.png"
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except Exception as e:
        return Response(content=f"图片代理失败：{str(e)}", status_code=500)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "ComfyUI Agent 运行正常"}

# =============================================================================
# 6. 启动入口
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "comfyapi:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )