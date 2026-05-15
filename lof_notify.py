"""
LOF基金溢价率监控 + 微信推送（Server酱）
用于 GitHub Actions 定时运行
测试分支功能
增加飞书推送功能
"""

import sys
import requests
import re
import time
import os
import csv
import argparse
import json
from datetime import datetime

# Windows 终端默认 GBK 编码无法输出 emoji，统一切换到 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_dotenv(path=".env"):
    """从本地 .env 文件加载环境变量（不覆盖已有环境变量，无需安装 python-dotenv）"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


# ─── 基金列表 ────────────────────────────────────────────────────────────────
FUNDS = [
("SZ167002", "167002", "鼎越LOF"),
("SZ165525", "165525", "基建工程LOF"),
("SH501209", "501209", "富久食品饮料LOF"),
("SZ161024", "161024", "军工LOF"),
("SZ160628", "160628", "地产LOF"),
("SZ163003", "163003", "长信利鑫LOF"),
("SZ167001", "167001", "鼎泰LOF"),
("SZ160620", "160620", "资源LOF"),
("SZ166016", "166016", "中欧纯债LOF"),
("SZ161122", "161122", "生物科技LOF"),
("SZ160636", "160636", "鹏华中证移动互联网A"),
("SZ163111", "163111", "申万中小LOF"),
("SZ160311", "160311", "华夏蓝筹LOF"),
("SZ161222", "161222", "国投瑞利LOF"),
("SZ166107", "166107", "多因子LOF"),
("SZ161816", "161816", "中证90LOF"),
("SZ165521", "165521", "金融LOF"),
("SZ164705", "164705", "恒生LOF"),
("SZ160616", "160616", "鹏华500LOF"),
("SZ160626", "160626", "信息LOF"),
("SH502048", "502048", "上证50LOF"),
("SZ160513", "160513", "稳健债LOF"),
("SZ164905", "164905", "交银国证新能源A"),
("SZ161015", "161015", "富国天盈LOF"),
("SH501031", "501031", "环境治理LOFC"),
("SZ167702", "167702", "德邦量化优选A"),
("SZ164818", "164818", "工银中证传媒A"),
("SH501043", "501043", "沪深300LOF"),
("SH502053", "502053", "券商LOF"),
("SZ161027", "161027", "证券LOF"),
("SZ160630", "160630", "国防LOF"),
("SZ161722", "161722", "招商丰泰LOF"),
("SZ160638", "160638", "带路LOF"),
("SZ165312", "165312", "建信央视财经50"),
("SH502010", "502010", "证券LOF"),
("SZ160918", "160918", "中小盘LOF"),
("SZ160135", "160135", "高铁基金LOF"),
("SZ163005", "163005", "长信利众LOF"),
("SH502023", "502023", "钢铁LOF"),
("SZ160717", "160717", "H股LOF"),
("SZ161728", "161728", "招商优选LOF"),
("SH502000", "502000", "500增强LOF"),
("SZ165522", "165522", "TMTLOF"),
("SZ164206", "164206", "天弘添利LOF"),
("SZ160218", "160218", "房地产LOF"),
("SZ168102", "168102", "九泰锐富LOF"),
("SZ160634", "160634", "鹏华中证环保产业A"),
("SH501017", "501017", "国泰融丰LOF"),
("SZ168204", "168204", "煤炭LOF"),
("SZ160639", "160639", "高铁LOF"),
("SZ161815", "161815", "抗通胀LOF"),
("SZ162509", "162509", "中证A100LOF"),
("SH501045", "501045", "沪深300LOFC"),
("SZ161727", "161727", "招商增荣LOF"),
("SZ165310", "165310", "建信沪深300增强A"),
("SZ166109", "166109", "信澳量化先锋A"),
("SZ160921", "160921", "多策略LOF"),
("SZ162712", "162712", "广发聚利LOF"),
("SZ167501", "167501", "安信宝利债券LOF"),
("SZ161607", "161607", "巨潮100LOF"),
("SZ161216", "161216", "国投双债LOF"),
("SH501058", "501058", "新能源车LOFC"),
("SZ163114", "163114", "申万环保LOF"),
("SZ169105", "169105", "东方红睿华LOF"),
("SH501200", "501200", "科创加银LOF"),
("SZ160505", "160505", "博时主题LOF"),
("SZ163113", "163113", "申万证券LOF"),
("SZ160133", "160133", "南方天元LOF"),
("SH502006", "502006", "国企改革LOF"),
("SH501087", "501087", "交银瑞丰LOF"),
("SZ160722", "160722", "嘉实惠泽LOF"),
("SZ160916", "160916", "优选LOF"),
("SZ160643", "160643", "空天军工LOF"),
("SZ160633", "160633", "券商LOF"),
("SH501207", "501207", "华夏创新未来LOF"),
("SH501076", "501076", "鹏华创新动力LOF"),
("SZ165513", "165513", "中信保诚商品LOF"),
("SZ163821", "163821", "沪深300等权LOF"),
("SZ160635", "160635", "医药LOF基金"),
("SH501202", "501202", "华泰创新先锋LOF"),
("SZ160219", "160219", "医药LOF"),
("SZ160716", "160716", "基本面50LOF"),
("SZ161025", "161025", "互联网LOF"),
("SZ165520", "165520", "有色LOF"),
("SH501050", "501050", "50AHLOF"),
("SZ166401", "166401", "稳健增利LOF"),
("SH501303", "501303", "恒生中型股LOF"),
("SZ165524", "165524", "中信保诚中证智能家居A"),
("SZ165515", "165515", "中信保诚300LOF"),
("SZ165531", "165531", "中信保诚多策略A"),
("SH501038", "501038", "银华明择"),
("SH501065", "501065", "经典成长"),
("SH501070", "501070", "广发睿阳"),
("SH501088", "501088", "嘉实瑞虹"),
("SH501100", "501100", "博时安康18个月定开"),
("SH501226", "501226", "长城全球新能源汽车A"),
("SH501300", "501300", "美元债LOF"),
("SH501312", "501312", "海外科技LOF"),
("SZ160216", "160216", "国泰商品LOF"),
("SZ160323", "160323", "华夏磐泰LOF"),
("SZ160515", "160515", "安丰18定开"),
("SZ160617", "160617", "鹏华丰润LOF"),
("SZ160618", "160618", "鹏华丰泽LOF"),
("SZ160632", "160632", "酒LOF"),
("SZ160926", "160926", "创业板定开"),
("SZ161005", "161005", "富国天惠LOF"),
("SZ161014", "161014", "富国汇利定开"),
("SZ161040", "161040", "创业富国定开"),
("SZ161116", "161116", "黄金主题LOF"),
("SZ161117", "161117", "易基永旭添利定开"),
("SZ161124", "161124", "港股小盘LOF"),
("SZ161125", "161125", "标普500LOF"),
("SZ161126", "161126", "标普医疗保健LOF"),
("SZ161127", "161127", "标普生物科技LOF"),
("SZ161128", "161128", "标普信息科技LOF"),
("SZ161129", "161129", "原油LOF易方达"),
("SZ161132", "161132", "易方达科顺定开"),
("SZ161226", "161226", "国投白银LOF"),
("SZ161505", "161505", "银河通利债券LOF"),
("SZ161716", "161716", "招商双债LOF"),
("SZ161725", "161725", "白酒基金LOF"),
("SZ161729", "161729", "招商瑞利LOF"),
("SZ161837", "161837", "银华大盘定开"),
("SZ161908", "161908", "万家添利LOF"),
("SZ161912", "161912", "社会责任定开"),
("SZ161914", "161914", "创业板2年定开"),
("SZ162216", "162216", "宏利500增强LOF"),
("SZ162411", "162411", "华宝油气LOF"),
("SZ162415", "162415", "美国消费LOF"),
("SZ162511", "162511", "国联安双佳信用"),
("SZ162715", "162715", "广发聚源LOF"),
("SZ162719", "162719", "石油LOF"),
("SZ162720", "162720", "广发创业板定开"),
("SZ163208", "163208", "全球油气能源LOF"),
("SZ163407", "163407", "兴全沪深300LOF"),
("SZ164210", "164210", "天弘同利LOF"),
("SZ164212", "164212", "天弘全球新能源汽车A"),
("SZ164701", "164701", "黄金LOF"),
("SZ164810", "164810", "工银纯债定开"),
("SZ164824", "164824", "印度基金LOF"),
("SZ164902", "164902", "交银添利LOF"),
("SZ165311", "165311", "信用债LOF"),
("SH506000", "506000", "科创板基金"),
("SH506001", "506001", "万家科创板"),
("SH506002", "506002", "易方达科创板"),
("SH506003", "506003", "富国科创板"),
("SH506005", "506005", "科创板博时"),
("SH506006", "506006", "汇添富科创板"),
("SH506008", "506008", "科创板长城"),
("SZ160625", "160625", "证保LOF"),
("SZ161631", "161631", "人工智能LOF"),
("SH501021", "501021", "香港中小LOF"),
("SZ161026", "161026", "国企改革LOF"),
("SZ162605", "162605", "景顺鼎益LOF"),
("SZ167003", "167003", "鼎弘LOF"),
("SH501026", "501026", "财通福享混合LOF"),
("SZ161019", "161019", "富国天锋LOF"),
("SZ161039", "161039", "1000增强LOF"),
("SZ164814", "164814", "工银双债LOF"),
("SH501080", "501080", "科创主题投资基金LOF"),
("SZ166802", "166802", "浙商沪深300指数增强A"),
("SZ160607", "160607", "鹏华价值优势LOF"),
("SH501025", "501025", "香港银行LOF"),
("SH501016", "501016", "券商基金LOF"),
("SZ164703", "164703", "汇添富纯债LOF"),
("SZ162107", "162107", "金鹰先进制造A"),
("SZ161628", "161628", "融通中证云计算与大数据A"),
("SZ161033", "161033", "智能汽车LOF"),
("SZ161730", "161730", "招商智星稳健配置A"),
("SZ163118", "163118", "医药生物LOF"),
("SZ161713", "161713", "招商信用添利LOF"),
("SZ166105", "166105", "信澳鑫安LOF"),
("SZ160621", "160621", "鹏华丰和LOF"),
("SZ160807", "160807", "长盛沪深300LOF"),
("SZ163415", "163415", "兴全商业模式LOF"),
("SZ161232", "161232", "国投瑞盛LOF"),
("SZ168203", "168203", "钢铁LOF"),
("SZ161706", "161706", "招商成长LOF"),
("SH502003", "502003", "军工LOF"),
("SZ160223", "160223", "创业板LOF"),
("SZ165523", "165523", "中信保诚中证信息安全A"),
("SZ167506", "167506", "安信深圳科技LOF"),
("SZ161030", "161030", "体育LOF"),
("SZ168104", "168104", "九泰锐丰LOF"),
("SZ161812", "161812", "深证100LOF"),
("SZ161123", "161123", "并购重组LOF"),
("SZ161017", "161017", "500增强LOF"),
("SZ160526", "160526", "博时优势企业"),
("SZ166008", "166008", "中欧强债LOF"),
("SZ161028", "161028", "新能源车LOF"),
("SZ165509", "165509", "中信保诚增强LOF"),
("SZ169201", "169201", "浙商鼎盈LOF"),
("SH501032", "501032", "财通福盛混合LOF"),
("SH501201", "501201", "科创红土LOF"),
("SZ160212", "160212", "国泰估值LOF"),
("SZ168701", "168701", "金融科技LOF"),
("SZ163907", "163907", "中海惠裕LOF"),
("SH501218", "501218", "工银睿智进取FOF"),
("SZ161038", "161038", "成长LOF"),
("SZ161820", "161820", "银华纯债LOF"),
("SZ161610", "161610", "融通领先成长LOF"),
("SZ161217", "161217", "国投资源LOF"),
("SZ160222", "160222", "食品LOF"),
("SH501307", "501307", "沪港深红利LOF"),
("SZ167302", "167302", "大湾区LOF"),
("SH501071", "501071", "泓德丰泽LOF"),
("SZ163115", "163115", "申万军工LOF"),
("SZ168101", "168101", "九泰锐智LOF"),
("SZ160925", "160925", "沪深港300LOF"),
("SZ160629", "160629", "传媒LOF"),
("SZ160135", "160135", "高铁基金LOF"),
("SZ167505", "167505", "安信中短利率债C"),
("SH501222", "501222", "如意招享FOF"),
("SZ161037", "161037", "高端制造LOF"),
("SZ161726", "161726", "生物医药LOF"),
("SZ163412", "163412", "兴全轻资产LOF"),
("SZ165512", "165512", "中信保诚机遇LOF"),
("SZ160125", "160125", "南方香港LOF"),
("SH501081", "501081", "科创中欧LOF"),
("SZ166023", "166023", "中欧瑞丰LOF"),
("SH501096", "501096", "国联安科创LOF"),
("SZ160910", "160910", "创新成长LOF"),
("SZ161036", "161036", "娱乐增强LOF"),
("SZ161010", "161010", "富国天丰LOF"),
("SZ163209", "163209", "诺安创业板指数增强A"),
("SH501028", "501028", "财通福瑞混合LOF"),
("SZ161031", "161031", "工业40LOF"),
("SZ165511", "165511", "中信保诚500LOF"),
("SZ160610", "160610", "鹏华动力LOF"),
("SZ161720", "161720", "证券基金LOF"),
("SH501205", "501205", "鹏华创新未来LOF"),
("SZ161115", "161115", "易基岁丰添利LOF"),
("SZ164606", "164606", "信用增利LOF"),
("SZ164208", "164208", "天弘丰利LOF"),
("SZ162721", "162721", "广发积极FOF-LOF"),
("SZ160140", "160140", "美国REIT精选LOF"),
("SH501030", "501030", "环境治理LOF"),
("SZ163406", "163406", "兴全合润LOF"),
("SZ160211", "160211", "国泰小盘LOF"),
("SZ160106", "160106", "南方高增LOF"),
("SZ163409", "163409", "兴全绿色LOF"),
("SH501085", "501085", "财通科创LOF"),
("SZ164105", "164105", "华富强债LOF"),
("SZ161811", "161811", "沪深300LOF银华"),
("SZ161229", "161229", "国投中国价值LOF"),
("SZ163503", "163503", "天治核心LOF"),
("SH501057", "501057", "新能源车LOF"),
("SH501095", "501095", "中银证券科技创新LOF"),
("SZ161614", "161614", "融通四季添利LOF"),
("SZ160225", "160225", "新能源汽车LOF"),
("SZ167301", "167301", "保险主题LOF"),
("SZ163801", "163801", "中银中国LOF"),
("SZ160631", "160631", "银行LOF基金"),
("SZ161133", "161133", "优势回报FOF-LOF"),
("SZ160805", "160805", "长盛同智LOF"),
("SZ160512", "160512", "博时卓越LOF"),
("SZ165517", "165517", "中信保诚双盈LOF"),
("SZ165516", "165516", "中信保诚周期LOF"),
("SZ160314", "160314", "华夏行业LOF"),
("SZ162108", "162108", "金鹰元盛债券LOF"),
("SZ161626", "161626", "融通通福LOF"),
("SH501019", "501019", "军工基金LOF"),
("SZ165519", "165519", "医药生物科技LOF"),
("SZ160518", "160518", "博时睿远LOF"),
("SZ161834", "161834", "银华鑫锐LOF"),
("SH501097", "501097", "科创国寿LOF"),
("SZ164808", "164808", "工银四季LOF"),
("SZ164403", "164403", "农业精选LOF"),
("SZ160919", "160919", "产业升级LOF"),
("SZ163819", "163819", "中银信用增利LOF"),
("SZ160326", "160326", "优选配置FOF-LOF"),
("SZ160324", "160324", "华夏磐晟LOF"),
("SH501008", "501008", "互联网医疗LOFC"),
("SZ168105", "168105", "九泰泰富LOF"),
("SZ166006", "166006", "中欧成长LOF"),
("SZ168103", "168103", "九泰锐益LOF"),
("SZ163402", "163402", "兴全趋势LOF"),
("SZ166009", "166009", "中欧动力LOF"),
("SZ160105", "160105", "南方积配LOF"),
("SZ163110", "163110", "申万量化LOF"),
("SZ160924", "160924", "恒生指数LOF"),
("SH501216", "501216", "富国行业精选FOF"),
("SH501051", "501051", "圆信永丰汇利LOF"),
("SZ161219", "161219", "国投新兴产业LOF"),
("SZ162207", "162207", "宏利效率混合LOF"),
("SZ162703", "162703", "广发小盘LOF"),
("SZ160611", "160611", "鹏华优质治理LOF"),
("SZ161233", "161233", "国投瑞泰LOF"),
("SH501005", "501005", "精准医疗LOF"),
("SZ164508", "164508", "国富中证A100LOF"),
("SH501089", "501089", "消费红利增强LOF"),
("SZ163417", "163417", "兴全合宜LOF"),
("SZ161724", "161724", "煤炭等权LOF"),
("SZ161227", "161227", "国投深证100LOF"),
("SH501188", "501188", "添富核心精选LOF"),
("SZ160220", "160220", "国泰民益LOF"),
("SZ161225", "161225", "国投瑞盈LOF"),
("SZ160142", "160142", "南方优势产业LOF"),
("SZ160127", "160127", "南方消费LOF"),
("SZ160637", "160637", "创业板LOF基金"),
("SZ161032", "161032", "煤炭龙头LOF"),
("SH501007", "501007", "互联网医疗LOF"),
("SH501208", "501208", "中欧创新未来LOF"),
("SH501311", "501311", "港股通新经济LOF"),
("SZ162607", "162607", "景顺资源LOF"),
("SH501073", "501073", "华安智联LOF"),
("SZ161903", "161903", "万家行业优选LOF"),
("SH501022", "501022", "银华鑫盛LOF"),
("SZ161831", "161831", "恒生国企LOF"),
("SH501001", "501001", "财通精选混合LOF"),
("SH501078", "501078", "科创配置LOF"),
("SZ164906", "164906", "中概互联网LOF"),
("SH501082", "501082", "科创投资LOF"),
("SH501310", "501310", "价值基金LOF"),
("SZ160215", "160215", "国泰价值LOF"),
("SZ164908", "164908", "交银中证环境治理A"),
("SZ162307", "162307", "海富通A100LOF"),
("SZ160641", "160641", "鹏华丰锐LOF"),
("SZ163109", "163109", "申万深成LOF"),
("SZ161224", "161224", "国投新丝路LOF"),
("SZ169104", "169104", "东方红睿满LOF"),
("SH501099", "501099", "平安新兴产业LOF"),
("SH501059", "501059", "国企红利LOF"),
("SH501061", "501061", "金选300C类LOF"),
("SH501217", "501217", "行业配置FOF"),
("SZ160813", "160813", "长盛同盛LOF"),
("SH501092", "501092", "交银瑞思LOF"),
("SZ165526", "165526", "中信保诚新旺回报A"),
("SH501083", "501083", "科创银华LOF"),
("SZ162006", "162006", "长城久富LOF"),
("SH501189", "501189", "嘉实产业优选LOF"),
("SZ163116", "163116", "申万电子LOF"),
("SH501009", "501009", "生物科技LOF"),
("SH502013", "502013", "一带一路LOF"),
("SZ161715", "161715", "大宗商品LOF"),
("SZ160812", "160812", "长盛同益LOF"),
("SH501220", "501220", "行业轮动FOF"),
("SZ160527", "160527", "博时研究优选LOF"),
("SH501186", "501186", "华夏兴融LOF"),
("SH501015", "501015", "财通升级混合LOF"),
("SH501060", "501060", "金选300A类LOF"),
("SZ165313", "165313", "建信优势LOF"),
("SH501206", "501206", "添富创新未来LOF"),
("SZ160622", "160622", "鹏华丰利LOF"),
("SZ160221", "160221", "有色金属LOF"),
("SZ161119", "161119", "易方达新综债LOF"),
("SZ163302", "163302", "大摩资源LOF"),
("SH501010", "501010", "生物科技LOFC"),
("SZ161810", "161810", "银华内需LOF"),
("SH501212", "501212", "广发优选配置FOF"),
("SH501227", "501227", "泓德红利优选LOF"),
("SZ164509", "164509", "国富恒利债券LOF"),
("SZ168401", "168401", "红土创新精选LOF"),
("SH501079", "501079", "科创大成LOF"),
("SH501098", "501098", "科创建信LOF"),
("SZ160646", "160646", "鹏华中证沪港深科技龙头A"),
("SZ163001", "163001", "长信医疗LOF"),
("SZ165508", "165508", "中信保诚深度LOF"),
("SZ162105", "162105", "金鹰持久增利LOF"),
("SZ162414", "162414", "新机遇LOF"),
("SZ166024", "166024", "中欧恒利定开"),
("SZ166025", "166025", "中欧远见定开"),
("SZ166027", "166027", "中欧创业定开"),
("SZ167508", "167508", "安信价值发现定开"),
("SZ169106", "169106", "东方红创优定开"),
("SH501018", "501018", "南方原油LOF"),
("SH501046", "501046", "财通福鑫定开混合"),
("SH501053", "501053", "东方红目标优选"),
("SH501062", "501062", "南方瑞合LOF"),
("SH501064", "501064", "国泰价值LOF"),
("SH501077", "501077", "富国创新企业LOF"),
("SH501093", "501093", "华夏翔阳LOF"),
("SH501203", "501203", "易基创新未来LOF"),
("SH501211", "501211", "民生加银优享FOF"),
("SH501219", "501219", "智胜先锋LOF"),
("SH501225", "501225", "全球芯片LOF"),
("SZ160128", "160128", "南方金利定开"),
("SZ160143", "160143", "创业板定开南方"),
("SZ160325", "160325", "华夏创业板定开"),
("SZ160416", "160416", "石油基金LOF"),
("SZ160529", "160529", "创业板博时定开"),
("SZ160644", "160644", "港美互联网LOF"),
("SZ160719", "160719", "嘉实黄金LOF"),
("SZ160723", "160723", "嘉实原油LOF"),
("SZ160726", "160726", "嘉实瑞享定开"),
("SZ165309", "165309", "沪深300LOF建信"),
("SZ169101", "169101", "东方红睿丰LOF"),
("SZ165528", "165528", "中信保诚鼎利LOF"),
("SZ160806", "160806", "长盛中证800LOF"),
("SZ166001", "166001", "中欧趋势LOF"),
("SH501210", "501210", "交银智选星光FOF"),
("SZ161131", "161131", "易方达科润LOF"),
("SZ160613", "160613", "鹏华盛世创新LOF"),
("SH501091", "501091", "嘉实欣荣LOF"),
("SZ166011", "166011", "中欧盛世LOF"),
("SZ161118", "161118", "中小企业100LOF"),
("SZ160642", "160642", "鹏华增瑞LOF"),
("SZ162215", "162215", "宏利聚利债券LOF"),
("SZ161035", "161035", "医药增强LOF"),
("SZ161029", "161029", "银行龙头LOF"),
("SH501075", "501075", "科创主题LOF"),
("SZ163418", "163418", "兴全合兴LOF"),
("SZ160421", "160421", "华安智增LOF"),
("SZ168301", "168301", "东海祥龙LOF"),
("SZ160322", "160322", "港股精选LOF"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": "https://fund.eastmoney.com/",
}

# ─── 数据获取（复用 lof_tracker.py 的逻辑）────────────────────────────────────

def fetch_premium():
    """从主列表页一次性抓取所有基金的EST数据（官方EST、EST日期、官方溢价、参考EST溢价）"""
    url = "https://palmmicro.com/woody/res/lofcn.php?sort=premium"
    print("获取溢价率（主列表页）...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        html = r.text

        m = re.search(r'id="estimationtable".*?<tbody>(.*?)</tbody>', html, re.S)
        if not m:
            print("  未找到 estimationtable")
            return {}

        tbody = m.group(1)
        result = {}

        for row_m in re.finditer(r'<tr>(.*?)</tr>', tbody, re.S):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row_m.group(1), re.S)
            if len(cells) < 6:
                continue

            code_m = re.search(r'>(S[HZ]\d{6})<', cells[0])
            if not code_m:
                continue
            full_code = code_m.group(1)

            est_m = re.search(r'>([\d.]+)<', cells[1])
            est = float(est_m.group(1)) if est_m else None

            date_m = re.search(r'(\d{4}-\d{2}-\d{2})', cells[2])
            est_date = date_m.group(1) if date_m else None

            prem_m = re.search(r'>([-\d.]+)', cells[3])
            premium = float(prem_m.group(1)) if prem_m else None

            ref_premium = None
            if cells[5].strip():
                ref_m = re.search(r'>([-\d.]+)', cells[5])
                ref_premium = float(ref_m.group(1)) if ref_m else None

            result[full_code] = {
                "est": est,
                "est_date": est_date,
                "premium": premium,
                "ref_premium": ref_premium,
            }

        print(f"  完成：{len(result)} 只")
        return result
    except Exception as e:
        print(f"  溢价获取失败: {e}")
        return {}

def fetch_prices():
    print("获取实时行情...")
    codes = ",".join(
        ("sh" if f[0].startswith("SH") else "sz") + f[1] for f in FUNDS
    )
    try:
        r = requests.get(
            f"https://hq.sinajs.cn/list={codes}",
            headers={**HEADERS, "Referer": "https://finance.sina.com.cn"},
            timeout=15
        )
        r.encoding = "gbk"
        result = {}
        for line in r.text.splitlines():
            m = re.match(r'var hq_str_(s[hz])(\d{6})="([^"]+)"', line)
            if not m:
                continue
            full_code = m.group(1).upper() + m.group(2)
            parts = m.group(3).split(",")
            if len(parts) < 4:
                continue
            try:
                price = float(parts[3])
                prev = float(parts[2]) if parts[2] else 0
                change = round((price - prev) / prev * 100, 2) if prev else 0
                result[full_code] = {"price": price, "change": change}
            except:
                pass
        print(f"  完成：{len(result)} 只")
        return result
    except Exception as e:
        print(f"  行情获取失败: {e}")
        return {}

def parse_money_str(s):
    s = s.replace(",", "").strip()
    m = re.match(r'([\d.]+)\s*万元?', s)
    if m: return float(m.group(1)) * 10000
    m = re.match(r'([\d.]+)\s*亿元?', s)
    if m: return float(m.group(1)) * 1e8
    m = re.match(r'([\d.]+)\s*元?', s)
    if m: return float(m.group(1))
    return None

def fetch_quota_batch(codes6_batch):
    fcodes = ",".join(codes6_batch)
    url = (
        f"https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
        f"?pageIndex=1&pageSize={len(codes6_batch)}&plat=Android"
        f"&appType=ttjj&product=EFund&Version=1&Fcodes={fcodes}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if not data.get("Datas"):
            return {}
        result = {}
        for item in data["Datas"]:
            code = item.get("FCODE", "")
            sgzt = str(item.get("SGZT", "0"))
            sgsxe = float(item.get("SGSXE") or 0)
            sgba = float(item.get("SGBA") or 0)
            if sgzt == "1":
                status, status_text = "closed", "暂停申购"
            elif sgzt == "3":
                status, status_text = "closed", "封闭期"
            elif sgzt == "2":
                status, status_text = "limited", "限制大额"
            elif sgsxe > 0:
                status, status_text = "limited", "限额申购"
            else:
                status, status_text = "open", "正常申购"
            result[code] = {
                "status": status, "status_text": status_text,
                "quota": sgsxe if sgsxe > 0 else None,
                "big_quota": sgba if sgba > 0 else None,
            }
        return result
    except:
        return {}

def fetch_quota_page(code6):
    try:
        r = requests.get(f"https://fund.eastmoney.com/{code6}.html", headers=HEADERS, timeout=10)
        r.encoding = "utf-8"
        html = r.text
        raw_cells = re.findall(r'class="staticCell"[^>]*>(.*?)</span>\s*(?=<span|<div|$)', html, re.S)
        cells = [re.sub(r'<[^>]+>', '', c) for c in raw_cells]
        cell_text = " ".join(c.strip() for c in cells)
        status, status_text, quota = "unknown", "未知", None
        if "暂停申购" in cell_text or "暂停大额" in cell_text:
            status, status_text = "closed", "暂停申购"
        elif "封闭期" in cell_text:
            status, status_text = "closed", "封闭期"
        elif "限大额" in cell_text or "限制大额" in cell_text:
            status, status_text = "limited", "限制大额"
        elif "开放申购" in cell_text or "正常申购" in cell_text:
            status, status_text = "open", "正常申购"
        for target in [cell_text, html]:
            for pat in [r'单日累计购买上限\s*([\d.,]+\s*[万亿]?元?)',
                        r'单笔限购[：:]\s*([\d.,]+\s*[万亿]?元?)',
                        r'每日累计限购[：:]\s*([\d.,]+\s*[万亿]?元?)']:
                m = re.search(pat, target)
                if m:
                    quota = parse_money_str(m.group(1))
                    break
            if quota:
                break
        if quota and status not in ("closed",):
            status = "limited"
            status_text = "限制大额" if "限大额" in cell_text else "限额申购"
        return {"status": status, "status_text": status_text, "quota": quota, "big_quota": None}
    except Exception as e:
        print(f"  网页抓取失败 {code6}: {e}")
        return {"status": "error", "status_text": "查询失败", "quota": None, "big_quota": None}

def fetch_quota():
    print("获取限购状态...")
    all_codes = [f[1] for f in FUNDS]
    result = {}
    for i in range(0, len(all_codes), 20):
        result.update(fetch_quota_batch(all_codes[i:i+20]))
        time.sleep(0.5)
    failed = [f[1] for f in FUNDS if f[1] not in result]
    if failed:
        print(f"  App API 未返回 {len(failed)} 只，改用网页...")
        for code6 in failed:
            result[code6] = fetch_quota_page(code6)
            time.sleep(0.3)
    print(f"  完成")
    return result

def merge(premium_map, price_map, quota_map):
    rows = []
    for full_code, code6, name in FUNDS:
        p = price_map.get(full_code, {})
        e = premium_map.get(full_code, {})
        q = quota_map.get(code6, {"status": "error", "status_text": "查询失败", "quota": None, "big_quota": None})
        price = p.get("price")
        change = p.get("change")
        est = e.get("est")
        premium = e.get("premium")
        if premium is None and price and est:
            premium = round((price - est) / est * 100, 2)
        rows.append({
            "full_code": full_code, "code6": code6, "name": name,
            "price": price, "change": change, "est": est, "premium": premium,
            "est_date": e.get("est_date"), "ref_premium": e.get("ref_premium"),
            "status": q["status"], "status_text": q["status_text"],
            "quota": q["quota"], "big_quota": q["big_quota"],
        })
    rows.sort(key=lambda x: (x["premium"] or -999), reverse=False)
    return rows

# ─── 格式化 ──────────────────────────────────────────────────────────────────

def fmt_money(val):
    if not val: return "无限制"
    if val >= 1e8: return f"{val/1e8:.0f}亿"
    if val >= 1e4: return f"{val/1e4:.0f}万"
    return f"{val:.0f}元"

def build_wechat_message(rows, now_str):
    """构建微信推送的标题和正文（支持 Server酱 Markdown）"""
    today = datetime.now().strftime("%Y-%m-%d")

    def prem_cell(r, bold=True):
        """格式化溢价单元格，EST日期非今日时附加参考溢价"""
        prem = r["premium"]
        if prem is None:
            return "—"
        sign = "+" if prem > 0 else ""
        prem_str = f"**{sign}{prem:.2f}%**" if bold and prem > 0 else f"{sign}{prem:.2f}%"
        est_date = r.get("est_date")
        ref = r.get("ref_premium")
        if est_date and est_date != today:
            if ref is not None:
                ref_sign = "+" if ref > 0 else ""
                prem_str += f"（参考: {ref_sign}{ref:.2f}%）"
            else:
                prem_str += " ⚠️"
        return prem_str

    stale_est = any(r.get("est_date") and r["est_date"] != today for r in rows)

    arb = [r for r in rows if (r["premium"] or 0) < 0 and r["status"] in ("open", "limited")]
    all_pos = [r for r in rows if (r["premium"] or 0) > 0]

    title = f"LOF溢价提醒 {now_str}｜{len(arb)}只套利机会"
    if not arb:
        title = f"LOF溢价提醒 {now_str}｜暂无套利机会"

    lines = [f"## LOF 溢价追踪 · {now_str}", ""]

    if stale_est:
        lines.append("> ⚠️ 部分基金EST日期非今日，溢价率可能存在滞后，已显示参考EST溢价（如有）")
        lines.append("")

    # 套利机会
    if arb:
        lines.append(f"### ⚡ 套利机会（{len(arb)}只）")
        lines.append("")
        lines.append("| 基金 | 溢价 | 限额 | 状态 |")
        lines.append("|------|------|------|------|")
        for r in arb:
            lines.append(
                f"| {r['name']} `{r['full_code']}` "
                f"| {prem_cell(r, bold=True)} "
                f"| {fmt_money(r['quota'])} "
                f"| {r['status_text']} |"
            )
        lines.append("")
    else:
        lines.append("### 暂无套利机会")
        lines.append("")

    # 所有溢价基金（含暂停申购的）
    if all_pos:
        closed_pos = [r for r in all_pos if r["status"] not in ("open", "limited")]
        if closed_pos:
            lines.append(f"### ⚠️ 溢价但已暂停申购（{len(closed_pos)}只）")
            lines.append("")
            for r in closed_pos:
                lines.append(f"- {r['name']} `{r['full_code']}` 溢价 **{prem_cell(r, bold=False)}** · {r['status_text']}")
            lines.append("")

    # 全部排名（折叠展示前10）
    lines.append("### 📊 溢价率排行（前10）")
    lines.append("")
    lines.append("| 排名 | 基金 | 溢价率 | 限额 |")
    lines.append("|------|------|--------|------|")
    for i, r in enumerate(rows[:10], 1):
        lines.append(f"| {i} | {r['name']} | {prem_cell(r, bold=False)} | {fmt_money(r['quota'])} |")

    lines.append("")
    lines.append(f"---")
    lines.append(f"*数据来源：palmmicro + 天天基金 · {now_str}*")

    return title, "\n".join(lines)

# ─── Server酱推送 ─────────────────────────────────────────────────────────────

def send_wechat(title, content, sendkey):
    """通过 Server酱 推送微信消息"""
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    try:
        r = requests.post(url, data={
            "title": title,
            "desp": content,
        }, timeout=15)
        result = r.json()
        if result.get("code") == 0:
            print(f"✅ 微信推送成功")
        else:
            print(f"⚠️  推送失败: {result}")
    except Exception as e:
        print(f"❌ 推送异常: {e}")

# ─── 飞书推送 ─────────────────────────────────────────────────────────────────

def send_feishu(title, content, app_id, app_secret, chat_id):
    """通过飞书机器人推送消息到指定群"""
    try:
        # 获取 tenant_access_token
        token_res = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10
        )
        access_token = token_res.json().get("tenant_access_token", "")
        if not access_token:
            print("⚠️  飞书 token 获取失败")
            return

        # 发送消息
        msg = f"{title}\n\n{content}"
        res = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"receive_id": chat_id, "msg_type": "text", "content": json.dumps({"text": msg})},
            timeout=10
        )
        if res.json().get("code") == 0:
            print("✅ 飞书推送成功")
        else:
            print(f"⚠️  飞书推送失败: {res.json()}")
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")

# ─── 历史记录 CSV ─────────────────────────────────────────────────────────────

def save_history_csv(rows, now_str, filepath="history.csv"):
    """追加一行到历史CSV"""
    file_exists = os.path.exists(filepath)
    with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["时间"] + [r["full_code"] for r in rows]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        row = {"时间": now_str}
        for r in rows:
            row[r["full_code"]] = r["premium"] if r["premium"] is not None else ""
        writer.writerow(row)
    print(f"历史记录已追加到 {filepath}")

# ─── 本地测试 ─────────────────────────────────────────────────────────────────

def make_test_rows():
    """生成模拟数据，覆盖推送消息的所有场景：套利机会、暂停申购、折价排行"""
    return [
        # 正溢价 + 正常申购 → 套利机会
        {"full_code": "SZ164906", "code6": "164906", "name": "中概互联网LOF",
         "price": 1.520, "change": 2.15, "est": 1.450, "premium": 4.83,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
        # 正溢价 + 限额申购 → 套利机会（有限额）
        {"full_code": "SZ161130", "code6": "161130", "name": "纳斯达克100LOF",
         "price": 2.180, "change": 1.88, "est": 2.100, "premium": 3.81,
         "status": "limited", "status_text": "限额申购", "quota": 10000.0, "big_quota": None},
        # 正溢价 + 暂停申购 → 溢价但已暂停
        {"full_code": "SZ162415", "code6": "162415", "name": "美国消费LOF",
         "price": 1.350, "change": 0.75, "est": 1.310, "premium": 3.05,
         "status": "closed", "status_text": "暂停申购", "quota": None, "big_quota": None},
        # 正溢价 + 限制大额
        {"full_code": "SH501018", "code6": "501018", "name": "南方原油LOF",
         "price": 1.220, "change": -0.81, "est": 1.200, "premium": 1.67,
         "status": "limited", "status_text": "限制大额", "quota": 1000000.0, "big_quota": None},
        # 微小正溢价 + 正常申购
        {"full_code": "SZ160719", "code6": "160719", "name": "嘉实黄金LOF",
         "price": 3.580, "change": 0.56, "est": 3.560, "premium": 0.56,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
        # 折价
        {"full_code": "SZ161226", "code6": "161226", "name": "国投白银LOF",
         "price": 3.120, "change": 3.22, "est": 3.180, "premium": -1.89,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
        {"full_code": "SZ160140", "code6": "160140", "name": "美国REIT精选LOF",
         "price": 1.340, "change": 1.82, "est": 1.380, "premium": -2.90,
         "status": "open", "status_text": "正常申购", "quota": None, "big_quota": None},
    ]


# ─── 本地表格输出 ─────────────────────────────────────────────────────────────

def print_local_table(rows, now_str):
    """在终端以对齐表格打印完整查询结果，供本地调试使用"""
    today = datetime.now().strftime("%Y-%m-%d")

    # ANSI 颜色（Windows cmd 不一定支持，Terminal/iTerm/Linux 均可）
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"

    def color_prem(val, est_date):
        if val is None:
            return "   —   "
        sign = "+" if val > 0 else ""
        stale = est_date and est_date != today
        text = f"{sign}{val:+.2f}%"
        if stale:
            text += "⚠"
        if val > 2:
            return RED + BOLD + text + RESET
        elif val > 0:
            return RED + text + RESET
        else:
            return GREEN + text + RESET

    def color_status(status, text):
        if status == "open":
            return GREEN + text + RESET
        elif status == "limited":
            return YELLOW + text + RESET
        elif status == "closed":
            return RED + text + RESET
        return text

    sep = "─" * 78
    print(f"\n{BOLD}{CYAN}{'═'*78}{RESET}")
    print(f"{BOLD}{CYAN}  LOF 溢价实时查询  ·  {now_str}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*78}{RESET}")
    print(f"  {'排':>2}  {'代码':<10}  {'基金名称':<16}  {'现价':>7}  {'涨跌':>7}  {'EST':>7}  {'溢价率':>10}  {'状态':<8}  {'限额'}")
    print(sep)

    arb_count = 0
    for i, r in enumerate(rows, 1):
        prem    = r["premium"]
        price   = r["price"]
        change  = r["change"]
        est     = r["est"]
        status  = r["status"]

        price_s  = f"{price:.3f}"  if price  is not None else "  —  "
        change_s = f"{change:+.2f}%" if change is not None else "  —  "
        est_s    = f"{est:.3f}"    if est    is not None else "  —  "
        prem_s   = color_prem(prem, r.get("est_date"))
        status_s = color_status(status, r["status_text"])
        quota_s  = fmt_money(r["quota"])

        if prem and prem > 0 and status in ("open", "limited"):
            arb_count += 1
            rank_s = f"{BOLD}{RED}{i:>2}{RESET}"
        else:
            rank_s = f"{i:>2}"

        print(f"  {rank_s}  {r['full_code']:<10}  {r['name']:<16}  {price_s:>7}  {change_s:>8}  {est_s:>7}  {prem_s:>10}  {status_s:<8}  {quota_s}")

    print(sep)

    # 汇总行
    arb_rows    = [r for r in rows if (r["premium"] or 0) < 0 and r["status"] in ("open","limited")]
    closed_rows = [r for r in rows if (r["premium"] or 0) < 0 and r["status"] not in ("open","limited")]

    print(f"\n  {BOLD}套利机会{RESET}（负溢价且可申购）：{GREEN}{BOLD}{arb_count} 只{RESET}")
    if arb_rows:
        for r in arb_rows:
            sign = "+" if (r["premium"] or 0) > 0 else ""
            stale = "⚠ EST非今日 " if r.get("est_date") and r["est_date"] != today else ""
            print(f"    → {r['name']} {r['full_code']}  溢价 {RED}{sign}{r['premium']:.2f}%{RESET}  {stale}{r['status_text']}  限额:{fmt_money(r['quota'])}")

    if closed_rows:
        print(f"\n  {BOLD}溢价但暂停申购{RESET}（{len(closed_rows)} 只）：")
        for r in closed_rows:
            print(f"    ⚠ {r['name']} {r['full_code']}  溢价 {r['premium']:.2f}%  · {r['status_text']}")

    stale = [r for r in rows if r.get("est_date") and r["est_date"] != today]
    if stale:
        print(f"\n  {YELLOW}⚠  {len(stale)} 只基金的EST日期非今日，溢价率可能滞后{RESET}")
        for r in stale:
            ref = r.get("ref_premium")
            ref_s = f"  参考溢价: {ref:+.2f}%" if ref is not None else ""
            print(f"     · {r['name']}  EST日期: {r['est_date']}{ref_s}")

    print(f"\n  数据来源: palmmicro + 天天基金  ·  {now_str}")
    print(f"{CYAN}{'═'*78}{RESET}\n")


# ─── 主程序 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LOF基金溢价率监控")
    parser.add_argument(
        "--test", action="store_true",
        help="使用模拟数据测试消息格式和推送（不抓取真实数据，不写入 CSV）"
    )
    parser.add_argument(
        "--local", action="store_true",
        help="本地调试模式：抓取真实数据，终端表格展示，不写入 CSV，不推送微信"
    )
    args = parser.parse_args()

    load_dotenv()  # 优先从本地 .env 文件加载 SERVERCHAN_KEY

    sendkeys = [
        "SCT348643TPeDG7b88AeaCEbpc4uqvPKv2",
         "SCT348625TeaJCpA5WwJh1WDaoGcZe1BwT",
         "SCT348719TRYV90SZ6SujEIaE4bwMFub7Q",
         "SCT348724TwhQxyd8VBZJxnOFNJyffnxBu"
    ]
    sendkey ="123"
    # for i in ["", "1", "2", "3", "4", "5"]:
    #     sendkey = os.environ.get(f"SERVERCHAN_KEY{i}", "").strip()
    #     if sendkey:
    #         sendkeys.append(sendkey)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    if args.local:
        print(f"=== [本地模式] LOF溢价监控 {now_str} ===")
        premium_map = fetch_premium()
        time.sleep(0.5)
        price_map = fetch_prices()
        time.sleep(0.5)
        quota_map = fetch_quota()
        rows = merge(premium_map, price_map, quota_map)
        print_local_table(rows, now_str)
        return  # 本地模式到此结束，不写 CSV，不推送

    if args.test:
        print(f"=== [测试模式] LOF溢价监控 {now_str} ===")
        print("使用模拟数据，不请求远程接口，不写入 history.csv\n")
        rows = make_test_rows()
        title, content = build_wechat_message(rows, now_str)
        # 测试模式在标题加【测试】标记，便于在微信中识别
        title = f"【测试】{title}"
    else:
        if not sendkey:
            print("⚠️  未设置 SERVERCHAN_KEY 环境变量，将跳过微信推送")
        print(f"=== LOF溢价监控 {now_str} ===")
        premium_map = fetch_premium()
        time.sleep(0.5)
        price_map = fetch_prices()
        time.sleep(0.5)
        quota_map = fetch_quota()
        rows = merge(premium_map, price_map, quota_map)
        save_history_csv(rows, now_str)
        title, content = build_wechat_message(rows, now_str)

    # 始终在终端打印完整消息，便于本地核查
    print(f"\n{'─'*60}")
    print(f"标题：{title}")
    print(f"{'─'*60}")
    print(content)
    print(f"{'─'*60}\n")

    # if sendkey:
    #     send_wechat(title, content, sendkey)
    for key in sendkeys:
        send_wechat(title, content, key)
        print(f"发送 key是: {key}")
    
    feishu_app_id     = os.environ.get("FEISHU_APP_ID", "")
    feishu_app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    feishu_chat_id    = os.environ.get("FEISHU_CHAT_ID", "")
    if feishu_app_id and feishu_app_secret and feishu_chat_id:
        send_feishu(title, content, feishu_app_id, feishu_app_secret, feishu_chat_id)
    elif args.test:
        print("💡 提示：在项目根目录创建 .env 文件并写入 SERVERCHAN_KEY=SCTxxx 即可同时测试实际推送")

if __name__ == "__main__":
    main()
