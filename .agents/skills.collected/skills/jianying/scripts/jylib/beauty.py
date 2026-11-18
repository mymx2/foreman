"""人像美化（materials.effects[type=figure]）材质生成。

字段与资源 ID 来自 capcut-mate 的 `beauty_meta.py` / `add_beauty.py` 文档，
其元数据已与剪映真实导出草稿逐条核对。这里只生成草稿材质，不做人脸检测；
强度按剪映滑杆 0..100 输入，写入时按 100（肤色冷暖按 99）归一。
"""

from __future__ import annotations

import uuid
from typing import Any

from .errors import SkillError

GROUP_SKIN = "skin"
GROUP_SHAPE = "shape"
GROUP_MAKEUP = "makeup"
GROUP_BODY = "body"
GROUPS = (GROUP_SKIN, GROUP_SHAPE, GROUP_MAKEUP, GROUP_BODY)
ALL_FACES = "-1"

SKIN_TONE_PRESETS = {
    "冷白": {"resource_id": "7148720872105185800"},
    "暖白": {"resource_id": "7148720647714116132"},
}

# name: (中文名, resource_id, 落点, intensity_key, category_id, sub_type, 需要算法路径)
_SLIDERS = {
    GROUP_SKIN: {
        "even": ("匀肤", "7106322605304451614", "adjust_param", "face_adjust_yunfu", "auto-beauty2", "auto_beauty", True),
        "plump": ("丰盈", "7165761391037518350", "adjust_param", "face_adjust_fuling", "auto-beauty2", "auto_beauty", True),
        "smooth": ("磨皮", "6976822940608238093", "value", "", "auto-beauty2", "auto_beauty", True),
        "dewrinkle": ("祛法令纹", "7127560078508429831", "adjust_param", "face_adjust_NasolabialFolds", "auto-beauty2", "auto_beauty", True),
        "bright_eye": ("亮眼", "7210363411970921017", "adjust_param", "face_adjust_BrightEye", "auto-beauty2", "auto_beauty", True),
        "dark_circle": ("祛黑眼圈", "7127559798861599268", "adjust_param", "face_adjust_Pouch", "auto-beauty2", "auto_beauty", True),
        "whitening": ("美白", "6998408303826965006", "value", "", "auto-beauty2", "none", False),
        "white_teeth": ("白牙", "6998408263892996639", "adjust_param", "face_adjust_WhiteTeeth", "auto-beauty2", "auto_beauty", True),
    },
    GROUP_SHAPE: {
        "small_face": ("小脸", "7325345220688613914", "adjust_param", "face_adjust_YouTaiFace", "auto-beauty", "auto_beauty", True),
        "slim": ("瘦脸", "7126765507457323557", "adjust_param", "face_adjust_TotalFace", "auto-beauty", "auto_beauty", True),
        "v_shape": ("V脸", "7358087335411454501", "adjust_param", "face_adjust_VFace", "auto-beauty", "auto_beauty", True),
        "jaw": ("下颌骨", "7126764917918536199", "adjust_param", "face_adjust_ZoomJawbone", "auto-beauty", "auto_beauty", True),
        "cheekbone": ("颧骨", "7127587811795931662", "adjust_param", "face_adjust_ZoomCheekbone", "auto-beauty", "auto_beauty", True),
        "shorten": ("短脸", "7126865570653278751", "adjust_param", "face_adjust_SmallFace", "auto-beauty", "auto_beauty", True),
        "contour_smooth": ("流畅脸", "7165761469231927838", "adjust_param", "face_adjust_lunkuopinghua", "auto-beauty", "auto_beauty", True),
        "lower": ("下庭", "7130850220891443725", "adjust_param", "face_adjust_lower_atrium", "auto-beauty", "auto_beauty", True),
        "middle": ("中庭", "7130850182488396325", "adjust_param", "face_adjust_mid_atrium", "auto-beauty", "auto_beauty", True),
        "upper": ("上庭", "7130849819957924389", "adjust_param", "face_adjust_upper_atrium", "auto-beauty", "auto_beauty", True),
        "hairline": ("发际线", "7126865429154238984", "adjust_param", "face_adjust_Forehead", "auto-beauty", "auto_beauty", True),
        "width": ("窄脸", "", "adjust_param", "", "auto-beauty", "auto_beauty", True),
        "chin_length": ("下巴长短", "", "adjust_param", "", "auto-beauty", "auto_beauty", True),
    },
    GROUP_MAKEUP: {
        "90年代": ("90年代", "7324657002670461450", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "doll感": ("doll感", "7204746549035799077", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "上镜韩妹": ("上镜韩妹", "7210671424225153596", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "中国妆": ("中国妆", "7187309936395686461", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "人形电脑": ("人形电脑", "7202169404975485499", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "元气": ("元气", "7271130195149460023", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "兔兔妆": ("兔兔妆", "7187309936395686456", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "冬日白开水": ("冬日白开水", "7187309936395686437", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "冷感": ("冷感", "7235931216854127160", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "减龄妆": ("减龄妆", "7207729715845534263", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "初恋": ("初恋", "7154258998324105736", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "原生": ("原生", "7348351091118969359", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "古早韩妆": ("古早韩妆", "7304997392086995465", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "夏日桃桃": ("夏日桃桃", "7268611177469448761", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "夏日清透感": ("夏日清透感", "7267081203486822967", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "夏日白开水": ("夏日白开水", "7244820474687918653", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "奶杏": ("奶杏", "7235938046191866424", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "学姐妆": ("学姐妆", "7154258998319911438", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "小烟熏": ("小烟熏", "7154258998324122120", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "小魔女": ("小魔女", "7271129993399243301", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "微醺": ("微醺", "7271129627353944633", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "心动": ("心动", "7196978269260878373", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "拜年妆": ("拜年妆", "7189193298639065656", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "新年开运妆": ("新年开运妆", "7327205752056058408", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "无花果": ("无花果", "7322328321969099302", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "春日樱花妆": ("春日樱花妆", "7366167621227516435", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "柿柿如意": ("柿柿如意", "7189193034200781372", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "橘子汽水": ("橘子汽水", "7391781771496395301", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "氧气感": ("氧气感", "7154258998315717150", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "派对微醺": ("派对微醺", "7309724478756360714", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "淡人妆": ("淡人妆", "7376172391774294554", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "淡妆公式": ("淡妆公式", "7296469047846113802", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "淡盐系": ("淡盐系", "7269610648722477625", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "清透感": ("清透感", "7248523280791900728", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "热红酒": ("热红酒", "7311677923121959475", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "猫系女友": ("猫系女友", "7267827717184164410", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "甜心芭比": ("甜心芭比", "7263035065511187005", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "甜系白开水": ("甜系白开水", "7273756259902296637", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "男友": ("男友", "7200284113964634682", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "男生": ("男生", "7154258998319911460", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "白开水": ("白开水", "7268611445313507877", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "白鹿好运妆": ("白鹿好运妆", "7181374519079080505", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "盐系": ("盐系", "7273756165836640823", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "纯欲蝴蝶兰": ("纯欲蝴蝶兰", "7327202399372710452", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "腮红大法": ("腮红大法", "7226666779211207227", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "芋泥啵啵": ("芋泥啵啵", "7154258998328300046", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "芭蕾少女": ("芭蕾少女", "7223303126919418405", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "英气": ("英气", "7202860622369788471", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "落日": ("落日", "7154258998319911431", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "裸妆": ("裸妆", "7154258998315717157", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "郁金香": ("郁金香", "7231490688204935737", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "雀斑自由": ("雀斑自由", "7154258998319911437", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "韩国学妹": ("韩国学妹", "7154258998324105764", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
        "韩系蜜桃": ("韩系蜜桃", "7241118265613750840", "face_adjust", "face_adjust_whole", "makeup", "exclusion_face", True),
    },
    GROUP_BODY: {
        "small_head": ("小头", "6976812039847023111", "value", "body_adjust_SmallHead", "auto-beauty3", "none", False),
        "swan_neck": ("天鹅颈", "7187453444146336313", "value", "body_adjust_SwanNeck", "auto-beauty3", "none", False),
        "slim_arm": ("瘦手臂", "7187394795965256247", "value", "body_adjust_SlimArm", "auto-beauty3", "none", False),
        "straight_shoulder": ("直角肩", "7246635041663488567", "value", "body_adjust_OrthoShoulder", "auto-beauty3", "none", False),
        "slim_body": ("瘦身", "6976812219048661540", "value", "body_adjust_SlimBody", "auto-beauty3", "none", False),
        "slim_waist": ("瘦腰", "6976812120591569416", "value", "body_adjust_SlimWaist", "auto-beauty3", "none", False),
        "long_leg": ("长腿", "6956089104412971534", "value", "body_adjust_StretchLeg", "auto-beauty3", "none", False),
        "plump_breast": ("丰胸", "7168288902728389157", "value", "body_adjust_SlimBreast", "auto-beauty3", "none", False),
        "slim_hip": ("美胯", "7168289037562679838", "value", "body_adjust_SlimHip", "auto-beauty3", "none", False),
        "smooth": ("磨皮", "7125729150572171812", "value", "", "auto-beauty3", "none", False),
        "whitening": ("美白", "7125780457576206879", "value", "", "auto-beauty3", "none", False),
        "wide_shoulder": ("宽肩", "", "value", "", "auto-beauty3", "none", False),
    },
}

_RESERVED = {"width", "chin_length", "wide_shoulder"}

MAKEUP_EXCLUSION_GROUP = (
    "face_adjust_brow", "face_adjust_eyeshadow", "face_adjust_eyeline",
    "face_adjust_eyelash", "face_adjust_pupil", "face_adjust_eyelight",
    "face_adjust_stereo", "face_adjust_blusher", "face_adjust_lip",
    "face_adjust_mask", "face_adjust_highlight",
)
MAKEUP_ROOT_RESOURCE_ID = "7273096354098844221"


def _number(field, value, *, min_value=0.0, max_value=100.0):
    if isinstance(value, bool):
        raise SkillError(f"{field} 必须是数字", code="VALIDATION",
                         details={"field": field, "value": value})
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SkillError(f"{field} 必须是数字", code="VALIDATION",
                         details={"field": field, "value": value})
    if number < min_value or number > max_value:
        raise SkillError(f"{field} 必须在 {min_value:g}..{max_value:g}",
                         code="VALIDATION", details={"field": field, "value": value})
    return number


def _figure_material(*, resource_id, draft_name, value=0.0, intensity_key="",
                     category_id="", sub_type="auto_beauty",
                     adjust_param=None, face_param=None, cold_warm=None,
                     face_id=ALL_FACES, exclusion_group=(),
                     algorithm_artifact_path="", material_type="figure"):
    uid = str(uuid.uuid4()).upper()
    adjust_params = []
    face_adjust_params = []
    if adjust_param is not None:
        adjust_params = [{"default_value": 0.0, "name": "0", "value": adjust_param}]
        value = 0.0
    if face_param is not None or cold_warm is not None:
        params = []
        if cold_warm is not None:
            params.append({"default_value": 0.0, "name": "face_adjust_skin_ColdWarm",
                           "value": cold_warm})
        if face_param is not None:
            params.append({"default_value": 0.0, "name": intensity_key or "face_adjust_whole",
                           "value": face_param})
        face_adjust_params = [{
            "adjust_params": params, "disable_part": [], "enable": True,
            "face_id": str(face_id),
        }]
        value = 0.0
    return {
        "adjust_params": adjust_params,
        "algorithm_artifact_path": algorithm_artifact_path,
        "apply_target_type": 0,
        "bloom_params": None,
        "category_id": category_id,
        "category_name": "",
        "color_match_info": {"source_feature_path": "", "target_feature_path": "",
                             "target_image_path": ""},
        "effect_id": "",
        "enable_skin_tone_correction": False,
        "exclusion_group": list(exclusion_group),
        "face_adjust_params": face_adjust_params,
        "formula_id": "",
        "id": uid,
        "intensity_key": intensity_key,
        "multi_language_current": "",
        "name": draft_name,
        "panel_id": "",
        "platform": "all",
        "request_id": "",
        "resource_id": resource_id,
        "source_platform": 0,
        "sub_type": sub_type,
        "time_range": None,
        "type": material_type,
        "value": value,
        "version": "",
    }


def _algorithm_path(placeholder_id, video_material_id):
    return (f"##_draftpath_placeholder_{placeholder_id}_##"
            f"/video/figure_algorithm/{video_material_id}")


def build(spec, *, video_material_id, placeholder_id):
    """把一个 segment 的 beauty 规格展开成 figure 材质列表。

    spec: {skin:{...}, shape:{...}, makeup:{...}, body:{...}}。
    0 值不写；预留字段非 0 抛 VALIDATION；未知键也拒绝。
    """
    if not isinstance(spec, dict):
        raise SkillError("beauty 必须是对象 {skin,shape,makeup,body}", code="VALIDATION")
    unknown_groups = [key for key in spec if key not in GROUPS]
    if unknown_groups:
        raise SkillError("beauty 含未知分组", code="VALIDATION",
                         details={"groups": unknown_groups})
    figures = []
    algorithm = _algorithm_path(placeholder_id, video_material_id)
    has_makeup = bool(spec.get(GROUP_MAKEUP))
    for group in GROUPS:
        group_spec = spec.get(group)
        if group_spec is None:
            continue
        if not isinstance(group_spec, dict):
            raise SkillError(f"beauty.{group} 必须是对象", code="VALIDATION")
        catalog = _SLIDERS[group]
        extra_keys = {"skin_tone", "temperature", "intensity"} if group == GROUP_SKIN else (
            {"look", "intensity", "face_id"} if group == GROUP_MAKEUP else set())
        unknown = [key for key in group_spec if key not in catalog and key not in extra_keys]
        if unknown:
            raise SkillError(f"beauty.{group} 含未知字段", code="VALIDATION",
                             details={"fields": unknown})
        for name, meta in catalog.items():
            if name not in group_spec:
                continue
            draft_name, resource_id, mode, intensity_key, category_id, sub_type, needs_path = meta
            value = _number(f"beauty.{group}.{name}", group_spec.get(name))
            if value == 0:
                continue
            if not resource_id or name in _RESERVED:
                raise SkillError(f"beauty.{group}.{name} 暂不支持，必须为 0",
                                 code="VALIDATION",
                                 details={"field": name})
            common = dict(resource_id=resource_id, draft_name=draft_name,
                          intensity_key=intensity_key, category_id=category_id,
                          sub_type=sub_type,
                          algorithm_artifact_path=algorithm if needs_path else "")
            if mode == "value":
                figures.append(_figure_material(value=value / 100.0, **common))
            elif mode == "adjust_param":
                figures.append(_figure_material(adjust_param=value / 100.0, **common))
            else:
                figures.append(_figure_material(face_param=value / 100.0, **common))
        if group == GROUP_SKIN:
            preset = str(group_spec.get("skin_tone") or "").strip()
            if preset:
                if preset not in SKIN_TONE_PRESETS:
                    raise SkillError("skin_tone 只支持 冷白 / 暖白", code="VALIDATION",
                                     details={"value": preset})
                intensity = _number("beauty.skin.intensity",
                                    group_spec.get("intensity", 60))
                temperature = _number("beauty.skin.temperature",
                                      group_spec.get("temperature", 0), max_value=99)
                figures.append(_figure_material(
                    resource_id=SKIN_TONE_PRESETS[preset]["resource_id"],
                    draft_name=preset,
                    intensity_key="face_adjust_skin_Intensity",
                    category_id="auto-beauty2", sub_type="exclusion",
                    face_param=intensity / 100.0,
                    cold_warm=temperature / 99.0,
                    exclusion_group=("face_adjust_skin",)))
        if group == GROUP_MAKEUP:
            look = str(group_spec.get("look") or "").strip()
            if look:
                meta = catalog.get(look)
                if meta is None:
                    raise SkillError("未知美妆套装", code="VALIDATION",
                                     details={"look": look})
                intensity = _number("beauty.makeup.intensity",
                                    group_spec.get("intensity", 80))
                face_id = str(group_spec.get("face_id", ALL_FACES) or ALL_FACES).strip()
                if face_id != ALL_FACES and not face_id.isdigit():
                    raise SkillError("makeup.face_id 必须是 -1 或非负整数",
                                     code="VALIDATION", details={"value": face_id})
                figures.append(_figure_material(
                    resource_id=meta[1], draft_name=look,
                    intensity_key="face_adjust_whole", category_id="makeup",
                    sub_type="exclusion_face", face_param=intensity / 100.0,
                    face_id=face_id, exclusion_group=MAKEUP_EXCLUSION_GROUP,
                    algorithm_artifact_path=algorithm))
    if figures and has_makeup:
        figures.append(_figure_material(
            resource_id=MAKEUP_ROOT_RESOURCE_ID, draft_name="makeup-root",
            category_id="", sub_type="auto_beauty", material_type="makeup_root",
            algorithm_artifact_path=algorithm))
    return figures
