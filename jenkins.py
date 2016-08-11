# -*- coding: utf-8 -*-    
import os
import re
import sys
import glob
import time
import zipfile
import fnmatch
import tempfile
import subprocess
from ntpath import basename, dirname
from shutil import rmtree, copyfile, copy

# 压缩文件方式，为什么不能直接调用zipfile的宏定义???
ZIP_STORED = 0
ZIP_DEFLATED = 8
ZIP_BZIP2 = 12
ZIP_LZMA = 14

# 日期时间宏定义
DATE_INFO = r'$DATE'

# 按照源目录文件层次结构打包
ZIP_ALLFILE = r'*' # 对指定的文件格式进行压缩，'*.h'表示只压缩头文件，'*'表示压缩所有文件

# jenkins命令参数集合
ARG_TAG_NONE = 0 # 找不到TAG参数
ARG_TAG_ALPHA = 1 # TAG参数
ARG_TAG_BETA = 2 # TAG参数
ARG_TAG_RELEASE = 3 # TAG参数
ARG_TAG_REMOVE = 4 # TAG参数
ARG_DATE = 5 # 日期参数
ARG_BUILD = 6 # 编译和打包参数

ARG_TBL = \
[
    ['-build', ARG_BUILD], # 是否需要编译工程和打包zip文件
    ['-alpha', ARG_TAG_ALPHA], # tag选项，SVN版本号在ini配置文件中
    ['-beta', ARG_TAG_BETA], # tag选项，beta版本(中试版本)，SVN版本号在ini配置文件中
    ['-release', ARG_TAG_RELEASE], # tag选项，release版本，SVN版本号在ini配置文件中
    ['-rmtag', ARG_TAG_REMOVE], # tag选项，如果SVN目标TAG路径已经存在，则删除重复的TAG路径
    ['-date@', ARG_DATE], # 日期信息，用于目标zip文件或者tag文件夹日期，'@'后面为日期时间信息
]

# 配置文件命令集合
CMD_TBL = \
[
    # 编译命令 - 格式为'@@@...xxx...@@@'，其中xxx为查找标识符，...表示多于3个'@'符号，xxx前面或者后面允许多个空格
    ['[@]{3,}\s*VXWORKS_BUILD_START\s*[@]{3,}', '[@]{3,}\s*VXWORKS_BUILD_END\s*[@]{3,}', 'vxworks_build'],
    ['[@]{3,}\s*KEIL_BUILD_START\s*[@]{3,}', '[@]{3,}\s*KEIL_BUILD_END\s*[@]{3,}', 'keil_build'],
    ['[@]{3,}\s*CCS_BUILD_START\s*[@]{3,}', '[@]{3,}\s*CCS_BUILD_END\s*[@]{3,}', 'ccs_build'],
    ['[@]{3,}\s*IAR_BUILD_START\s*[@]{3,}', '[@]{3,}\s*IAR_BUILD_END\s*[@]{3,}', 'iar_build'],
    # 打包命令
    ['[@]{3,}\s*ZIP_TAR_START\s*[@]{3,}', '[@]{3,}\s*ZIP_TAR_END\s*[@]{3,}', 'zip'],
    # TAG命令
    ['[@]{3,}\s*TAG_START\s*[@]{3,}', '[@]{3,}\s*TAG_END\s*[@]{3,}', 'tag'],
]

# TAG命令和SVN命令
TAG_CMD = 'TAG'
SVN_CMD = 'SVN'

# ftp服务器路径
RE_FTP_DIR = r"\s*FTP_DIR\s*=\s*(.+?)\s*$" # FTP服务器目录
# 源代码根目录
RE_BUILD_ROOT = r"\s*ROOT_DIR\s*=\s*(.+?)\s*$" # 源代码根目录

# VXWORKS编译命令正则表达式
RE_VX_BUILD_MKFILE = r"PRJ_ROOT_DIR" # makefile文件编译选项
RE_VX_BUILD_ENV = r"\s*WRENV\s*=\s*(.+?)\s*$" # 环境变量
RE_VX_BUILD_SPEC = r"\s*BUILD_SPEC\d{1,2}\s*=\s*(.+?)\s*$" # 体系结构
RE_VX_BUILD_PRO = r"\s*PRO_NAME\d{1,2}\s*=\s*(.+?)\s*$" # 工程路径
RE_VX_BUILD_TAR = r"\s*TAR_NAME\d{1,2}\s*=\s*(.+?)\s*$" # 目标文件名称
RE_VX_BUILD_MAKE = r'\s*MAKE_PRO\d{1,2}\s*=\s*(.+?)\s*$' # 编译命令

# IAR编译命令正则表达式
RE_IAR_BUILD_ENV = r"\s*IARENV_DIR\s*=\s*(.+?)\s*$" # 环境变量
RE_IAR_BUILD_PRO = r"\s*PRO_NAME\d{1,2}\s*=\s*(.+?)\s*$" # 工程路径
RE_IAR_BUILD_TAR = r"\s*TAR_NAME\d{1,2}\s*=\s*(.+?)\s*$" # 目标文件名称
RE_IAR_BUILD_MAKE = r'\s*MAKE_PRO\d{1,2}\s*=\s*(.+?)\s*$' # 编译命令
RE_IAR_FTP_FILE = r'\s*IAR_FTP_FILE\s*=\s*(.+?)\s*$' # FTP共享文件

# IAR应用程序合并正则表达式
RE_IAR_MERGER_SVN = r"\s*MERGER_SVN\s*=\s*(.+?)\s*$" # SVN下载合并文件
RE_IAR_MERGER_FILE = r"\s*MERGER_FILE\s*=\s*(.+?)\s*$" # 合并文件名称
RE_IAR_MERGER_OUTPUT = r"\s*MERGER_OUTPUT\s*=\s*(.+?)\s*$" # 合并后输出文件名称

# KEIL编译命令正则表达式
RE_KEIL_BUILD_BATPATH = r"\s*BAT_PATH\d{1,2}\s*=\s*(.+?)\s*$" # BAT脚本文件路径
RE_KEIL_BUILD_OUTPATH = r"\s*OUT_PATH\d{1,2}\s*=\s*(.+?)\s*$" # 目标输出文件路径
RE_KEIL_BUILD_TAR = r"\s*TAR_NAME\d{1,2}\s*=\s*(.+?)\s*$" # 目标文件名称
RE_KEIL_BUILD_FTPFILE = r"\s*KEIL_FTP_FILE\s*=\s*(.+?)\s*$" # FTP共享文件目标文件

# 打包命令正则表达式
RE_ZIP_NAME = r'\s*ZIP_NAME\s*=\s*(.+?)\s*$' # zip文件名称
RE_ZIP_SVN = r'\s*ZIP_SVN\d{1,2}\s*=\s*(.+?)\s*$' # SVN文件名称
RE_ZIP_END = r'\s*ZIP_END\s*$'
RE_ZIP_DIR = r'\s*ZIP(_\dDIR){1,2}\s*=\s*(.+?)\s*$' # zip文件夹名称
RE_ZIP_FILE = r'\s*ZIP_FILE\s*=\s*(.+?)\s*$' # zip打包文件列表
RE_ZIP_DNAME = r'\s*ZIP_DIR_NAME\s*=\s*(.+?)\s*$'

# TAG命令正则表达式
# 3种tag模式，alpha、beta、release
# 正则表达式中不能使用括号标识符???
RE_TAG_ALPHA_ST = r'[@]{3,}\s*ALPHA_START\s*[@]{3,}\s*$'
RE_TAG_ALPHA_END = r'[@]{3,}\s*ALPHA_END\s*[@]{3,}\s*$'
RE_TAG_BETA_ST = r'[@]{3,}\s*BETA_START\s*[@]{3,}\s*$'
RE_TAG_BETA_END = r'[@]{3,}\s*BETA_END\s*[@]{3,}\s*$'
RE_TAG_RELEASE_ST = r'[@]{3,}\s*RELEASE_START\s*[@]{3,}\s*$'
RE_TAG_RELEASE_END = r'[@]{3,}\s*RELEASE_END\s*[@]{3,}\s*$'
# TAG命令参数
RE_TAG_ARG = r'\s*TAG_ARG\d{1,2}\s*=\s*(.+?)\s*$' # 参数变量，相当于宏定义
RE_TAG_SRC_PATH = r'\s*TAG_SRC_PATH\s*=\s*(.+?)\s*$' # TAG源目录路径
RE_TAG_DST_PATH = r'\s*TAG_DST_PATH\s*=\s*(.+?)\s*$' # TAG目标目录路径
RE_TAG_SRC_SVN = r'\s*SVN_SRC_PATH\s*=\s*(.+?)\s*$' # SVN源目录路径
RE_TAG_DST_SVN = r'\s*SVN_DST_PATH\s*=\s*(.+?)\s*$' # SVN目标目录路径


# 目标文件临时存放路径
g_root_dir = None
g_ftp_dir = None
ROMFS_DIR = r"ROMFS"

# 打印错误信息
class Error(EnvironmentError):
    pass

# 打包zip文件，抄袭zipfile源文件中main中的代码
def addToZip(zf, path, zippath):
    if os.path.isfile(path):
        zf.write(path, zippath, ZIP_DEFLATED)
    elif os.path.isdir(path):
        for nm in os.listdir(path):
            addToZip(zf, os.path.join(path, nm), os.path.join(zippath, nm))
    # else: ignore
    
# 嵌套打包文件夹，包括文件夹顶层目录
def zip_copy2(srcPath, dstPath):
    zf = zipfile.ZipFile(dstPath, 'w', ZIP_DEFLATED)
    # 包含上级目录
    # addToZip(zf, srcPath, os.path.basename(srcPath))
    # 不包含上级目录
    addToZip(zf, srcPath, None)
    zf.close()

# 删除svn隐藏文件
def delete_svn(rmpath = None):
    if (rmpath == None):
        raise Error("Error: no dir to delete")
        # raise Error("没有目录可以删除.")
        
    # 删除所有.svn隐藏文件
    for (p, d, f) in os.walk(rmpath):
        # 只删除.svn隐藏文件夹，不删除空文件夹
        for item in d:
            if '.svn' in item:
                # 只删除.svn隐藏文件夹
                s = os.path.join(p, item)
                print('delete .svn path = %s' % s)
                os.popen('rd /s /q %s' % s)

# 删除目录所有文件，包括隐藏文件.svn
def delete_allFile(rmpath = None):
    if (rmpath == None):
        raise Error("Error: no dir to delete")
        # raise Error("没有目录可以删除.")
    
    # 删除所有.svn隐藏文件
    for (p, d, f) in os.walk(rmpath):
        # 只删除.svn隐藏文件夹，不删除空文件夹
        for item in d:
            if '.svn' in item:
                # 只删除.svn隐藏文件夹
                s = os.path.join(p, item)
                os.popen('rd /s /q %s' % s)
    
    # 递归删除目录所有内容        
    print('remove path: ', rmpath)
    rmtree(rmpath, ignore_errors = True)

# 递归查找目录下匹配的文件类型
def find_files(dir, pattern = None):
    if pattern == None:
        pattern = ZIP_ALLFILE
    flst = []
    # root 和 dirs 到底有什么作用???
    for root, dirs, files in os.walk(dir):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                flst.append(os.path.join(root, basename))
    return flst

# 嵌套打包文件夹，不包括顶层目录
# 将指定目录的指定文件压缩后复制到另外一个目录，指定压缩文件类型([*.h], [*.c], [*])
def zip_copy(srcPath, dstPath = None, fileType = None):
    if fileType == None:
        fileType = ZIP_ALLFILE
    if dstPath == None:
        dstPath = r'tmp.zip'
    lst = find_files(srcPath, fileType)
    if len(lst) > 0:
        # 递归压缩指定目录所有文件
        tmp = zipfile.ZipFile(dstPath, 'w', ZIP_DEFLATED)
        for item in lst:
            # zipfile.write()中arcname指定归档的路径，可以实现相对路径进行打包
            # 将归档压缩文件的绝对路径部分删除
            tmp.write(item, item.replace(srcPath, ''))
        # print(tmp.printdir())
        tmp.close()
    else:        
        print("文件格式不正确，无法进行压缩")
        
# 替换文件名称日期信息
def replaceDate(srcarg = '', datearg = ''):
    dstarg = ''   
    # 需要替换日期信息
    if '$DATE' in srcarg:
        if datearg == '':
            timeInfo = time.strftime('%Y%m%d', time.localtime())
            dstarg = srcarg.replace('$DATE', '(%s)' % timeInfo)
        else:
            dstarg = srcarg.replace('$DATE', '(%s)' % datearg)
    # 不需要替换日期信息
    else:
        dstarg = srcarg
    # 返回更新日期后的参数
    return dstarg        

# 读取当前目录ini配置文件信息
def cmGetCfgInfo(flname):
    global g_ftp_dir # 引入外部全局变量
    global g_root_dir # 引入外部全局变量
    mark = False # 命令标记
    first = False
    allcmd = []
    
    fp = open(flname)    
    for eachLine in fp:
        # 注释行直接跳过
        if eachLine.startswith('#'):
            continue
        # 如果是空行的话直接跳过
        if re.match(r'^\s*$', eachLine):
            continue
        
        # 获取ftp服务器目录
        lst = re.match(RE_FTP_DIR, eachLine)
        if lst != None:
            g_ftp_dir = lst.group(1)
            
        # 获取目标文件临时文件夹路径
        lst = re.match(RE_BUILD_ROOT, eachLine)
        if lst != None:
            g_root_dir = lst.group(1)
        
        # 读取命令集合
        for item in CMD_TBL: 
            # 命令起始标识符
            if re.match(item[0], eachLine) != None:
                mark = True
                first = True
                subcmd = []
                subcmd.append(item[2])
                allcmd.append(subcmd)
                break
            # 命令结束标识符
            if re.match(item[1], eachLine) != None:
                mark = False
                break
        
        if (mark == True) and (first == True):
            first = False
        elif mark == True:
            subcmd.append(eachLine)
    return allcmd

#  处理vxworks平台编译命令
def dealVxBuild(buildmsg = [], buildarg = None):
    if buildarg == None:
        return
    
    global g_root_dir
    if len(buildmsg) == 0:
        raise Error("Error: no make command")
        # raise Error("无编译命令")
    
    # 整理编译命令
    wrenv = '' # 环境变量
    buildspec = [] # 体系结构目录
    proname = [] # 工程名称集合
    cmdlst = [] # 编译命令集合
    tarname = [] # 目标文件集合
    tmppro = ''
    for item in buildmsg:        
        # 字符串匹配环境变量
        lst = re.match(RE_VX_BUILD_ENV, item)
        if lst != None:
            wrenv = lst.group(1)
        # 体系结构目录匹配'BUILD_SPEC1~BUILD_SPECn'
        lst = re.match(RE_VX_BUILD_SPEC, item)
        if lst != None:
            buildspec.append(lst.group(1))
        # 字符串匹配'PRO_DIR1~PRO_DIRn'
        lst = re.match(RE_VX_BUILD_PRO, item)
        if lst != None:
            tmppro = lst.group(1)
            proname.append(lst.group(1))
        # 字符串匹配目标文件
        lst = re.match(RE_VX_BUILD_TAR, item)
        if lst != None:
            tarname.append(lst.group(1))
        # 匹配编译命令'MAKE_PRO1~MAKE_PROn'
        lst = re.match(RE_VX_BUILD_MAKE, item)
        if lst != None:
            # 如果存在工程路径编译选项则需要更新编译命令
            makecmd = lst.group(1)
            if RE_VX_BUILD_MKFILE in makecmd:
                makecmd = makecmd.replace(RE_VX_BUILD_MKFILE, r'%s=%s/%s' % (RE_VX_BUILD_MKFILE, g_root_dir, tmppro))
                # Vxwork编译命令make不支持Windows路径方式'\'，支持Linux路径方式'/'
                makecmd = makecmd.replace('\\', '/')
            cmdlst.append(makecmd)
    
    # 判断源代码根目录是否存在
    if (g_root_dir == None):
        raise Error("Error: can't find root code path")
        # raise Error('源代码根目录不存在!')
    
    # 删除svn隐藏文件
    # delete_svn(g_root_dir)
    
    # 构造编译命令集合
    allbuild = []
    if len(proname) == len(cmdlst) and len(proname) == len(tarname) and len(proname) == len(buildspec):
        size = len(proname)
        for i in range(size):
            # 每个工程的命令集合(工程路径，编译命令)
            subbuild = []
            subbuild.append(tarname[i]) # 目标文件名称: allbuild[x][0]
            subbuild.append(g_root_dir + '\\' + proname[i] + '\\' + buildspec[i]) # makefile文件路径: allbuild[x][1]
            subbuild.append(wrenv + '\t' + cmdlst[i]) # 编译命令: allbuild[x][2]
            allbuild.append(subbuild)
    else:
        raise Error("Error: number of make command wrong")
        # raise Error("编译命令集合个数不一致")
    
    # print((romfs, buildspec, allbuild))
    
    # 创建目标文件临时文件夹
    romfs = g_root_dir + '\\' + ROMFS_DIR
    if os.path.exists(romfs):
        delete_allFile(romfs)
    os.mkdir(romfs)
    
    # 编译前先清空目录工程目录Debug和NonDebug所有内容
    # 需要先判断该目录是否存在
    for item in allbuild:
        if len(item) == 3:
            # item[0]:目标文件，item[1]:makefile文件所在路径，item[2]:编译命令
            rmPath = item[1] + '\\' + item[0]
            if os.path.exists(rmPath):                
                delete_allFile(rmPath)
        else:
            raise Error("Error: number of make command wrong")
            # raise Error("编译命令个数不正确!")
    
    # 编译所有工程
    cppath = ''
    for item in allbuild:
        # 改变当前工作路径，切换makefile文件所在路径
        # item[0]:目标文件，item[1]:makefile文件所在路径，item[2]:编译命令，
        os.chdir(item[1])
        output = subprocess.check_output(item[2])           
        print(output)
        print('make %s success' % item[0])
        
        # 拷贝编译生成的目标文件到临时文件夹中
        cppath = r"%s\%s" % (item[1], item[0])
        if 'NonDebug' in os.listdir(cppath):
            cppath = cppath + '\\' + 'NonDebug'
            print("copy path: ", cppath)
        else:
            raise Error('can not find copy dir!')
        for tar in os.listdir(cppath):
            if item[0] in tar:
                print("copy file: ", tar)
                copy(cppath+'\\'+tar, romfs)
    print('make all success')
# IAR编译环境合并txt文件  
def mergerTxt(inDir = '', output = '', mergerFile = []):
    num = 0 # log临时文件数量
    dict = {}   # 代码段文件名称和代码段地址，需要进行排序后合并成一个txt
    logName = [] # log临时文件名称
    
    if inDir == '':
        raise Error("Error: can't find merger file input path")
        # raise Error("找不到合并文件输入路径!")
    if output == '':
        raise Error("Error: no output file")
        # raise Error("没有输出文件")
    if len(mergerFile) == 0:
        raise Error("no merger file")
        # raise Error("没有合并文件")
    
    # 切换到合并文件输入路径
    os.chdir(inDir)
    
    # 先删除目标文件
    if os.path.exists(output):
        os.remove(output)

    # 处理单个文件，提取文件的各个代码段到log*临时文件中   
    for item in mergerFile:
        print("merger file name: ", item)
        # print("合并文件名称:", item)
        logList = []
        fd = open(item)
        for eachLine in fd:
            if '@' in eachLine:     # 文件头必须声明为utf-8，否则不能识别eachLine内容具体的格式
                num += 1
                name = 'log' + str(num)
                logName.append(name) # 添加log文件到列表中
                log = open(name, 'w')   # w表示重新清空文件内容，a表示在文件末尾添加
                logList.append(log)
                addr = eachLine.strip('@')  # strip表示删除某个特定的字符，split表示过滤某个特定的字符
                dict[addr] = name  # name为代码段文件名称，addr为对应的代码段地址
                # print(int(addr, 16))    # 16进制字符串转换为整数
                # print(name + ': ', addr, end = '')   # 搜索每一行，如果遇到@，则打印该行内容到控制台中
            else:
                if 'q' not in eachLine:
                    print(eachLine, end = '', file = log)   # end表示行尾不添加换行符，file表示输出重定向到文件中，fd.readline表示只读取一行
        fd.close()
        for sublog in logList:
            sublog.close()    
    # print(dict)
    
    # 按照地址大小排序各个log文件，整合输出到1个txt文件中
    result = open(output, 'w')
    addrList = []
    newList = sorted([int(item, 16) for item in dict.keys()])   # key为16进制字符串地址，转换为10进制后重新合成List，再进行排序操作
    for addr in newList:   # 地址顺序为从小到大
        for key in dict.keys():
            if int(key, 16) == addr:   # 找到对应的地址
                fd = open(dict[key])
                addrList.append(fd)
                # print('opening file', dict[key])
                print('@' + key, end = '', file = result)     # 第一行信息
                for eachLine in fd:
                    print(eachLine, end = '', file = result)
                #print(dict[key])
    print('q', end = '', file = result)
    result.close()
    for item in addrList:
        item.close()
    # 删除所有临时文件
    for item in logName:
        os.remove(item)
    
def dealIarBuild(buildmsg = [], datearg = '', buildarg = None):
    if buildarg == None:
        return
    
    global g_root_dir
    if len(buildmsg) == 0:
        raise Error("Error: no make command")
        # raise Error("无编译命令")
    
    # 整理编译命令
    wrenv = '' # 环境变量
    proname = [] # 工程名称集合
    cmdlst = [] # 编译命令集合
    tarname = [] # 目标文件集合
    
    merger_svn = [] # svn下载合并文件
    merger_file = [] # 合并文件名称
    merger_output = '' # 合并后输出文件名称
    ftp_file = '' # FTP共享文件
    
    for item in buildmsg:        
        # 字符串匹配环境变量
        lst = re.match(RE_IAR_BUILD_ENV, item)
        if lst != None:
            wrenv = lst.group(1)
        # 字符串匹配'PRO_DIR1~PRO_DIRn'
        lst = re.match(RE_IAR_BUILD_PRO, item)
        if lst != None:
            tmppro = lst.group(1)
            proname.append(lst.group(1))
        # 字符串匹配目标文件
        lst = re.match(RE_IAR_BUILD_TAR, item)
        if lst != None:
            tarname.append(lst.group(1))
        # 匹配编译命令'MAKE_PRO1~MAKE_PROn'
        lst = re.match(RE_IAR_BUILD_MAKE, item)
        if lst != None:
            cmdlst.append(lst.group(1))
        # 匹配FTP共享文件夹目标文件
        lst = re.match(RE_IAR_FTP_FILE, item)
        if lst != None:
            ftp_file = lst.group(1)
        # 匹配下载SVN合并文件
        lst = re.match(RE_IAR_MERGER_SVN, item)
        if lst != None:
            merger_svn.append(lst.group(1))
        # 匹配合并文件名称
        lst = re.match(RE_IAR_MERGER_FILE, item)
        if lst != None:
            merger_file.append(lst.group(1))
        # 匹配合并后输出文件名称
        lst = re.match(RE_IAR_MERGER_OUTPUT, item)
        if lst != None:
            merger_output = lst.group(1)
    
    # 判断源代码根目录是否存在
    if (g_root_dir == None):
        raise Error("Error: can't find root code path")
        # raise Error('源代码根目录不存在!')
    
    # 构造编译命令集合
    allbuild = []
    if len(proname) == len(cmdlst) and len(proname) == len(tarname):
        size = len(proname)
        for i in range(size):
            # 每个工程的命令集合(工程路径，编译命令)
            subbuild = []
            subbuild.append(tarname[i]) # 目标文件名称: allbuild[x][0]
            subbuild.append(g_root_dir + '\\' + proname[i]) # makefile文件路径: allbuild[x][1]
            subbuild.append(wrenv + '\\' + cmdlst[i]) # 编译命令: allbuild[x][2]
            allbuild.append(subbuild)
    else:
        raise Error("Error: number of make command is wrong")
        # raise Error("编译命令集合个数不一致")

    for item in allbuild:
        print(item)
        
    # 创建目标文件临时文件夹
    romfs = g_root_dir + '\\' + ROMFS_DIR
    if os.path.exists(romfs):
        delete_allFile(romfs)
    os.mkdir(romfs)
    
    # 编译前先清空目录工程目录Debug和NonDebug所有内容
    # 需要先判断该目录是否存在
    for item in allbuild:
        if len(item) == 3:
            # item[0]:目标文件，item[1]:makefile文件所在路径，item[2]:编译命令
            rmdir = ['Release', 'Debug']
            for subdir in rmdir:
                rmPath = item[1] + '\\' + subdir
                if os.path.exists(rmPath):
                    delete_allFile(rmPath)
        else:
            raise Error("Error: number of make command is wrong")
            # raise Error("编译命令个数不正确!")
    
   # 编译所有工程
    cppath = ''
    for item in allbuild:
        # 改变当前工作路径，切换makefile文件所在路径
        # item[0]:目标文件，item[1]:makefile文件所在路径，item[2]:编译命令，
        os.chdir(item[1])
        output = subprocess.check_output(item[2])           
        print(output)
        print('make %s success' % item[0])
        
        # 拷贝编译生成的目标文件到临时文件夹中
        cppath = r"%s\Release\Exe" % item[1]
        if os.path.exists(cppath) == False:
            raise Error('can not find copy dir!')
        # 查找txt目标文件并且替换为ini配置的目标文件名称
        os.chdir(cppath)
        flname = glob.glob('*.txt')
        # 找不到txt文件；或者如果找到多个txt文件，表示编译出现问题，因为不能识别多个txt文件        
        if (len(flname) == 0) or (len(flname) > 1):
            raise Error("Error: IAR build can't find *.txt file or many txt file")            
        # 判断目标文件名称是否需要更新日期信息
        item[0] = replaceDate(item[0], datearg)
        # 如果找到txt文件则重命名该文件
        os.rename(flname[0], item[0])
        print("copy file: ", item[0])
        copy(cppath+'\\'+item[0], romfs)
    print('make all success')
    
    # 编译完成后查看是否需要进行合并txt
    if len(merger_file) > 0:
        # 导出SVN文件到临时文件夹
        if len(merger_svn) > 0:
            for item in merger_svn:
                svncmd = r'svn export' + '\t' + item + '\t' + romfs
                output = subprocess.check_output(svncmd)
                print(output)
        # 判断合并文件是否需要更新日期信息
        for idx in range(len(merger_file)):
            merger_file[idx] = replaceDate(merger_file[idx], datearg)
        # 判断合并输出文件名称是否需要更新日期信息
        merger_output = replaceDate(merger_output, datearg)
        # 合并txt文件        
        mergerTxt(romfs, merger_output, merger_file)
        print("merger txt file finish")
        # print("合并txt完成")
    
    # 拷贝目标文件到FTP共享文件夹
    if ftp_file != '':
        # 替换FTP共享文件夹目标文件名称日期
        ftp_file = replaceDate(ftp_file, datearg)
        # 拷贝目标文件到FTP共享目录
        for tar in os.listdir(romfs):
            if (ftp_file in tar) and (g_ftp_dir != None):
                if os.path.exists(g_ftp_dir):                                        
                    copy(romfs+'\\'+ftp_file, g_ftp_dir)

def dealKeilBuild(buildmsg = [], datearg = '', buildarg = None):
    if buildarg == None:
        return
    
    global g_root_dir
    if len(buildmsg) == 0:
        raise Error("Error: no root code path")
        # raise Error("无编译命令")
        
    batpath = [] # bat自动编译脚本集合
    outpath = [] # 目标文件输出文件夹集合
    tarname = [] # 目标文件集合
    ftp_file = '' # FTP共享文件夹目标文件
    
    for item in buildmsg:        
        # 字符串匹配bat自动编译脚本文件
        lst = re.match(RE_KEIL_BUILD_BATPATH, item)
        if lst != None:
            batpath.append(lst.group(1))
        # 字符串匹配目标输出文件夹
        lst = re.match(RE_KEIL_BUILD_OUTPATH, item)
        if lst != None:
            outpath.append(lst.group(1))
        # 字符串匹配目标文件
        lst = re.match(RE_KEIL_BUILD_TAR, item)
        if lst != None:
            tarname.append(lst.group(1))
        # 字符串匹配FTP共享文件夹目标文件
        lst = re.match(RE_KEIL_BUILD_FTPFILE, item)
        if lst != None:
            ftp_file = lst.group(1)
            
    # 判断源代码根目录是否存在
    if (g_root_dir == None):
        raise Error("Error: can't find root code path")
        # raise Error('源代码根目录不存在!')
    
    # 判断编译命令个数是否一致
    if (len(batpath) != len(outpath)) or (len(outpath) != len(tarname)):
        raise Error("Error: number of make command is wrong")
        # raise Error("编译命令集合个数不一致")
        
    # 创建目标文件临时文件夹
    romfs = g_root_dir + '\\' + ROMFS_DIR
    if os.path.exists(romfs):
        delete_allFile(romfs)
    os.mkdir(romfs)
    
    # 编译前先清空目录工程目录Debug和NonDebug所有内容
    # 需要先判断该目录是否存在
    for idx in range(len(tarname)):
        # 删除目标文件夹所有内容
        if os.path.exists(g_root_dir+'\\'+outpath[idx]):
            rmtree(g_root_dir+'\\'+outpath[idx])
        # 执行bat脚本编译工程
        if os.path.exists(g_root_dir+'\\'+dirname(batpath[idx])) == False:
            raise Error("KEIL can not find bat path")        
        os.chdir(g_root_dir+'\\'+dirname(batpath[idx]))
        os.system(g_root_dir+'\\'+batpath[idx])
        # 获取目标输出文件
        if os.path.exists(g_root_dir+'\\'+outpath[idx]) == False:
            raise Error("KEIL can not find out path")
        os.chdir(g_root_dir+'\\'+outpath[idx])
        # 替换目标文件名称
        flname = glob.glob('*.hex')
        if (len(flname) == 0) or (len(flname) > 1):
            raise Error("Error: KEIL build can't find *.hex file or many hex file")
        # 替换目标文件日期信息
        tarname[idx] = replaceDate(tarname[idx], datearg)
        os.rename(flname[0], tarname[idx])
        copy(tarname[idx], romfs)        
    print('make all success')
    
    # 拷贝目标文件到FTP共享文件夹
    if ftp_file != '':
        # 替换FTP共享文件夹目标文件名称日期
        ftp_file = replaceDate(ftp_file, datearg)
        # 拷贝目标文件到FTP共享目录
        for tar in os.listdir(romfs):
            if (ftp_file in tar) and (g_ftp_dir != None):
                if os.path.exists(g_ftp_dir):                                        
                    copy(romfs+'\\'+ftp_file, g_ftp_dir)
    
def dealZip(zipmsg = [], datearg = '', buildarg = None):
    if buildarg == None:
        return
    
    global g_root_dir # 引入外部全局变量
    global g_ftp_dir # 引入外部全局变量
    
    cpdir = '' # 拷贝文件夹名称，文件会被拷贝到该文件夹中
    zipdir = '' # zip文件夹名称，最后会压缩成对应的zip文件
    flname = '' # zip文件列表名称，文件会被拷贝到文件夹中
    nestpath = '' # 嵌套文件夹名称，递归创建文件夹
    rubbish = []
    
    # 切换到调试目录
    if (g_root_dir == None):
        raise Error("Error: can't find src code root path")
        # raise Error('源代码根目录不存在!')
    
    romfs = g_root_dir + '\\' + ROMFS_DIR
    os.chdir(romfs)
    
    # 获取所有svn文件，拷贝到临时文件目录，注意目录采用单引号或者双引号，避免被目录中的空格隔断
    # 导出单个文件用svn export命令: svn export filename dst_dir
    # 导出文件夹目录用svn checkout命令: svn checkout src_dir dst_dir
    for eachLine in zipmsg:
        lst = re.match(RE_ZIP_SVN, eachLine)
        if lst != None:
            svndir = lst.group(1)
            svndir = ' "%s" ' % svndir
            svncmd = r'svn export' + '\t' + svndir + '\t' + romfs
            output = subprocess.check_output(svncmd)
            print(output)
        
    zipname = ''
    # 递归创建zip文件夹和zip下面的压缩文件
    for eachLine in zipmsg:
        # 如果遇到ZIP_NAME则创建文件夹
        lst = re.match(RE_ZIP_NAME, eachLine)
        if lst != None:
            cpdir = lst.group(1)
            # 先更新参数日期信息
            cpdir = replaceDate(cpdir, datearg)
            # 获取zip压缩文件名称
            zipdir = cpdir
            rubbish.append(zipdir)
            # 创建多级文件夹
            if os.path.exists(cpdir) == False:
                os.mkdir(cpdir)
        # 如果遇到ZIP_END则结束打包
        lst = re.match(RE_ZIP_END, eachLine)
        if lst != None:
            zipname = zipdir+'.zip'
            zip_copy2(zipdir, zipname)
        # 收集所有的DIR目录，'_\dDIR'只能重复1次
        lst = re.match(RE_ZIP_DIR, eachLine)
        if lst != None:
            # 嵌套创建目录
            nestpath = lst.group(2)
            # 先更新参数日期信息
            nestpath = replaceDate(nestpath, datearg)
            # 递归创建多级文件夹
            if os.path.exists(nestpath) == False:
                os.makedirs(nestpath)
        # 如果遇到ZIP_FILE则将文件移动到文件夹中
        lst = re.match(RE_ZIP_FILE, eachLine)
        if lst != None:            
            flname = lst.group(1)
            # 先更新参数日期信息
            flname = replaceDate(flname, datearg)
            copy(flname, cpdir)
        # 如果遇到ZIP_DIR_NAME则切换拷贝的路径
        lst = re.match(RE_ZIP_DNAME, eachLine)
        if lst != None:
            cpdir = lst.group(1)
            # 先更新参数日期信息
            cpdir = replaceDate(cpdir, datearg)
            
    # 将最后生成的目标文件拷贝到ftp共享目录
    if g_ftp_dir != None:
        if os.path.exists(g_ftp_dir) == True:
            copy(zipname, g_ftp_dir)
            
    # 删除临时文件
    for item in rubbish:
        delete_allFile(item)
    print('zip ok')
    
def dealTag(tagmode = None, rmtag = None, datearg = '', tagmsg = []):
    global g_root_dir # 引入外部全局变量
    # 匹配tag模式正则表达式    
    if (tagmode == ARG_TAG_ALPHA):
        re_st = RE_TAG_ALPHA_ST
        re_end = RE_TAG_ALPHA_END
    elif (tagmode == ARG_TAG_BETA):
        re_st = RE_TAG_BETA_ST
        re_end = RE_TAG_BETA_END
    elif (tagmode == ARG_TAG_RELEASE):
        re_st = RE_TAG_RELEASE_ST
        re_end = RE_TAG_RELEASE_END
    else:
        raise Error("Error: tag mode is wrong")
        # raise Error('没有找到匹配的tag命令模式')
    
    # 组织所有命令参数
    stflg = False # 命令开始匹配标志
    tagflg = False # tag命令成对检查标志，true表示开始匹配，false表示结束匹配
    svnflg = False # svn命令成对检查标志，true表示开始匹配，false表示结束匹配
    arglst = []
    allcmd = []
    # 需要约束命令成对出现，如'RE_TAG_SRC_PATH'和'RE_TAG_DST_PATH'
    # 并且必须先出现'RE_TAG_SRC_PATH'
    for item in tagmsg:
        # 获取开始匹配的位置        
        lst = re.match(re_st, item)
        if lst != None:
            stflg = True
        lst = re.match(re_end, item)
        if lst != None:
            stflg = False
            break
        if stflg == False:
            continue
        
        # 匹配tag模式参数变量
        lst = re.match(RE_TAG_ARG, item)
        if lst != None:
            # 匹配'参数变量'='号左边的内容
            re_ex = re.match(r"\w*", item)
            if re_ex != None:
                subarg = []
                subarg.append(re_ex.group(0))
                subarg.append(lst.group(1))
                arglst.append(subarg)
        # 匹配tag源路径
        lst = re.match(RE_TAG_SRC_PATH, item)
        if lst != None:
            if tagflg != False:
                raise Error("Error: TAG command must be double, src path before, dst follow the next")
                # raise Error('TAG命令必须成对出现，并且源路径在前，目标路径在后')
            else:
                tagflg = True
            subcmd = []
            subcmd.append(TAG_CMD)
            subcmd.append(lst.group(1))
        # 匹配tag目标路径
        lst = re.match(RE_TAG_DST_PATH, item)
        if lst != None:
            if tagflg != True:
                raise Error("Error: TAG command must be double, src path before, dst follow the next")
                # raise Error('TAG命令必须成对出现，并且源路径在前，目标路径在后')
            else:
                tagflg = False
            subcmd.append(lst.group(1))
            allcmd.append(subcmd)
        # 匹配svn源路径
        lst = re.match(RE_TAG_SRC_SVN, item)
        if lst != None:
            if svnflg != False:
                raise Error("Error: SVN command must be double, src path before, dst follow the next")
                # raise Error('SVN命令必须成对出现，并且源路径在前，目标路径在后')
            else:
                svnflg = True
            subcmd = []
            subcmd.append(SVN_CMD)
            subcmd.append(lst.group(1))
        # 匹配svn目标路径
        lst = re.match(RE_TAG_DST_SVN, item)
        if lst != None:
            if svnflg != True:
                raise Error("Error: SVN command must be double, src path before, dst follow the next")
                # raise Error('SVN命令必须成对出现，并且源路径在前，目标路径在后')
            else:
                svnflg = False
            subcmd.append(lst.group(1))
            allcmd.append(subcmd)
     
    # 整理命令行，替换参数变量
    for item in allcmd:
        for i in range(len(item)):
            for arg in arglst:
                var = '$' + arg[0]
                if var in item[i]:
                    item[i] = item[i].replace(var, arg[1]) # 替换匹配的参数变量
                    
    # 整理命令行，替换时间参数
    for item in allcmd:
        for i in range(len(item)):
            item[i] = replaceDate(item[i], datearg)
                    
    # 顺序处理所有命令
    # 提交时必须增加日志信息，即参数-m
    # 打tag，源代码tag到beta目录，--parents创建中间目录
    # 正则表达式既可以实现字符串匹配re.match(r"xxx", yyy)，也可以实现二进制匹配re.match(b"xxx", yyy)
    # 将trunk目录tag到tags目录beta/release/test等目录
    # -m 参数必须采用双引号-m "add tag"，不能采用单引号-m 'add tag' ???
    # 检出SVN最新版本到本地路径: svncmd = r"svn checkout https://191.0.0.252:8443/svn/Personal/李迪 D:\checkout"
    for item in allcmd:
        if len(item) == 3:
            cmd = item[0]
            if cmd == TAG_CMD:
                # 如果命令中出现空格，必须采用引号括起来，注意引号的用法
                # 如下面参数传递过程中可能出现空格(srcpath和dstpath)，因此需要用引号括起来
                # 注意引号的用法，单引号中间包含双引号，这样明确标志字符串，如' "" '，双引号中内容可以包含空格
                # 打tag，源代码tag到beta目录，--parents创建中间目录
                
                # 匹配同一个项目的SVN路径，匹配格式为: xxx/svn/项目号/xxx，匹配"xxx"中间的内容
                slst = re.match(".*/svn/([^/]+).*", item[1])
                dlst = re.match(".*/svn/([^/]+).*", item[2])
                if (slst != None) and (dlst != None):
                    if slst.group(1) != dlst.group(1):
                        raise Error("Error: SVN live in different project!")
                        # raise Error("SVN路径不是位于同一个项目中!")
                else:
                    raise Error("Error: can't find SVN path")
                    # raise Error("找不到SVN路径!")
                
                # 解析TAG版本号和TAG源路径
                if '@' in item[1]:
                    [srcpath, tagrev] = item[1].split('@', 1)
                else:
                    [srcpath, tagrev] = [item[1], 'HEAD']
                
                # 根据对应版本打TAG
                srcpath = ' "%s" ' % srcpath
                dstpath = ' "%s" ' % item[2]
                
                # 如果已经存在目标路径，则先删除目标路径
                errno = False
                try:
                    # 如果存在目标路径，则打印目标路径内容
                    svncmd = r'svn list' + '\t' + dstpath
                    output = subprocess.check_output(svncmd)
                    print(output)
                    # 如果已经存在TAG目标路径，需要根据参数判断是否需要手动删除重复的TAG
                    if (rmtag == None):
                        errno = True
                    else:
                        # 已经赋予删除权限，删除目标路径
                        print("delete repeat svn path: ", item[2])
                        svncmd = r'svn delete -m "del svn path" ' + '\t' + dstpath
                        output = subprocess.check_output(svncmd)
                        print(output)
                except:
                    # 如果不能访问目标路径，则下面会自动创建目标路径
                    pass
                
                # 在try中不能使用raise，因为try本来就是判断是否合法的操作
                if errno == True:
                    raise Error("Error: already exist TAG dst path, you need to delete by hand")
                    # raise Error("已经存在TAG目标路径，需要手动进行删除!")
                
                svncmd = r'svn copy -m "create tag" --parents -r' + '\t' + tagrev + '\t' + srcpath + '\t' + dstpath
                output = subprocess.check_output(svncmd)
                print(output)
            elif cmd == SVN_CMD:
                # 上传zip包到beta目录下的"烧录程序"文件夹，必须是文件夹上传到SVN目录
                # svn import: 上传文件夹到SVN目录，没有上传单个文件到SVN的命令
                
                # 创建临时文件夹
                tmpdir = tempfile.mkdtemp()
                # 下载目标文件到临时文件夹
                # 如果路径为SVN路径，则从SVN下载文件到本地
                if ('http' in item[1]) or ('HTTP' in item[1]):
                    # 匹配同一个项目的SVN路径，匹配格式为: xxx/svn/项目号/xxx，匹配"xxx"中间的内容
                    slst = re.match(".*/svn/([^/]+).*", item[1])
                    dlst = re.match(".*/svn/([^/]+).*", item[2])
                    if (slst != None) and (dlst != None):
                        if slst.group(1) != dlst.group(1):
                            raise Error("Error: SVN live in different project!")
                            # raise Error("SVN路径不是位于同一个项目中!")
                    else:
                        raise Error("Error: can't find SVN path")
                        # raise Error("找不到SVN路径!")
                    
                    # 解析TAG版本号
                    if '@' in item[1]:
                        [svndir, svnrev] = item[1].split('@', 1)
                    else:
                        [svndir, svnrev] = [item[1], 'HEAD']
                    
                    # 上传本地文件到SVN
                    svndir = ' "%s" ' % svndir
                    svncmd = r'svn export  --force  -r' + '\t' + svnrev + '\t' + svndir + '\t' + tmpdir
                    output = subprocess.check_output(svncmd)
                    print(output)
                    # 临时文件夹作为将要上传SVN的文件夹
                    srcpath = tmpdir
                else:
                    # 判断文件夹是否存在
                    if os.path.exists(item[1]) == False:
                        raise Error("Error: SVN CMD can not local path")
                    # 如果不是服务器的FTP路径，则直接报错，避免ini文件配置错误导致上传非法的服务器目录
                    if r':\FTP_SHARE' not in item[1]:
                        raise Error("Error: can not find FTP local path")                    
                    # 服务器本地路径作为将要上传SVN的文件夹
                    srcpath = item[1]
                    
                # 将临时目录tmpdir的所有目标文件上传到SVN, 执行SVN上传文件命令
                srcpath = ' "%s" ' % srcpath
                dstpath = ' "%s" ' % item[2]
                svncmd = r'svn import -m "import file"' + '\t' + srcpath + '\t' + dstpath
                output = subprocess.check_output(svncmd)
                print(output)
                
                # 删除临时文件夹
                os.chdir(tmpdir)
                os.chdir('..')
                if os.path.exists(tmpdir):
                    print("remove tmp dir:", tmpdir)
                    rmtree(tmpdir)
    print('TAG cmd finish.')
    
if __name__ == '__main__':
    print('Jenkins start...')
    
    # 获取入口参数
    # test test test
    # arg = ['-beta', '-date@2014-02-14']
    arg = sys.argv[0:]
    # 判断ini文件是SVN路径、服务器本地文件夹、文件名称
    if len(arg) < 2:
        raise Error("Error: too few arg, please check dir for *.ini file.")
        # raise Error("入口参数太少，请执行脚本执行文件和配置文件路径信息")
    
    # 获取TAG入口参数和时间日期入口参数
    datearg = '' # 日期时间信息
    tagmode = ARG_TAG_NONE # 打TAG类型
    rmtag = None # 删除重复tag目标路径
    buildarg = None # 编译和打包选项
    for item in arg:
        for subarg in ARG_TBL:
            # 解析tag参数或者日期参数
            if subarg[0] in item:
                # 获取日期时间信息
                if (subarg[1] == ARG_DATE):
                    datearg = item.replace(subarg[0], '')
                # 获取是否删除重复TAG参数
                elif (subarg[1] == ARG_TAG_REMOVE):
                    rmtag = subarg[1]
                # 判断TAG版本信息类型
                elif ((subarg[1] == ARG_TAG_ALPHA) or (subarg[1] == ARG_TAG_BETA) or (subarg[1] == ARG_TAG_RELEASE)):
                    tagmode = subarg[1]
                # 判断是否需要编译和打包
                elif (subarg[1] == ARG_BUILD):
                    buildarg = subarg[1]            
                # 找不到命令参数
                else:
                    raise Error("Error: Jenkins can't find command in *.ini file")
                    # raise Error("找不到命令信息")
    
    # 获取配置文件命令信息
    if ('http' in arg[1]) or ('HTTP' in arg[1]):
        # 创建临时文件夹
        tmpdir = tempfile.mkdtemp()
        srcpath = ' "%s" ' % arg[1]
        dstpath = ' "%s" ' % tmpdir
        
        # 从SVN下载ini文件到临时文件夹
        svncmd = r'svn export' + '\t' + srcpath + '\t' + dstpath
        output = subprocess.check_output(svncmd)
        print(output)
        
        # 获取ini配置文件信息
        os.chdir(tmpdir)
        flname = glob.glob('*.ini')        
        if (len(flname) == 0) or (len(flname) > 1):
            raise Error("Error: can't find *.ini file or too many *.ini file")
            # raise Error('找不到ini配置文件')
        allcmd = cmGetCfgInfo(flname[0])
        
        # 删除临时文件夹
        os.chdir('..')
        if os.path.exists(tmpdir):
            print("remove tmp dir:", tmpdir)
            rmtree(tmpdir)
    else:
        # 判断入口参数是服务器本地路径还是文件名称
        path = dirname(arg[1])
        # 如果找不到配置文件本地路径则采用脚本执行文件当前路径
        if re.match('\s*$', path) != None:
            path = dirname(arg[0])
        # 跳转配置文件目录，读取当前目录ini配置文件信息
        # 找到匹配的ini文件
        flname = find_files(path, basename(arg[1]))
        if (len(flname)) == 0 or (len(flname)) > 1:
            raise Error("Error: can't find *.ini file or too many *.ini file")
        allcmd = cmGetCfgInfo(flname[0])
        
    # 处理命令集合
    for item in allcmd:
        if 'vxworks_build' in item[0]:
            dealVxBuild(item, buildarg)
        elif 'iar_build' in item[0]:
            dealIarBuild(item, datearg, buildarg)
        elif 'keil_build' in item[0]:
            dealKeilBuild(item, datearg, buildarg)
        elif 'zip' in item[0]:
           dealZip(item, datearg, buildarg)
        elif 'tag' in item[0]:
            if tagmode != ARG_TAG_NONE:
                dealTag(tagmode, rmtag, datearg, item)
            