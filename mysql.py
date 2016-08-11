# -*- coding: utf-8 -*-    
import os
import sys
import re
import random

# 定义数据库最大记录条数
MAX_RECORD_NUM = 3000000

if __name__ == '__main__':
    print('sql script start...')
    
    # 将兴趣名称放在一个数组中
    interestTbl = []
    interestNum = 0
    fd = open("data/interest.txt")
    for eachLine in fd:
        # 如果是空行的话直接跳过
        if re.match(r'^\s*$', eachLine):
            continue
        # 删除空白符，换行符
        eachLine = eachLine.rstrip()
        interestTbl.append(eachLine)
    # 打印兴趣数量
    interestNum = len(interestTbl)
    fd.close()
    
    # 将高校名称存放在一个数组中
    collegeTbl = []
    collegeNum = 0
    fd = open("data/college.txt")
    for eachLine in fd:
        # 如果是空行的话直接跳过
        if re.match(r'^\s*$', eachLine):
            continue
        # 删除空白符，换行符
        eachLine = eachLine.rstrip()
        collegeTbl.append(eachLine)
    # 打印高校数量
    collegeNum = len(collegeTbl)
    #print('num=%d' % collegeNum)
    fd.close()
    
    # 将百家姓名称存放在一个数组中
    surnameTbl = []
    surnameNum = 0
    fd = open("data/surname.txt")
    for eachLine in fd:
        # 如果是空行的话直接跳过
        if re.match(r'^\s*$', eachLine):
            continue
        # 删除字符中的空白符
        eachLine = eachLine.rstrip()
        for word in eachLine:
            # 跳过空白符
            if re.match(r'^\s*$', word):
                continue
            surnameTbl.append(word)
    # 删除空白符，换行符
    
    # 打印百家姓数量
    surnameNum = len(surnameTbl)
    #print('surname num=%d' % len(surnameTbl))
    fd.close()
    
    # 将所有学生信息写入记事本文件
    logBase = open("log_base.txt", 'w')
    logInterest = open("log_interest.txt", 'w')
    for i in range(MAX_RECORD_NUM):
    #for i in range(30000):
        # 组织数据库的记录格式（基本信息表）
        # 姓名(xxx)     年龄(18~35)      ID(1~100000)     学校(大学)
        name = random.choice(surnameTbl) + random.choice(surnameTbl) + random.choice(surnameTbl)
        age = random.randint(18,35)
        id = random.randint(1,100000)
        college = random.choice(collegeTbl)
        # print如果不开启flush,连续打印多行到文件时会导致2行黏在一行显示
        # 貌似开启flush还是会导致2行黏在一起啊
        # log = open("log.txt", 'w', 0) : ValueError: can't have unbuffered text I/O
        # 意思大概是text IO不能禁止缓冲
        # 原来是collegeTbl中的元素含有换行符的问题,需要手动删除,然后手动添加换行符
        print('%s|%d|%d|%s' %(name,age,id,college), file=logBase)
        
        # 组织数据库的记录格式（兴趣表）
        # 姓名(xxx)    兴趣(羽毛球/小说)
        # 每个人最多1~5种兴趣
        interest = []
        interestNum = random.randint(1,5)
        for i in range(interestNum):
            interest.append(random.choice(interestTbl))
        # 删除重复的元素
        interest = list(set(interest))
        str = ' '.join(interest)
        # 写入文件
        print('%s|%s' %(name,str), file=logInterest)
    logBase.close()
    logInterest.close()
    
    print("sql script finish.")
    
    