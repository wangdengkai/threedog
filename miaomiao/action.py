import os
from pathlib import Path
from typing import List, Optional



from pydantic import BaseModel, Field
from miaomiao.config.config import settings
from miaomiao.model.model_client import AgentResponse

class ActionResult(BaseModel):
    old_not_exists: Optional[List] = Field(default_factory=list)# 旧文件不存在的
    new_exists: Optional[List] = Field(default_factory=list) # 新文件已存在


class ModelAction:
    def __init__(self):
        self.target_path = settings.output_dir

    def create_soft_link(self, result: AgentResponse):
        action_result = ActionResult()
        for _data in result.response:
            # 检测是否存在
            _old_path = Path(_data.old)
            if _old_path.is_dir():
                continue
            if not _old_path.exists():
                action_result.old_not_exists.append(_old_path)
                continue
            _new_path = self.target_path.joinpath(_data.new)
            if _new_path.exists():
                action_result.new_exists.append(_new_path)
                continue
            # 创建软连接
            _new_path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(_old_path, _new_path)
        return action_result

