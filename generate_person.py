#!/usr/bin/env python3
"""生成随机人员信息（身份证号、姓名、手机号等）"""

import random
from datetime import datetime, timedelta

# 常见姓氏（百家姓前100）
SURNAMES = (
    "王李张刘陈杨黄赵吴周徐孙马胡朱郭何罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅"
    "沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝"
    "孔白崔康毛邱秦江史顾侯邵孟龙万段漕钱汤尹黎易常武乔贺赖龚文"
)

# 常见名字用字
GIVEN_CHARS = (
    "伟芳娜秀英敏静丽强磊洋勇艳杰娟涛超明华慧巧美婕娅欣雪飞"
    "玉平萍红旭凤琳璐瑶怡婷洁慧倩志成建文辉力固之轮明哲嘉"
    "芬菲乐佳媛德建华军磊刚峰强斌杰明辉鹏旭志鑫波涛俊楠"
)

# 常见省份简称（用于手机号）
PHONE_PREFIXES = [
    "130", "131", "132", "133", "134", "135", "136", "137", "138", "139",
    "150", "151", "152", "153", "155", "156", "157", "158", "159",
    "170", "176", "177", "178",
    "180", "181", "182", "183", "184", "185", "186", "187", "188", "189",
]

# 部分地区行政区划代码（6位）
AREA_CODES = [
    "110101", "110102", "110105", "110106", "110108", "110109", "110111", "110112",
    "120101", "120102", "120103", "120104", "120105", "120106",
    "310101", "310104", "310105", "310106", "310107", "310108", "310109", "310110",
    "440103", "440104", "440105", "440106", "440111", "440112", "440113", "440114",
    "440303", "440304", "440305", "440306", "440307", "440308",
    "500101", "500102", "500103", "500104", "500105", "500106",
    "330102", "330103", "330104", "330105", "330106", "330108", "330109", "330110",
    "320102", "320104", "320105", "320106", "320111", "320113", "320114", "320115",
    "510104", "510105", "510106", "510107", "510108", "510112", "510113", "510114",
    "420102", "420103", "420104", "420105", "420106", "420107", "420111", "420112",
    "430102", "430103", "430104", "430105", "430111", "430112", "430121", "430122",
    "370102", "370103", "370104", "370105", "370112", "370113",
    "350102", "350103", "350104", "350105", "350111", "350112",
    "610102", "610103", "610104", "610111", "610112", "610113",
    "500101", "500102", "500103", "500104", "500105", "500106",
    "210102", "210103", "210104", "210105", "210106", "210111", "210112",
    "220102", "220103", "220104", "220105", "220106",
    "230102", "230103", "230104", "230105", "230106", "230107", "230108",
]


def generate_birth_date(age, as_of_date=None):
    """根据年龄生成出生日期"""
    if as_of_date is None:
        as_of_date = datetime.now()
    
    # 生成该年龄范围内的随机日期
    start_year = as_of_date.year - age - 1
    end_year = as_of_date.year - age
    
    year = random.randint(start_year, end_year)
    month = random.randint(1, 12)
    
    # 根据月份确定天数
    if month in [1, 3, 5, 7, 8, 10, 12]:
        max_day = 31
    elif month in [4, 6, 9, 11]:
        max_day = 30
    elif month == 2:
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            max_day = 29
        else:
            max_day = 28
    else:
        max_day = 28
    
    day = random.randint(1, max_day)
    return datetime(year, month, day)


def calculate_id_checksum(id17):
    """计算身份证号校验码（第18位）"""
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_chars = "10X98765432"
    
    total = sum(int(id17[i]) * weights[i] for i in range(17))
    return check_chars[total % 11]


def generate_id_card(age=30, gender="女", area_code=None):
    """
    生成18位身份证号
    
    参数:
        age: 年龄（默认30岁）
        gender: 性别 "男" 或 "女"（默认女）
        area_code: 地区码（6位），不指定则随机
    返回:
        18位身份证号字符串
    """
    birth_date = generate_birth_date(age)
    return generate_id_card_from_birth(birth_date, gender, area_code)


def generate_id_card_from_birth(birth_date, gender="女", area_code=None):
    """
    根据出生日期生成18位身份证号
    
    参数:
        birth_date: datetime对象
        gender: 性别 "男" 或 "女"
        area_code: 地区码（6位），不指定则随机
    返回:
        18位身份证号字符串
    """
    # 地区码
    if area_code is None:
        area_code = random.choice(AREA_CODES)
    else:
        area_code = str(area_code).zfill(6)
    
    # 出生日期字符串
    birth_str = birth_date.strftime("%Y%m%d")
    
    # 顺序码（3位）：奇数为男，偶数为女
    seq = random.randint(0, 499) * 2
    if gender == "男":
        seq += 1
    seq_str = str(seq).zfill(3)
    
    # 前17位
    id17 = area_code + birth_str + seq_str
    
    # 校验码
    checksum = calculate_id_checksum(id17)
    
    return id17 + checksum


def generate_name(gender="女"):
    """生成随机中文姓名"""
    surname = random.choice(SURNAMES)
    
    # 名字：1-2个字
    name_len = random.choice([1, 2])
    given = "".join(random.choice(GIVEN_CHARS) for _ in range(name_len))
    
    return surname + given


def generate_phone():
    """生成随机手机号"""
    prefix = random.choice(PHONE_PREFIXES)
    suffix = "".join([str(random.randint(0, 9)) for _ in range(8)])
    return prefix + suffix


def generate_person(age=30, gender="女"):
    """
    生成完整人员信息（所有字段基于同一个人）
    
    返回字典:
        name: 姓名
        gender: 性别
        age: 年龄
        birth_date: 出生日期
        id_card: 身份证号
        phone: 手机号
    """
    # 先生成出生日期，后续所有字段基于此日期
    birth_date = generate_birth_date(age)
    
    # 生成身份证号（使用同一个出生日期）
    id_card = generate_id_card_from_birth(birth_date, gender)
    
    name = generate_name(gender)
    phone = generate_phone()
    
    return {
        "姓名": name,
        "性别": gender,
        "年龄": age,
        "出生日期": birth_date.strftime("%Y-%m-%d"),
        "身份证号": id_card,
        "手机号": phone,
    }


if __name__ == "__main__":
    # 测试生成
    for i in range(5):
        person = generate_person(age=30, gender="女")
        print(f"{person['姓名']} | {person['性别']} | {person['年龄']}岁 | "
              f"{person['出生日期']} | {person['身份证号']} | {person['手机号']}")
