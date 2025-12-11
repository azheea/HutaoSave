"""
UIGF (统一可交换抽卡记录标准) v3.0 导出脚本
从 Userdata.db 中的 gacha_items 表导出数据到 UIGF v3.0 格式的 JSON 文件

UIGF v3.0 标准: https://uigf.org/zh/standards/uigf-legacy-v3.0.html
"""
import sqlite3
import json
from datetime import datetime


# 映射表：QueryType 到 UIGF gacha_type
GACHA_TYPE_MAP = {
    100: {"uigf_gacha_type": "100", "gacha_type": "100"},  # 新手祈愿
    200: {"uigf_gacha_type": "200", "gacha_type": "200"},  # 常驻祈愿
    301: {"uigf_gacha_type": "301", "gacha_type": "301"},  # 角色活动祈愿
    302: {"uigf_gacha_type": "302", "gacha_type": "302"},  # 武器活动祈愿
    400: {"uigf_gacha_type": "301", "gacha_type": "400"},  # 角色活动祈愿-2
    500: {"uigf_gacha_type": "500", "gacha_type": "500"},  # 集录祈愿
}

# 物品等级映射（根据 ItemId 范围推断，可能需要调整）
def get_rank_type(item_id):
    """根据物品 ID 推断稀有度"""
    # 这里需要根据实际的物品 ID 数据库来映射
    # 暂时返回默认值，需要完善
    if 10000 <= item_id <= 19999:
        return "5"  # 5星角色
    elif 11000 <= item_id <= 16999:
        return "4"  # 4星角色
    elif 14000 <= item_id <= 14999:
        return "4"  # 4星武器
    elif 15000 <= item_id <= 15999:
        return "3"  # 3星武器
    return "3"  # 默认3星


def get_item_info(item_id):
    """获取物品信息（名称、类型等）"""
    # 这里应该有一个完整的物品数据库映射
    # 暂时返回基础信息
    rank = get_rank_type(item_id)
    if 10000 <= item_id <= 19999:
        return {
            "name": f"角色_{item_id}",
            "item_type": "角色",
            "rank_type": rank
        }
    else:
        return {
            "name": f"武器_{item_id}",
            "item_type": "武器",
            "rank_type": rank
        }


def parse_timestamp(time_str):
    """解析时间字符串，返回标准格式"""
    # 输入格式可能是: '2024-11-16 10:33:15\n+08:00' 或 '2024-11-16 10:33:15+00:00'
    # 输出格式: '2024-11-16 10:33:15' (必须严格符合 UIGF v3.0 格式)
    
    # 先移除换行符
    time_str = time_str.replace('\n', '')
    
    # 移除时区信息（+XX:XX 或 -XX:XX）
    import re
    time_str = re.sub(r'[+-]\d{2}:\d{2}$', '', time_str)
    
    return time_str.strip()


def get_timezone_from_uid(uid):
    """根据 UID 推断时区偏移"""
    # UIGF v3.0 标准规定的映射关系
    uid_str = str(uid)
    if uid_str.startswith('6'):
        return -5  # 美服
    elif uid_str.startswith('7'):
        return 1   # 欧服
    else:
        return 8   # 亚服/国服


def export_gacha_data(db_path, output_path, uid=None):
    """
    从数据库导出抽卡记录到 UIGF v3.0 格式
    
    Args:
        db_path: SQLite 数据库文件路径
        output_path: 输出 JSON 文件路径
        uid: 指定导出的 UID（可选，如果为 None 则使用数据库中的第一个）
    """
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 如果未指定 UID，获取第一个 ArchiveId 作为 UID
    if uid is None:
        cursor.execute("SELECT DISTINCT ArchiveId FROM gacha_items LIMIT 1")
        result = cursor.fetchone()
        if result:
            uid = result[0]
        else:
            print("错误: 数据库中没有抽卡记录")
            conn.close()
            return
    
    # 查询指定 UID 的所有抽卡记录
    cursor.execute("""
        SELECT InnerId, ArchiveId, GachaType, Id, ItemId, QueryType, Time
        FROM gacha_items
        WHERE ArchiveId = ?
        ORDER BY Id ASC
    """, (uid,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"错误: 未找到 UID {uid} 的抽卡记录")
        return
    
    print(f"正在导出 UID {uid} 的 {len(rows)} 条抽卡记录...")
    
    # 构建抽卡记录列表
    gacha_list = []
    
    for row in rows:
        inner_id, archive_id, gacha_type_db, record_id, item_id, query_type, time_str = row
        
        # 获取卡池类型映射
        gacha_info = GACHA_TYPE_MAP.get(query_type)
        if not gacha_info:
            print(f"警告: 未知的卡池类型 {query_type}, 跳过记录 {record_id}")
            continue
        
        # 获取物品信息
        item_info = get_item_info(item_id)
        
        # 解析时间
        formatted_time = parse_timestamp(time_str)
        
        # 构建记录（符合 UIGF v3.0 标准）
        record = {
            "uigf_gacha_type": gacha_info["uigf_gacha_type"],
            "gacha_type": gacha_info["gacha_type"],
            "item_id": str(item_id),
            "count": "1",
            "time": formatted_time,
            "name": item_info["name"],
            "item_type": item_info["item_type"],
            "rank_type": item_info["rank_type"],
            "id": str(record_id)
        }
        
        gacha_list.append(record)
    
    # 获取当前时间戳
    export_timestamp = int(datetime.now().timestamp())
    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 获取时区偏移
    region_time_zone = get_timezone_from_uid(uid)
    
    # 构建 UIGF v3.0 格式的输出
    uigf_data = {
        "info": {
            "uid": str(uid),
            "lang": "zh-cn",
            "export_timestamp": export_timestamp,
            "export_time": export_time,
            "export_app": "HutaoSave Exporter",
            "export_app_version": "1.0.0",
            "uigf_version": "v3.0",
            "region_time_zone": region_time_zone
        },
        "list": gacha_list
    }
    
    # 写入 JSON 文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(uigf_data, f, ensure_ascii=False, indent=2)
    
    print(f"导出完成!")
    print(f"- UID: {uid}")
    print(f"- 记录数: {len(gacha_list)}")
    print(f"- 时区偏移: {region_time_zone}")
    print(f"- 文件保存至: {output_path}")
    
    return uigf_data


if __name__ == "__main__":
    # 数据库路径
    db_path = r"c:\Users\azhegod\Desktop\hutaoSave\Userdata.db"
    
    # 输出文件路径
    output_path = r"c:\Users\azhegod\Desktop\hutaoSave\gacha_export_uigf_v3.json"
    
    # 执行导出（uid 参数可选，不指定则自动使用数据库中的第一个 UID）
    try:
        export_gacha_data(db_path, output_path)
    except Exception as e:
        print(f"导出失败: {e}")
        import traceback
        traceback.print_exc()
