from enum import Enum



class PathType(Enum):
    # 路径类别，时目录还是文件
    directory = "directory"
    file = "file"
