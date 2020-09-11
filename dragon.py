import os
import sys
import json
import re
import urllib.parse

# 全局变量, 所有图片识别码
all_url = {}

# 图片相关文件
BAD_IMG_FILE = "DARGON-IMG-SUCC-100.dat.all" # "src_head.txt"
REDIS_TRANS_FILE = "trans_redis.log" # "dst_redis.log"
MYSQL_TRANS_FILE = "trans_mysql.log" # "dst_mysql.log"
OUTPUT_FILE = "result.txt"

# 记录所有的图片识别码
def get_mark():
    print("start mark url...")
    fd = open(BAD_IMG_FILE, 'r', encoding='UTF-8')
    for line in fd:
        # 如果是空行的话直接跳过
        if re.match(r'^\s*$', line):
            continue
        # 删除空白符，换行符
        line = line.rstrip()
        # mark = line.split("/")[-2]
        all_url[line] = 1
        # print(line)
    fd.close()
    print("finish mark url...")

def match_mysql_trans(f):
    print("start mysql trans...")
    fd = open(MYSQL_TRANS_FILE, 'r', encoding='UTF-8')
    for line in fd:
        # 如果是空行的话直接跳过
        if re.match(r'^\s*$', line):
            continue
        # 删除空白符，换行符
        line = line.rstrip()
        # 图片decode
        dragonid = line.split("\t")[0]
        desc = line.split("\t")[1]
        type = line.split("\t")[3]
        url = urllib.parse.unquote(desc)
        # 检查流水图片是否匹配脏图
        if url in all_url.keys():
            # 记录db的url, 避免重复计算
            print(dragonid, type, url, file=f)
    fd.close()
    print("finish mysql trans...")

def match_redis_trans(f):
    print("start redis trans...")
    fd = open(REDIS_TRANS_FILE, 'r', encoding='UTF-8')
    for line in fd:
        # 如果是空行的话直接跳过
        if re.match(r'^\s*$', line):
            continue
        # 删除空白符，换行符
        line = line.rstrip()
        # 解析json
        trans = json.loads(line)
        dragonid = trans["dragonid"]
        type = trans["type"]
        desc = trans["desc"]
        # 图片decode
        url = urllib.parse.unquote(desc)
        # 只解析 draw/word/smile
        if type not in ["draw","word","smile","connword"]:
            continue
        # 截取url图片//之间的内容, 取出倒数第二个分隔的内容, 作为图片识别码
        # s = desc.split("%2F")[-2]
        # 检查流水图片是否匹配脏图
        if url in all_url.keys():
            print(dragonid, type, url, file=f)
        # print(trans)
    fd.close()
    print("finish redis trans...")

if __name__ == '__main__':
    # 先删除结果文件
    if os.path.isfile(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    f = open(OUTPUT_FILE, 'w')

    # 记录所有非法的url
    get_mark()
    # 匹配db流水
    match_mysql_trans(f)
    # 匹配redis流水(企业龙)
    match_redis_trans(f)

    f.close()