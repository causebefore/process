from setuptools import setup, Extension
from Cython.Distutils import build_ext
import shutil
import os
import sys
import time

# python setup.py build_ext --inplace
arg = ''
print('---------------------------------------------------')
print('开始打包')
print('---------------------------------------------------')
print('请输入打包的模式：')
state = input('是否打包为一个文件：\n1.是\n2.否\n')
if state == '1':
    arg += '-F'
state = input('是否隐藏命令行窗口：\n1.隐藏\n2.不隐藏\n')
if state == '1':
    arg += ' -w'
state = input('是否使用图标：\n1.使用\n2.不使用\n')
if state == '1':
    icon = input('请输入图标的路径：')
    arg += ' -i=' + icon

stop_line = 'DEBUG = True\n'
change_line = 'DEBUG = False\n'

t1 = time.time()

# 创建setup文件夹
if not os.path.exists('setup'):
    os.makedirs('setup')
else:
    shutil.rmtree('setup')
    os.makedirs('setup')
print('---------------------------------------------------')
print('创建setup文件夹')
print('---------------------------------------------------')

try:
    with open('main.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if i > 50:
                print('error: 未在前50行找到 DEBUG 标志')
                sys.exit(1)
            if line.startswith(stop_line):
                lines[i] = change_line
                break
    with open('main.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

    import_dir = []
    for i in range(i):
        print(lines[i])
        import_dir.append(lines[i])

    import_dir.append('from main import main\n')
    import_dir.append('\n')
    import_dir.append('if __name__ == \'__main__\':\n')
    import_dir.append('    main()\n')
    print('---------------------------------------------------')
    print('创建pack.py文件')
    print('---------------------------------------------------')
    with open('setup/pack.py', 'w', encoding='utf-8') as f:
        f.writelines(import_dir)

    print('---------------------------------------------------')
    print('开始编译main.py')
    print('---------------------------------------------------')
    # 编译main.py为pyd文件
    ext_modules = [Extension('main', ['main.py'])]
    setup(
        cmdclass={'build_ext': build_ext},
        ext_modules=ext_modules
    )

    # 查找编译后的pyd文件
    for root, dirs, files in os.walk(os.getcwd()):
        for file in files:
            if file.endswith('.pyd'):
                print(os.path.join(root, file))
                # 重命名pyd文件
                os.rename(os.path.join(root, file), os.path.join(root, 'main.pyd'))
                # 移动pyd文件到setup文件夹
                shutil.move(os.path.join(root, 'main.pyd'), os.path.join('setup', 'main.pyd'))
                break

    with open('main.py', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith(change_line):
                lines[i] = stop_line
                break
    with open('main.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print('---------------------------------------------------')
    print('开始打包')
    print('---------------------------------------------------')
    #使用pyinstaller打包
    os.system('pyinstaller ' + arg + ' main.py')
    # 删除spec文件
    os.remove('main.spec')
    #删除.c文件
    os.remove('main.c')
    #删除build文件夹
    shutil.rmtree('build')

    #压缩dist文件夹
    shutil.make_archive('dist', 'zip', 'dist')
    t2 = time.time()
    print('---------------------------------------------------')
    print('打包成功')
    print('用时：%.2f s' % (t2 - t1))
except Exception as e:

    with open('main.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith(change_line):
                lines[i] = stop_line
                break
    with open('main.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    shutil.rmtree('build')
