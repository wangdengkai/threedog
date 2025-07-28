import os

from miaomiao.action import ModelAction
from miaomiao.data.model import DatabaseHandler
from miaomiao.data.file_model import FileHandler, DirHandler
from miaomiao.model.model_client import collating


class Controller:
    def __init__(self, database_handler: DatabaseHandler = None, action: ModelAction = None):
        self.database_handler = database_handler
        self.action = action


    async def handler_dir(self, dir_handler: DirHandler):
        # 对目录进行处理
        # 获取是否有这个node
        res = await collating(dir_handler)
        self.action.create_soft_link(res)



    # def handler_file(self, file_handler: FileHandler):
        # 对文件进行处理