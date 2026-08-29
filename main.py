
import asyncio
from pathlib import Path
from miaomiao.config.config import settings
from miaomiao.data.file_model import FileHandler, DirHandler
from miaomiao.data.model import DatabaseHandler
from miaomiao.action import ModelAction
from miaomiao.control import Controller

already = []

for root, dirs, files in settings.output_dir.walk():
    for _file in files:
        _a_path = root.joinpath(_file)
        if _a_path.is_symlink():
            already.append(str(_a_path.resolve()))


async def analysis_work():
    """
    分析工作目录的数据。
    1. 读取工作目录的文件
    2. 提取该文件的相关属性
    3. 提取已有数据，一起对该文件进行大模型分析
    4. 将该数据录入图数据库
    5. 分析下一个数据
    :return:
    """
    # dh = DatabaseHandler()
    # controller = Controller(dh)
    controller = Controller(action=ModelAction())


    for _work_dir in settings.analysis_dir:
        _cur_path = Path(_work_dir)
        if not _cur_path.exists():
            continue
        for root, dirs, files in _cur_path.walk():
            # for _dir in dirs:
            #     _target_path = root.joinpath(_dir)
            #     if _target_path.name.startswith("."):
            #         continue
            #     if _target_path in already:
            #         continue
            #
            #     dh = DirHandler(_target_path, _cur_path, dirs, files)
            #     res = await controller.handler_dir(dh)
            #     print(res)
            #     already.append(_target_path)
            if root.name.startswith("."):
                continue
            if root.full_match("**/.*/"):
                continue
            if not files:
                continue
            for _file in files:
                # dh = DirHandler(root, _cur_path, files=[root.joinpath(_file)])
                target_file = root.joinpath(_file)
                if str(target_file) in already:
                    continue
                fh = FileHandler(target_file, _cur_path)
                res = await controller.handler_dir(fh)
                print(res)
                already.append(str(target_file))
            # for _file in files:
            #     _target_path = root.joinpath(_file)
            #     if _target_path in already:
            #         continue
            #     if _target_path.
            #     fh = FileHandler(_target_path, _cur_path, dirs, files)
            #     res = await controller.handler_file(fh)
            #     already.append(_target_path)





def main():
    print("Hello from miaomiao!")
    # df = DirHandler(settings.analysis_dir)



if __name__ == "__main__":
    # main()
    asyncio.run(analysis_work())