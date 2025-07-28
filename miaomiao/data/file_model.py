from pydantic import BaseModel
from pathlib import Path
from typing import List, Tuple
from miaomiao.config.constant import PathType

class FileInfo(BaseModel):
    work_path: Path
    extension: str
    create_time: float
    file_name: str
    file_path: Path   # 相对work_path
    # peak_dirs: List[str]
    # peak_files: List[str]

class DirInfo(BaseModel):
    work_path: Path
    create_time: float
    file_name: str
    file_path: Path
    sub_dir_name: List[str]
    sub_file_name: List[str]
    # peak_dirs: List[str]
    # peak_files: List[str]

class FileHandler:
    path_type = PathType.file.value
    def __init__(self, file_path: Path, work_path: Path):
        self.file_path = file_path
        self.work_path = work_path
        # self.peak_dirs = peak_dirs
        # self.peak_files = peak_files
        # if self.peak_dirs is None and self.peak_files is None:
        #     self.peak_dirs, self.peak_files = [], []
        #     if self.file_path.parent == self.file_path:
        #         return
        #     for child in self.file_path.parent.iterdir():
        #         if child.is_dir():
        #             self.peak_dirs.append(child.name)
        #         if child.is_file():
        #             self.peak_files.append(child.name)



    # @property
    # def info(self) -> FileInfo:
    #     file_name = self.file_path.name
    #     extension = self.file_path.suffix
    #     create_time = self.file_path.stat().st_ctime
    #     return FileInfo(work_path=self.work_path, extension=extension, create_time=create_time,
    #                     file_name=file_name, file_path=self.file_path.relative_to(self.work_path),
    #                     peak_dirs=self.peak_dirs, peak_files=self.peak_files)


class DirHandler(FileHandler):
    path_type = PathType.directory.value
    def __init__(self, file_path: Path, work_path: Path, files: List[str]=None):
        super().__init__(file_path, work_path)
        self.files = files


    @property
    def info(self) -> DirInfo:
        file_name = self.file_path.name
        create_time = self.file_path.stat().st_ctime
        sub_dir_name = []
        sub_file_name = []
        for root, dirs, files in self.file_path.walk():
            if root == self.file_path:
                sub_dir_name = dirs
                sub_file_name = files
                break
        return DirInfo(work_path=self.work_path, create_time=create_time, file_name=file_name, file_path=self.file_path,
                       sub_dir_name=sub_dir_name, sub_file_name=sub_file_name)

