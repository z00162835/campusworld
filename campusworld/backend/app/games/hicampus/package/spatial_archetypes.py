"""
Room archetypes for HiCampus spatial_generate: tags, room_type, and P0 text templates.
"""

from __future__ import annotations

from typing import Any, Dict, List

ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "office": {
        "room_type": "office",
        "tags": ["space:office", "function:work"],
        "name_tpl": "{building} · {floor_label} 开放办公区 {seq}",
        "name_en_tpl": "Open Office {code}",
        "short_tpl": "{floor_label}开放工位与协作位。",
        "desc_tpl": "工位分区清晰，靠窗侧采光良好；白板与储物柜沿墙布置，适合日常研发与站会。",
        "ambiance_tpl": "键盘声与简短讨论交替。",
    },
    "meeting": {
        "room_type": "special",
        "tags": ["space:meeting", "function:collaboration"],
        "name_tpl": "{building} · {floor_label} 会议室 {seq}",
        "name_en_tpl": "Meeting Room {code}",
        "short_tpl": "中小型会议与视频会议空间。",
        "desc_tpl": "会议桌居中，墙面预留投屏接口；隔音门降低走廊干扰，适合评审与对齐。",
        "ambiance_tpl": "投屏提示音与通话回声偶尔可闻。",
    },
    "manager": {
        "room_type": "office",
        "tags": ["space:office", "function:manager", "access:staff"],
        "name_tpl": "{building} · {floor_label} 经理室 {seq}",
        "name_en_tpl": "Manager Office {code}",
        "short_tpl": "独立办公与小型会谈。",
        "desc_tpl": "独立隔间，配小型沙发与书柜；窗外为园区或内院景观，适合一对一沟通。",
        "ambiance_tpl": "相对安静，偶有电话铃。",
    },
    "restroom": {
        "room_type": "normal",
        "tags": ["space:restroom", "function:sanitary", "zone:public"],
        "name_tpl": "{building} · {floor_label} 卫生间 {seq}",
        "name_en_tpl": "Restroom {code}",
        "short_tpl": "公共卫生间。",
        "desc_tpl": "洁具与无障碍设施按标准配置；保洁动线独立，高峰时段需短暂排队。",
        "ambiance_tpl": "排风低频运行。",
    },
    "electrical": {
        "room_type": "special",
        "tags": ["space:electrical", "function:infrastructure", "access:staff"],
        "name_tpl": "{building} · {floor_label} 配电间 {seq}",
        "name_en_tpl": "Electrical Room {code}",
        "short_tpl": "楼层配电与分闸。",
        "desc_tpl": "金属门常闭，内部为配电柜与标签清晰的回路标识；仅授权人员进入维护。",
        "ambiance_tpl": "设备低鸣，温度略高。",
    },
    "monitoring": {
        "room_type": "special",
        "tags": ["space:monitoring", "function:security", "access:staff"],
        "name_tpl": "{building} · {floor_label} 监控室 {seq}",
        "name_en_tpl": "Security Monitoring {code}",
        "short_tpl": "安防与消防值班监视终端。",
        "desc_tpl": "多屏显示公区与出入口画面，与消控策略联动；24 小时或分时值守。",
        "ambiance_tpl": "显示器风扇声与偶尔对讲。",
    },
    "circulation": {
        "room_type": "circulation",
        "tags": ["space:circulation", "zone:public"],
        "name_tpl": "{building} · {floor_label} 交通核 {seq}",
        "name_en_tpl": "Circulation Core {code}",
        "short_tpl": "电梯厅与楼梯间前室。",
        "desc_tpl": "连接垂直交通与走廊；导向标识指向防火分区与疏散楼梯。",
        "ambiance_tpl": "电梯到达提示音与脚步声。",
    },
    "pantry": {
        "room_type": "normal",
        "tags": ["space:pantry", "zone:staff"],
        "name_tpl": "{building} · {floor_label} 茶水间 {seq}",
        "name_en_tpl": "Pantry {code}",
        "short_tpl": "饮水、简餐与微波炉区。",
        "desc_tpl": "台面与洗池便于清洗杯具；冰箱与咖啡机共享使用，高峰略拥挤。",
        "ambiance_tpl": "咖啡机蒸汽与闲聊。",
    },
    "canteen_dining": {
        "room_type": "normal",
        "tags": ["space:dining", "function:canteen", "zone:public"],
        "name_tpl": "{building} · {floor_label} 就餐区 {seq}",
        "name_en_tpl": "Dining Area {code}",
        "short_tpl": "集中就餐与回收动线。",
        "desc_tpl": "餐桌分区布置，收餐口与垃圾分类点就近设置；餐峰人流大、需排队。",
        "ambiance_tpl": "餐盘碰撞声与交谈嘈杂。",
    },
    "kitchen": {
        "room_type": "special",
        "tags": ["space:kitchen", "function:canteen", "access:staff"],
        "name_tpl": "{building} · {floor_label} 备餐间 {seq}",
        "name_en_tpl": "Kitchen Back {code}",
        "short_tpl": "后厨与备餐通道。",
        "desc_tpl": "不锈钢操作台与排烟系统；与就餐区通过传菜口或独立门分隔。",
        "ambiance_tpl": "油烟机与设备运转声。",
    },
    "storage": {
        "room_type": "normal",
        "tags": ["space:storage", "function:logistics"],
        "name_tpl": "{building} · {floor_label} 库房 {seq}",
        "name_en_tpl": "Storage {code}",
        "short_tpl": "杂物与耗材暂存。",
        "desc_tpl": "货架与托盘位，温湿度按物资要求管理；需登记领用。",
        "ambiance_tpl": "安静，偶有推车声。",
    },
    "classroom": {
        "room_type": "classroom",
        "tags": ["space:classroom", "function:training"],
        "name_tpl": "{building} · {floor_label} 教室 {seq}",
        "name_en_tpl": "Classroom {code}",
        "short_tpl": "授课与上机实训。",
        "desc_tpl": "投影或智慧黑板、可移动桌椅；后排插座便于笔记本使用。",
        "ambiance_tpl": "讲课声与键盘练习声。",
    },
    "lab": {
        "room_type": "lab",
        "tags": ["space:lab", "function:research"],
        "name_tpl": "{building} · {floor_label} 实验室 {seq}",
        "name_en_tpl": "Laboratory {code}",
        "short_tpl": "通用实验与测试台位。",
        "desc_tpl": "通风柜与气瓶间分区；安全淋浴与洗眼器按规范布置，入口张贴 MSDS 索引。",
        "ambiance_tpl": "通风设备持续运行。",
    },
    "prep_lab": {
        "room_type": "lab",
        "tags": ["space:lab", "function:prep"],
        "name_tpl": "{building} · {floor_label} 实验准备室 {seq}",
        "name_en_tpl": "Lab Prep {code}",
        "short_tpl": "试剂与样品准备。",
        "desc_tpl": "操作台与冷藏柜；与主实验室通过缓冲间相连，减少交叉污染。",
        "ambiance_tpl": "低温设备间歇启停。",
    },
    "expo_hall": {
        "room_type": "special",
        "tags": ["space:expo", "function:exhibition"],
        "name_tpl": "{building} · {floor_label} 展陈空间 {seq}",
        "name_en_tpl": "Exhibition Space {code}",
        "short_tpl": "临展与活动大空间。",
        "desc_tpl": "可拆装展墙与吊装锚点；地面荷载满足装置与人流集散要求。",
        "ambiance_tpl": "布展期工具声与讲解试音。",
    },
    "av_room": {
        "room_type": "special",
        "tags": ["space:av", "function:events", "access:staff"],
        "name_tpl": "{building} · {floor_label} 音控室 {seq}",
        "name_en_tpl": "AV Control {code}",
        "short_tpl": "灯光音响与播控。",
        "desc_tpl": "机柜与调音台，信号送至展厅扬声器与大屏；活动时专人值守。",
        "ambiance_tpl": "设备散热风扇声。",
    },
    "dorm_unit": {
        "room_type": "normal",
        "tags": ["space:dorm", "function:residential"],
        "name_tpl": "{building} · {floor_label} 公寓单元 {seq}",
        "name_en_tpl": "Dorm Unit {code}",
        "short_tpl": "配套住宿单元。",
        "desc_tpl": "独立卫浴与简易厨台；采光窗朝向内院或慢行系统，强调安静与隐私。",
        "ambiance_tpl": "夜间安静，偶有水声。",
    },
    "lounge": {
        "room_type": "normal",
        "tags": ["space:lounge", "zone:public"],
        "name_tpl": "{building} · {floor_label} 公共休闲区 {seq}",
        "name_en_tpl": "Lounge {code}",
        "short_tpl": "沙发与阅读角。",
        "desc_tpl": "软装配低噪活动区，与走廊用家具软分隔；适合短暂休息与等候。",
        "ambiance_tpl": "背景音乐轻柔。",
    },
}


def merge_tags(building_tags: List[str], floor_tags: List[str], arche_tags: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for t in building_tags + floor_tags + arche_tags:
        s = str(t).strip().lower()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out
