"""
AstrBot Emotion Sign Plugin v15
- 依赖自动安装兜底（Pillow / aiohttp）
- WebUI 配置支持（_conf_schema.json）
- data 目录渲染图片每 7 天自动清理（可配置）
"""

import os
import sys
import time
import random
import json
import asyncio
import importlib
import subprocess
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger
import astrbot.api.message_components as Comp

try:
    from astrbot.api import AstrBotConfig
except Exception:  # 兼容旧版本 AstrBot
    AstrBotConfig = None


def _ensure_dependency(module_name: str, package_name: str = ""):
    """确保第三方依赖可用，缺失时自动调用 pip 安装（兜底机制）。

    AstrBot 在加载插件时会按 requirements.txt 自动安装依赖，
    此处作为个别环境下自动安装失败的兜底方案。
    """
    try:
        return importlib.import_module(module_name)
    except ImportError:
        pkg = package_name or module_name
        logger.info("[EmotionSign] 检测到缺少依赖: " + pkg + "，正在自动安装...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("[EmotionSign] 依赖安装成功: " + pkg)
            return importlib.import_module(module_name)
        except Exception as e:
            logger.error("[EmotionSign] 依赖 " + pkg + " 自动安装失败: " + str(e))
            raise


# 依赖兜底：正常情况下 AstrBot 已按 requirements.txt 安装，这里仅作保险
_ensure_dependency("PIL", "Pillow")
_ensure_dependency("aiohttp")

from PIL import Image, ImageDraw, ImageFont
import aiohttp


DEFAULT_CONFIG = {
    "generate_probability": 0.3,
    "image_provider": "pillow",
    "api_url": "",
    "api_key": "",
    "font_path": "",
    "max_text_length": 15,
    "enable": True,
    "debug": False,
    "upscale": 2,
    "cleanup_enable": True,
    "cleanup_days": 7,
}


@dataclass
class EmotionConfig:
    id: int
    name: str
    keywords: List[str]
    image_file: str
    font_color: tuple
    font_size: int
    rel_text_area: Tuple[float, float, float, float]
    max_chars_per_line: int = 6


EMOTION_CONFIGS = [
    EmotionConfig(id=1, name="安逸、宁静、困倦、柔和", keywords=["安逸","宁静","困","柔和","放松","舒服","晚安","好梦","安静","温柔","慵懒"], image_file="image.png", font_color=(50,50,70), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=2, name="无情感，冷漠", keywords=["冷漠","无感","平淡","随便","嗯","哦","好吧","无所谓","冷淡","平静"], image_file="image(1).png", font_color=(30,30,50), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=3, name="开心、甜美、温柔、愉悦", keywords=["开心","高兴","快乐","甜","温柔","愉悦","喜欢","爱你","嘻嘻","哈哈","好耶","棒","可爱"], image_file="image(2).png", font_color=(70,30,50), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=4, name="愤怒，生气", keywords=["生气","愤怒","讨厌","烦","滚","可恶","恨","气死","暴躁","火大"], image_file="image(3).png", font_color=(90,10,10), font_size=38, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=5, name="难受，痛苦", keywords=["难受","痛苦","疼","伤心","心痛","折磨","煎熬","苦","好累","崩溃"], image_file="image(4).png", font_color=(70,20,40), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=6, name="脸红，害羞", keywords=["害羞","脸红","羞","不好意思","尴尬","腼腆","怯","紧张","心跳"], image_file="image(5).png", font_color=(90,30,40), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=7, name="哭泣，悲伤，难过", keywords=["哭","泪","悲伤","难过","伤心","呜","呜呜","好惨","心碎","绝望"], image_file="image(6).png", font_color=(50,40,60), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=8, name="惊讶，不可思议的", keywords=["惊讶","惊","啊","哇","不可思议","震惊","不会吧","真的吗","天哪","omg"], image_file="image(7).png", font_color=(50,40,70), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=9, name="激动，兴奋", keywords=["激动","兴奋","太棒了","好耶","冲","燃","热血","期待","迫不及待"], image_file="image(8).png", font_color=(70,20,50), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=10, name="害怕，恐惧", keywords=["怕","恐惧","吓","恐怖","不敢","退缩","怂","惊慌","瑟瑟发抖"], image_file="image(9).png", font_color=(40,30,60), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=11, name="无语", keywords=["无语","无奈","服了","沉默","呃","汗","囧","无语了","无话可说"], image_file="image(10).png", font_color=(40,40,60), font_size=36, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
    EmotionConfig(id=12, name="病娇，黑化", keywords=["病娇","黑化","坏","疯","扭曲","独占","不许","永远","只属于","黑暗"], image_file="image(11).png", font_color=(30,10,30), font_size=38, rel_text_area=(0.20, 0.70, 0.80, 0.94)),
]

# 清理检查间隔（秒）：每天检查一次
_CLEANUP_INTERVAL = 24 * 3600
# data 目录中渲染产物的文件名前缀
_OUTPUT_PREFIXES = ("output_", "api_output_")
_OUTPUT_SUFFIXES = (".png", ".jpg", ".jpeg")


class EmotionSignPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.context = context
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.plugin_dir, "data")
        self.images_dir = os.path.join(self.plugin_dir, "images")
        self.fonts_dir = os.path.join(self.plugin_dir, "fonts")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.fonts_dir, exist_ok=True)
        self._font_cache: Dict[str, ImageFont.FreeTypeFont] = {}
        self._image_size_cache: Dict[str, Tuple[int, int]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

        # 配置来源：优先使用 AstrBot WebUI 配置（_conf_schema.json），
        # 旧版本 AstrBot 或不支持 schema 时回退到插件目录下的 data/config.json
        if config is not None:
            self._schema_config = True
            self._migrate_legacy_config(config)
            self.config = config
        else:
            self._schema_config = False
            self.config = self._load_config()

        # 启动时立即清理一次过期渲染图片
        self._cleanup_outputs()

        # 启动后台定时清理任务（每 24 小时检查一次，删除超过保留天数的渲染图片）
        try:
            loop = asyncio.get_event_loop()
            self._cleanup_task = loop.create_task(self._cleanup_loop())
        except Exception as e:
            logger.warning("[EmotionSign] 清理任务启动失败: " + str(e))

        logger.info("[EmotionSign] v15 Plugin loaded (auto-deps, webui-config, auto-cleanup)")
        logger.info("[EmotionSign] Images dir: " + self.images_dir)
        logger.info("[EmotionSign] Probability: " + str(self.config.get("generate_probability", 0.3)))
        logger.info("[EmotionSign] Cleanup: " + ("On, keep " + str(self.config.get("cleanup_days", 7)) + " days" if self.config.get("cleanup_enable", True) else "Off"))

    # ------------------------------------------------------------------
    # 配置读写
    # ------------------------------------------------------------------
    def _migrate_legacy_config(self, config):
        """将旧版插件目录 data/config.json 中的非默认配置迁移到 WebUI 配置。"""
        legacy_path = os.path.join(self.data_dir, "config.json")
        if not os.path.exists(legacy_path):
            return
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            migrated = False
            for key, value in legacy.items():
                # 仅当 schema 配置仍为默认值且旧配置有自定义值时才迁移，避免覆盖 WebUI 中已保存的配置
                if key in DEFAULT_CONFIG and key in config:
                    if config.get(key) == DEFAULT_CONFIG[key] and value != DEFAULT_CONFIG[key]:
                        config[key] = value
                        migrated = True
            if migrated and hasattr(config, "save_config"):
                config.save_config()
                logger.info("[EmotionSign] 已从旧版 data/config.json 迁移自定义配置")
        except Exception as e:
            logger.warning("[EmotionSign] 旧版配置迁移失败: " + str(e))

    def _load_config(self) -> dict:
        config_path = os.path.join(self.data_dir, "config.json")
        default_config = dict(DEFAULT_CONFIG)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in default_config.items():
                    if k not in saved:
                        saved[k] = v
                return saved
            except Exception as e:
                logger.error("[EmotionSign] Load config failed: " + str(e))
        self._save_config(default_config)
        return default_config

    def _save_config(self, config: dict):
        # WebUI（schema）模式下保存到 AstrBot 配置目录
        if self._schema_config and hasattr(config, "save_config"):
            try:
                config.save_config()
                return
            except Exception as e:
                logger.error("[EmotionSign] Save config failed (schema): " + str(e))
                return
        # 旧版模式：保存到插件目录 data/config.json
        config_path = os.path.join(self.data_dir, "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("[EmotionSign] Save config failed: " + str(e))

    # ------------------------------------------------------------------
    # 渲染图片自动清理
    # ------------------------------------------------------------------
    def _cleanup_outputs(self):
        """删除 data 目录中超过保留天数的渲染产物（output_*.png / api_output_*.png）。"""
        if not self.config.get("cleanup_enable", True):
            return
        try:
            days = int(self.config.get("cleanup_days", 7))
        except Exception:
            days = 7
        if days < 0:
            return
        now = time.time()
        removed = 0
        try:
            for fname in os.listdir(self.data_dir):
                if not fname.startswith(_OUTPUT_PREFIXES):
                    continue
                if not fname.lower().endswith(_OUTPUT_SUFFIXES):
                    continue
                fpath = os.path.join(self.data_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    if now - os.path.getmtime(fpath) > days * 86400:
                        os.remove(fpath)
                        removed += 1
                except Exception as e:
                    logger.warning("[EmotionSign] 清理文件失败 " + fname + ": " + str(e))
        except Exception as e:
            logger.error("[EmotionSign] 清理渲染图片失败: " + str(e))
        if removed:
            logger.info("[EmotionSign] 已自动清理 " + str(removed) + " 张超过 " + str(days) + " 天的渲染图片")

    async def _cleanup_loop(self):
        """后台定时清理协程：每天检查一次，删除过期渲染图片。"""
        while True:
            try:
                await asyncio.sleep(_CLEANUP_INTERVAL)
                self._cleanup_outputs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[EmotionSign] 定时清理异常: " + str(e))

    # ------------------------------------------------------------------
    # 字体与素材
    # ------------------------------------------------------------------
    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        cache_key = str(size)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]
        if self.config.get("font_path") and os.path.exists(self.config["font_path"]):
            try:
                font = ImageFont.truetype(self.config["font_path"], size)
                self._font_cache[cache_key] = font
                logger.info("[EmotionSign] Using custom font: " + self.config["font_path"])
                return font
            except Exception as e:
                logger.warning("[EmotionSign] Custom font failed: " + str(e))
        font_candidates = [
            os.path.join(self.fonts_dir, "msyh.ttc"),
            "C:/Windows/Fonts/STXINGKA.TTF",
            "C:/Windows/Fonts/STHUPO.TTF",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, size)
                    self._font_cache[cache_key] = font
                    logger.info("[EmotionSign] Using font: " + font_path)
                    return font
                except Exception:
                    continue
        font = ImageFont.load_default()
        self._font_cache[cache_key] = font
        logger.warning("[EmotionSign] Using default font (may not support Chinese)")
        return font

    def _get_image_size(self, image_file: str) -> Tuple[int, int]:
        if image_file in self._image_size_cache:
            return self._image_size_cache[image_file]
        image_path = os.path.join(self.images_dir, image_file)
        if os.path.exists(image_path):
            img = Image.open(image_path)
            size = img.size
            self._image_size_cache[image_file] = size
            return size
        return (541, 648)

    def _analyze_emotion(self, text: str) -> EmotionConfig:
        text_lower = text.lower()
        scores = []
        for emotion in EMOTION_CONFIGS:
            score = 0
            for keyword in emotion.keywords:
                if keyword in text_lower:
                    score += len(keyword)
            scores.append((emotion, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        if scores[0][1] > 0:
            return scores[0][0]
        if "?" in text or "?" in text:
            return EMOTION_CONFIGS[7]
        elif "!" in text or "!" in text:
            return EMOTION_CONFIGS[8]
        elif "..." in text or "..." in text:
            return EMOTION_CONFIGS[10]
        elif len(text) <= 5 and ("嗯" in text or "哦" in text):
            return EMOTION_CONFIGS[1]
        return EMOTION_CONFIGS[0]

    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        lines = []
        current_line = ""
        for char in text:
            if len(current_line) >= max_chars:
                lines.append(current_line)
                current_line = char
            else:
                current_line += char
        if current_line:
            lines.append(current_line)
        return lines

    def _generate_image_pillow(self, text: str, emotion: EmotionConfig) -> str:
        image_path = os.path.join(self.images_dir, emotion.image_file)
        if not os.path.exists(image_path):
            logger.error("[EmotionSign] Image not found: " + image_path)
            raise FileNotFoundError("Image not found: " + emotion.image_file)

        upscale = self.config.get("upscale", 4)
        if upscale < 1:
            upscale = 1
        if upscale > 4:
            upscale = 4

        base_img = Image.open(image_path).convert("RGBA")
        orig_width, orig_height = base_img.size

        # Upscale template
        work_width = orig_width * upscale
        work_height = orig_height * upscale
        work_img = base_img.resize((work_width, work_height), Image.LANCZOS)

        # Calculate text area on work resolution
        rx1, ry1, rx2, ry2 = emotion.rel_text_area
        x1 = int(work_width * rx1)
        y1 = int(work_height * ry1)
        x2 = int(work_width * rx2)
        y2 = int(work_height * ry2)

        area_width = x2 - x1
        area_height = y2 - y1

        scale_factor = work_width / orig_width

        # Auto-fit font size with stricter constraints
        base_font_size = int(emotion.font_size * scale_factor)
        max_chars = emotion.max_chars_per_line

        def try_font_size(size: int):
            font = self._get_font(size)
            lines = self._wrap_text(text, max_chars)

            line_heights = []
            line_widths = []
            for line in lines:
                try:
                    bbox = font.getbbox(line)
                    if bbox:
                        line_widths.append(bbox[2] - bbox[0])
                        line_heights.append(bbox[3] - bbox[1])
                    else:
                        line_widths.append(len(line) * size * 0.6)
                        line_heights.append(size)
                except Exception:
                    line_widths.append(len(line) * size * 0.6)
                    line_heights.append(size)

            max_line_width = max(line_widths) if line_widths else 0
            total_text_height = sum(line_heights) + (len(lines) - 1) * int(size * 0.3)
            return font, lines, line_widths, line_heights, max_line_width, total_text_height

        # Stricter margins (20% padding) to keep text well inside sketchbook
        best_size = max(base_font_size // 4, 12)
        low, high = best_size, base_font_size
        best_result = None

        while low <= high:
            mid = (low + high) // 2
            font, lines, line_widths, line_heights, max_line_width, total_text_height = try_font_size(mid)

            margin_w = int(area_width * 0.20)
            margin_h = int(area_height * 0.20)

            if max_line_width <= (area_width - margin_w) and total_text_height <= (area_height - margin_h):
                best_size = mid
                best_result = (font, lines, line_widths, line_heights, max_line_width, total_text_height)
                low = mid + 1
            else:
                high = mid - 1

        if best_result:
            font, lines, line_widths, line_heights, max_line_width, total_text_height = best_result
        else:
            font, lines, line_widths, line_heights, max_line_width, total_text_height = try_font_size(best_size)

        if best_size < base_font_size:
            logger.info("[EmotionSign] Auto-shrunk font: " + str(base_font_size) + " -> " + str(best_size))

        start_x_base = x1 + (area_width - max_line_width) // 2
        start_y_base = y1 + (area_height - total_text_height) // 2

        draw = ImageDraw.Draw(work_img)

        current_y = start_y_base
        for i, line in enumerate(lines):
            line_width = line_widths[i]
            line_height = line_heights[i]
            start_x = x1 + (area_width - line_width) // 2

            # Clean text, no shadow
            draw.text((start_x, current_y), line, font=font, fill=emotion.font_color)

            current_y += line_height + int(best_size * 0.3)

        # Keep upscaled size
        result_rgb = work_img.convert("RGB")

        output_path = os.path.join(self.data_dir, "output_" + str(random.randint(10000, 99999)) + ".png")
        result_rgb.save(output_path, "PNG", quality=95)

        logger.info("[EmotionSign] Generated: " + output_path + " size=" + str(work_width) + "x" + str(work_height) + " text=" + repr(text) + " lines=" + str(len(lines)) + " font=" + str(best_size) + "/" + str(base_font_size) + " upscale=" + str(upscale))
        return output_path

    async def _generate_image_api(self, text: str, emotion: EmotionConfig) -> str:
        api_url = self.config.get("api_url", "")
        api_key = self.config.get("api_key", "")
        if not api_url:
            return self._generate_image_pillow(text, emotion)
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        payload = {"text": text, "emotion": emotion.name, "image_file": emotion.image_file, "font_color": emotion.font_color}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        image_url = data.get("image_url") or data.get("url")
                        if image_url:
                            return image_url
                        image_b64 = data.get("image_base64") or data.get("base64")
                        if image_b64:
                            import base64
                            output_path = os.path.join(self.data_dir, "api_output_" + str(random.randint(10000, 99999)) + ".png")
                            with open(output_path, "wb") as f:
                                f.write(base64.b64decode(image_b64))
                            return output_path
        except Exception as e:
            logger.error("[EmotionSign] API error: " + str(e))
        return self._generate_image_pillow(text, emotion)

    async def _generate_sign_image(self, text: str) -> Optional[str]:
        emotion = self._analyze_emotion(text)
        provider = self.config.get("image_provider", "pillow")
        if provider == "api":
            return await self._generate_image_api(text, emotion)
        else:
            return self._generate_image_pillow(text, emotion)

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        if not self.config.get("enable", True):
            return

        result = event.get_result()
        if not result:
            return

        plain_text = ""
        if hasattr(result, "chain") and result.chain:
            for comp in result.chain:
                if isinstance(comp, Comp.Plain):
                    plain_text += comp.text

        if not plain_text:
            return

        plain_text = plain_text.strip()

        max_len = self.config.get("max_text_length", 15)
        if len(plain_text) > max_len:
            return
        if "\n" in plain_text or "```" in plain_text:
            return

        probability = self.config.get("generate_probability", 0.3)
        if random.random() > probability:
            return

        try:
            image_path = await self._generate_sign_image(plain_text)
            if image_path:
                abs_path = os.path.abspath(image_path)
                if os.name == 'nt':
                    file_url = "file:///" + abs_path.replace("\\", "/")
                else:
                    file_url = "file://" + abs_path

                try:
                    new_chain = [Comp.Image(file=file_url)]
                    result.chain = new_chain
                except Exception:
                    new_chain = [Comp.Image.fromFileSystem(abs_path)]
                    result.chain = new_chain
        except Exception as e:
            logger.error("[EmotionSign] Failed to replace: " + str(e))

    @filter.command_group("emotion_sign")
    def emotion_sign(self):
        pass

    @emotion_sign.command("set_prob")
    async def set_probability(self, event: AstrMessageEvent, prob: float):
        if not 0.0 <= prob <= 1.0:
            yield event.plain_result("Probability must be 0.0-1.0!")
            return
        self.config["generate_probability"] = prob
        self._save_config(self.config)
        yield event.plain_result("Probability set to: " + str(prob))

    @emotion_sign.command("set_provider")
    async def set_provider(self, event: AstrMessageEvent, provider: str):
        if provider not in ("pillow", "api"):
            yield event.plain_result("Provider must be pillow or api!")
            return
        self.config["image_provider"] = provider
        self._save_config(self.config)
        yield event.plain_result("Provider set to: " + provider)

    @emotion_sign.command("set_api")
    async def set_api(self, event: AstrMessageEvent, url: str, key: str = ""):
        self.config["api_url"] = url
        self.config["api_key"] = key
        self._save_config(self.config)
        yield event.plain_result("API set: " + url)

    @emotion_sign.command("set_font")
    async def set_font(self, event: AstrMessageEvent, font_path: str):
        if not os.path.exists(font_path):
            yield event.plain_result("Font not found: " + font_path)
            return
        self.config["font_path"] = font_path
        self._save_config(self.config)
        self._font_cache.clear()
        yield event.plain_result("Font set: " + font_path)

    @emotion_sign.command("set_upscale")
    async def set_upscale(self, event: AstrMessageEvent, factor: int):
        if not 1 <= factor <= 4:
            yield event.plain_result("Upscale factor must be 1-4!")
            return
        self.config["upscale"] = factor
        self._save_config(self.config)
        yield event.plain_result("Upscale factor set to: " + str(factor) + "x")

    @emotion_sign.command("cleanup")
    async def cleanup_now(self, event: AstrMessageEvent):
        """立即清理 data 目录中过期的渲染图片。"""
        before = time.time()
        self._cleanup_outputs()
        yield event.plain_result("Cleanup finished. (清理任务已执行，详见日志)")

    @emotion_sign.command("status")
    async def show_status(self, event: AstrMessageEvent):
        api_key_status = "Set" if self.config.get("api_key") else "Not set"
        enable_status = "On" if self.config.get("enable", True) else "Off"
        debug_status = "On" if self.config.get("debug", False) else "Off"
        upscale = self.config.get("upscale", 2)
        cleanup_status = "On (keep " + str(self.config.get("cleanup_days", 7)) + " days)" if self.config.get("cleanup_enable", True) else "Off"
        status_text = (
            "EmotionSign Config:\n"
            + "Probability: " + str(self.config.get("generate_probability", 0.3)) + "\n"
            + "Provider: " + str(self.config.get("image_provider", "pillow")) + "\n"
            + "API URL: " + (self.config.get("api_url", "Not set") or "Not set") + "\n"
            + "API Key: " + api_key_status + "\n"
            + "Font: " + (self.config.get("font_path", "System default") or "System default") + "\n"
            + "Max Length: " + str(self.config.get("max_text_length", 15)) + "\n"
            + "Upscale: " + str(upscale) + "x\n"
            + "Enabled: " + enable_status + "\n"
            + "Debug: " + debug_status + "\n"
            + "Auto Cleanup: " + cleanup_status
        )
        yield event.plain_result(status_text)

    @emotion_sign.command("toggle")
    async def toggle(self, event: AstrMessageEvent):
        self.config["enable"] = not self.config.get("enable", True)
        self._save_config(self.config)
        status = "enabled" if self.config["enable"] else "disabled"
        yield event.plain_result("Plugin " + status)

    @emotion_sign.command("test")
    async def test_generate(self, event: AstrMessageEvent, text: str):
        if len(text) > self.config.get("max_text_length", 15):
            yield event.plain_result("Too long! Max " + str(self.config.get("max_text_length", 15)) + " chars")
            return
        try:
            image_path = await self._generate_sign_image(text)
            if image_path:
                abs_path = os.path.abspath(image_path)
                if os.name == 'nt':
                    file_url = "file:///" + abs_path.replace("\\", "/")
                else:
                    file_url = "file://" + abs_path
                try:
                    chain = [Comp.Image(file=file_url)]
                    yield event.chain_result(chain)
                except Exception:
                    chain = [Comp.Image.fromFileSystem(abs_path)]
                    yield event.chain_result(chain)
            else:
                yield event.plain_result("Failed")
        except Exception as e:
            logger.error("[EmotionSign] Test failed: " + str(e))
            yield event.plain_result("Error: " + str(e))

    @emotion_sign.command("list_emotions")
    async def list_emotions(self, event: AstrMessageEvent):
        text = "Emotion Types:\n"
        for emotion in EMOTION_CONFIGS:
            text += str(emotion.id) + ". " + emotion.name + "\n"
        yield event.plain_result(text)

    async def terminate(self):
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except BaseException:
                pass
        logger.info("[EmotionSign] Plugin unloaded")
