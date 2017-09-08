#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
      百度失信人黑名单的爬取
"""
from time import strftime,gmtime
import elasticsearch
import requests
import sys
import collections
import time
import json
from requests.exceptions import ProxyError
default_encoding = 'utf-8'
if sys.getdefaultencoding() != default_encoding:
    reload(sys)
    sys.setdefaultencoding(default_encoding)
# 代理
proxies = {
  "HTTPS": "https://114.230.234.223:808",
  "HTTP": "http://110.73.6.124:8123",
  "HTTPS": "https://221.229.44.14:808",
  "HTTP": "http://116.226.90.12:808",
  "HTTPS": "https://218.108.107.70:909"
}
# headers
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'zh-CN,zh;q=0.8',
    'Cookie': 'JSESSIONID=9CAA8C2BEE80C74B1952EFA9E69C4150; '
              'wafenterurl=L3NzZncvZnltaC8xNDUxL3p4Z2suaHRtP3N0PTAmcT0mc3hseD0xJmJ6e'
              'HJseD0xJmNvdXJ0X2lkPSZienhybWM9JnpqaG09JmFoPSZzdGFydENwcnE9JmVuZENwcnE9JnBhZ2U9Mw==; '
              '__utma=161156077.495504895.1501221471.1501221471.1501221471.1; '
              '__utmc=161156077; '
              '__utmz=161156077.1501221471.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); '
              'wafcookie=6638c7e043d4634e31fc03f98c44d6c6; '
              'wafverify=1ac90afbc1da7e6e86e4f07057416bcb; '
              'wzwsconfirm=7711ddd10a544f8efa642db4685e86e8; '
              'wzwstemplate=OA==; '
              'clientlanguage=zh_CN; '
              'JSESSIONID=0E40DC7D29A84A4528787317B590F218; '
              'ccpassport=601fd92b79652fe0489b52310512d73b; '
              'wzwschallenge=-1; '
              'wzwsvtime=1501226469',
    'Host': 'www.ahgyss.cn',
    'Proxy-Connection': 'keep-alive',
    'Referer': 'http://www.ahgyss.cn/ssfw/fymh/1451/zxgk.htm'
               '?st=0&q=&sxlx=&bzxrlx=&court_id=&bzxrmc=&zjhm=&ah=&startCprq=&endCprq=&page=11',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/58.0.3029.110 Safari/537.36'
}

# es链接地址
class ElasticSearchClient(object):
    @classmethod
    def get_es_servers(cls):
        hosts = [
            {"host": "172.16.39.55", "port": 9200},
            {"host": "172.16.39.56", "port": 9200},
            {"host": "172.16.39.57", "port": 9200}
        ]
        es = elasticsearch.Elasticsearch(
            hosts,
            sniff_on_start=True,
            sniff_on_connection_fail=True,
            sniffer_timeout=6000,
            http_auth=('elastic', 'cgtz@bigdata')
        )
        return es


def is_chinese(s):
    """
    判断是否有中文
    :return:
    """
    for ch in s.decode('utf-8'):
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False


# es数据操作
class LoadElasticSearchTest(object):
    def __init__(self, index, doc_type):
        self.index = index
        self.doc_type = doc_type
        self.es_client = ElasticSearchClient.get_es_servers()

    # 如果返回结果>=1,这表明该黑名单已经存在了
    def search_data(self, id_card_no, name):
        return len(self.es_client.search(index="blacklist",
                                        body={"query": {"bool": {"filter": [{"term": {"ID_card_no": str(id_card_no)}},{ "term": { "name":  str(name) }}]}}})['hits']['hits'] )

    def add_date(self, id, row_obj):
        """
        单条插入ES
        """
        resu = self.es_client.index(index=self.index, doc_type=self.doc_type, id=id, body=row_obj)
        return resu.get('created', '')


# 数据解析
def parse_data(html):
    # 一页的数据
    data_list = []
    # 具体数据
    rest = html["data"]
    rest = rest[0]["result"]
    if len(rest) > 0:
        try:
            for rs in rest:
                try:
                    result = collections.OrderedDict()
                    result['name'] = rs.get('iname', '')
                    result['ID_card_no'] = rs.get('cardNum', '')
                    id_card_no_pre = result.get('ID_card_no', '')
                    # 获取身份证，如果有
                    if id_card_no_pre:
                        result['ID_card_no_pre'] = id_card_no_pre[0: 6]
                    result['from_platform'] = rs.get('courtName', '')
                    result['case_code'] = rs.get('caseCode', '')
                    result['filing_time'] = rs.get('publishDate', '')
                    result['notes'] = rs.get('disruptTypeName', '')
                    result['involved_amt'] = rs.get('duty', '')
                    result['gender'] = rs.get('sexy', '')
                    result['address'] = rs.get('areaName', '')
                    data_list.append(result)
                except Exception as e:
                    print(e)
        except Exception as e:
            print(e)
    return data_list


# 爬取数据
def spider_data(url):
    try:
        try:
            # 使用代理
            res = requests.get(url, timeout=10, proxies=proxies)
        except ProxyError:
            print("ProxyError Exception ,use no proxies ")
            # 不使用代理
            res = requests.get(url, timeout=10)
        res = res.content
        res = res[:-2]
        res = res[46:]
        return json.loads(res)
    except Exception as e:
        print("爬取失败", e)
        return -1


# 数据最终结果的封装
def package_data(result):
    # 结果数据的封装
    message = collections.OrderedDict()
    if len(result) == 0:
        message["statue_code"] = 0
        message["msg_size"] = 0
    else:
        message["statue_code"] = 1
        message["msg_size"] = len(result)
        message["msg"] = result
    return json.dumps(message).decode("unicode-escape")


# 数据的解析,写到elastic中
def parse_data_write_es(rest):
    users = rest["msg"]
    if len(users) > 0:
        load_es = LoadElasticSearchTest('blacklist', 'promise')
        insert_count = 0
        for user in users:
            try:
                id_card = user.get('ID_card_no', '')
                name = user.get('name', '')
                if id_card and name and len(id_card) >= 6 and (not is_chinese(id_card)):
                    from_platform = user.get('from_platform', '').strip()
                    name = user.get('name', '').strip()
                    ID_card_no = user.get('ID_card_no', '').strip()
                    ID_card_no_pre = user.get('ID_card_no_pre', '').strip()
                    phone_no = user.get('phone_no', '').strip()
                    qq = user.get('qq', '').strip()
                    gender = user.get('gender', '').strip()
                    address = user.get('address', '').strip()
                    involved_amt = user.get('involved_amt', '').strip()
                    filing_time = user.get('filing_time', '').strip()
                    case_code = user.get('case_code', '').strip()
                    notes = user.get('notes', '').strip()

                    id = str(id_card) + str(name)
                    action = '{"from_platform": \"'+from_platform+'\", ' \
                              '"name": \"'+name+'\", ' \
                              '"ID_card_no": \"'+ID_card_no+'\", ' \
                              '"ID_card_no_pre": \"'+ID_card_no_pre+'\", ' \
                              '"phone_no": \"'+phone_no+'\", ' \
                              '"qq": \"'+qq+'\", ' \
                              '"gender": \"'+gender+'\", ' \
                              '"address": \"'+address+'\", ' \
                              '"involved_amt": \"'+involved_amt+'\", ' \
                              '"filing_time": \"'+filing_time+'\", ' \
                              '"case_code": \"'+case_code+'\",' \
                              '"notes": \"'+notes+'\"}'

                    if load_es.add_date(id, action) == True:
                        insert_count += 1
            except Exception as e:
                print(e)
        print('该批次共插入 '+str(insert_count)+' 条数据')


# 爬取每页的具体数据（处理超时异常,默认10次重试）
def re_spider_page_data(url_list):
    count = 1
    for url in url_list:
        try:
            html = spider_data(url)
            # 如果没有获取到数据则重试多次
            if html == -1:
                # 如果没有爬取成功则，重爬
                for num in range(1, 10):
                    time.sleep(8)
                    print(num)
                    if html == -1:
                        html = spider_data(url)
                    else:
                        break
            # 解析数据
            result = parse_data(html)
            # 包装数据
            result = package_data(result)
            result = json.loads(result)
            print('第 ' + str(count) + ' 页爬取，共 '+str(len(result["msg"]))+' 条数据====>')
            parse_data_write_es(result)
            time.sleep(1)
            count += 1
        except Exception as e:
            print(e)


if __name__ == '__main__':
    # 常用字
    # first_name_list = [
    #         '明','国','华','建','文','平','志','伟','东','海','强','晓','生','光','林','小','民','永','杰','军',
    #         '波','成','荣','新','峰','刚','家','龙','德','庆','斌','辉','良','玉','俊','立','浩','天','宏','子',
    #         '金','健','一','忠','洪','江','福','祥','中','正','振','勇','耀','春','大','宁','亮','宇','兴','宝',
    #         '少','剑','云','学','仁','涛','瑞','飞','鹏','安','亚','泽','世','汉','达','卫','利','胜','敏','群',
    #         '松','克','清','长','嘉','红','山','贤','阳','乐','锋','智','青','跃','元','南','武','广','思','雄',
    #         '锦','威','启','昌','铭','维','义','宗','英','凯','鸿','森','超','坚','旭','政','传','康','继','翔',
    #         '远','力','进','泉','茂','毅','富','博','霖','顺','信','凡','豪','树','和','恩','向','道','川','彬',
    #         '柏','磊','敬','书','鸣','芳','培','全','炳','基','冠','晖','京','欣','廷','哲','保','秋','君','劲',
    #         '栋','仲','权','奇','礼','楠','炜','友','年','震','鑫','雷','兵','万','星','骏','伦','绍','麟','雨',
    #         '行','才','希','彦','兆','贵','源','有','景','升','惠','臣','慧','开','章','润','高','佳','虎','根'
    # ]
    print('-----------------------start:' + str(strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + '-----------------------')
    first_name_list = [
        '世','舜','丞','主','产','仁','仇','仓','仕','仞','任','伋','众','伸','佐','佺','侃','侪','促',
        '俟','信','俣','修','倝','倡','倧','偿','储','僖','僧','僳','儒','俊','伟','列','则','刚','创',
        '前','剑','助','劭','势','勘','参','叔','吏','嗣','士','壮','孺','守','宽','宾','宋','宗','宙',
        '宣','实','宰','尊','峙','峻','崇','崈','川','州','巡','帅','庚','战','才','承','拯','操','斋',
        '昌','晁','暠','曹','曾','珺','玮','珹','琒','琛','琩','琮','琸','瑎','玚','璟','璥','瑜','生',
        '畴','矗','矢','石','磊','砂','碫','示','社','祖','祚','祥','禅','稹','穆','竣','竦','综','缜',
        '绪','舱','舷','船','蚩','襦','轼','辑','轩','子','杰','榜','碧','葆','莱','蒲','天','乐','东',
        '钢','铎','铖','铠','铸','铿','锋','镇','键','镰','馗','旭','骏','骢','骥','驹','驾','骄','诚',
        '诤','赐','慕','端','征','坚','建','弓','强','彦','御','悍','擎','攀','旷','昂','晷','健','冀',
        '凯','劻','啸','柴','木','林','森','朴','骞','寒','函','高','魁','魏','鲛','鲲','鹰','丕','乒',
        '候','冕','勰','备','宪','宾','密','封','山','峰','弼','彪','彭','旁','日','明','昪','昴','胜',
        '汉','涵','汗','浩','涛','淏','清','澜','浦','澉','澎','澔','濮','濯','瀚','瀛','灏','沧','虚',
        '豪','豹','辅','辈','迈','邶','合','部','阔','雄','霆','震','韩','俯','颁','颇','频','颔','风',
        '飒','飙','飚','马','亮','仑','仝','代','儋','利','力','劼','勒','卓','哲','喆','展','帝','弛',
        '弢','弩','彰','征','律','德','志','忠','思','振','挺','掣','旲','旻','昊','昮','晋','晟','晸',
        '朕','朗','段','殿','泰','滕','炅','炜','煜','煊','炎','选','玄','勇','君','稼','黎','利','贤',
        '谊','金','鑫','辉','墨','欧','有','友','闻','问','秀','娟','英','华','慧','巧','美','娜','静',
        '淑','惠','珠','翠','雅','芝','玉','萍','红','娥','玲','芬','芳','燕','彩','春','菊','兰','凤',
        '爱','妹','霞','香','月','莺','媛','艳','瑞','凡','佳','嘉','琼','勤','珍','贞','莉','桂','娣',
        '叶','璧','璐','娅','琦','晶','妍','茜','秋','珊','莎','锦','黛','青','倩','婷','姣','婉','娴',
        '瑾','颖','露','瑶','怡','婵','雁','蓓','纨','仪','荷','丹','蓉','眉','君','琴','蕊','薇','菁',
        '梦','岚','苑','婕','馨','瑗','琰','韵','融','园','艺','咏','卿','聪','澜','纯','毓','悦','昭',
        '冰','爽','琬','茗','羽','希','宁','欣','飘','育','滢','馥','筠','柔','竹','霭','凝','晓','欢',
        '霄','枫','芸','菲','寒','伊','亚','宜','可','姬','舒','影','荔','枝','思','丽''洁','梅','琳',
        '素','云','莲','真','环','雪','荣',
    ]
    for first_name in first_name_list:
        print('-------------------'+first_name+"-字：开始爬取-------------------")
        title = '失信被执行人名单'
        url_list = ['https://sp0.baidu.com/8aQDcjqpAAV3otqbppnN2DJv/api.php' \
                    '?resource_id=6899'
                    '&query=' + title + ''
                    '&cardNum='
                    '&iname=' + first_name + ''
                    '&areaName='
                    '&ie=utf-8'
                    '&oe=utf-8'
                    '&format=json'
                    '&t=1504228484424'
                    '&cb=jQuery110203450799221787775_1504227514772'
                    '&_=1504227514784'
                    ]
        # 爬取姓氏的前30页
        for page_num in range(1, 30):
            url_list.append(
                        'https://sp0.baidu.com/8aQDcjqpAAV3otqbppnN2DJv/api.php'
                        '?resource_id=6899'
                        '&query=' + title + ''
                        '&cardNum='
                        '&iname=' + first_name + ''
                        '&areaName='
                        '&pn='+str(page_num*50)+''
                        '&rn=10'
                        '&ie=utf-8'
                        '&oe=utf-8'
                        '&format=json'
                        '&t=1504259202271'
                        '&cb=jQuery110205604198048294293_1504254835087'
                        '&_=1504254835152'
                        )
        re_spider_page_data(url_list)
    print('-----------------------end:' + str(strftime("%Y-%m-%d %H:%M:%S", time.localtime())) + '-----------------------')
