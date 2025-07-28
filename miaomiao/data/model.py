# 与neo4j 交互
from typing import List, Optional, Dict
from miaomiao.config.config import settings
from miaomiao.config.constant import PathType
from py2neo import Graph, NodeMatcher, Node
from miaomiao.data.file_model import DirHandler



class DatabaseHandler:
    """
    用于将数据存入和读取。
    支持一下功能
    1. 创建node
    可用于顶级node，只创建node。
    2. 创建中间目录node
    创建node，然后建立该node与其他node的关系。
    3. 创建node
    用户创建文件node，建立node与其他node的关系。
    """
    def __init__(self):
        self.graph = Graph(settings.neo4j.profile, auth=settings.neo4j.auth)
        self.matcher = NodeMatcher(self.graph)
        self.base_nodes = self.create_base_node()

    def create_base_node(self):
        # 查看数据库中base node 是否存在，不存在就建立base node
        base_nodes = []
        tx = self.graph.begin()
        for _name in settings.top_field:
            _base_node = self.matcher.match(PathType.directory.value, name = _name ).first()
            if _base_node is None:
                _base_node = Node(PathType.directory.value, name=_name)
                self.graph.create(_base_node)
            base_nodes.append(_base_node)
        self.graph.commit(tx)
        return base_nodes

    # def get_node_from_file_handler(self, ) -> Optional[Node]:
    #     if


if __name__ == '__main__':
    db = DatabaseHandler()
    print(db.base_nodes)