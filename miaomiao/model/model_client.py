
import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict
from pydantic import BaseModel

from autogen_core.tools import FunctionTool
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

from miaomiao.data.file_model import DirHandler, FileHandler

from miaomiao.config.config import settings

from autogen_core.models import UserMessage

current_path = os.path.dirname(os.path.abspath(__file__))

class DataMapping(BaseModel):
    new: str = ""
    old: str = ""

class AgentResponse(BaseModel):
    response: List[DataMapping]

model_client = OpenAIChatCompletionClient(model = settings.ai.model, api_key = settings.ai.api_key,
                                          base_url = settings.ai.base_url, model_info=settings.ai.model_info.model_dump())


result = model_client.create([UserMessage(content="哈喽，是否已经正常连接。", source="user")])

def get_sub_files(target_path: str):
    """获取target_path下的文件和目录"""
    _files = []
    _dirs = []
    for child in Path(target_path).iterdir():
        if child.is_dir():
            _dirs.append(str(child))
        if child.is_file():
            _files.append(str(child))
    print(target_path)
    return _files, _dirs

with open(Path(current_path).parent.joinpath("prompt", "multi_step_analysis.txt"), encoding="utf-8") as f:
    custom_system_message = f.read()
# primary_agent = AssistantAgent(name = "primary", model_client =model_client, tools = [FunctionTool(name="get_sub_fiels",
#             func=get_sub_files, strict=True, description="获取目录下所有的文件")],
#                        system_message = custom_system_message,
#                        model_client_stream=True)
primary_agent = AssistantAgent(name = "primary", model_client =model_client, tools = [FunctionTool(name="get_sub_fiels",
            func=get_sub_files, strict=True, description="获取目录下所有的文件")],
                       system_message = "你是一个助理，根据任务进行处理。",
                       model_client_stream=True)

critic_agent = AssistantAgent(name = "critic", model_client =model_client,
            #                   tools = [FunctionTool(name="get_sub_fiels",
            # func=get_sub_files, strict=True, description="获取目录下所有的文件")],
                       system_message = custom_system_message)
text_termination = TextMessageTermination("任务完成。")

team = RoundRobinGroupChat([primary_agent, critic_agent], termination_condition=text_termination)
def parse_result(content):
    content = content[content.find("```json")+7:]
    content = content[:content.find("```")]
    return json.loads(content)

# async def collating(handler: DirHandler):
#     content = f"工作目录：{handler.work_path}, 目录下文件： {handler.files}, 分配目标目录{settings.output_dir}. "
#     await team.reset()
    # result = await team.run(task=content)
    # if result.finish_reason != "stop":
    #     raise ValueError(result.finish_reason)
    # ar = AgentResponse(response=parse_result(result.content))
    # ar.response[0].old = handler.files[0]
    # return ar
    # async for message in team.run_stream(task=content):
    #     if isinstance(message, TaskResult):
    #         print("stop reason", message.stop_reason)
    #     else:
    #         print('-------------', message.source, '---------------------')
    #         print(message.content)
    # print('finished')

async def collating(handler: FileHandler):
    first_content = (f"工作目录：{handler.work_path}, 请对这个文件进行分析： {handler.file_path}, 分配目标目录{settings.output_dir}."
               f"请按照步骤一，给出第一步返回结果。")
    result = await critic_agent.run(task=first_content)
    _file_class = json.loads(result.messages[-1].content)["res"]
    _exists_class = [c.stem for c in settings.output_dir.iterdir() if c.is_dir()]
    if _file_class not in _exists_class:
        _file_class_path = settings.output_dir.joinpath(_file_class)
        second_content = (f"工作目录：{handler.work_path},请对这个文件进行分析： {handler.file_path},分配目标目录{settings.output_dir}."
                   f"步骤一分类结果：{result.messages[-1].content}，第一步分配的目录不存在，请按照步骤二，给出第二步返回结果。")
    else:
        second_content = (f"工作目录：{handler.work_path}, 请对这个文件进行分析： {handler.file_path},分配目标目录{settings.output_dir}."
                   f"步骤一分类结果：{result.messages[-1].content}，第一步分配的目录已经存在"
                   f"{_file_class} 目录下文件：{get_sub_files(settings.output_dir)}. 请按照步骤二，给出第二步返回结果。")
    result = await critic_agent.run(task=second_content)
    _file_new_sub_path = json.loads(result.messages[-1].content)["res"]
    _file_new_path = settings.output_dir.joinpath(_file_new_sub_path)
    if not _file_new_path.exists():
        content = (f"工作目录：{handler.work_path},请对这个文件进行分析： {handler.file_path}, 分配目标目录{settings.output_dir}."
                   f"{first_content},步骤一结果：{result.messages[-1].content}，{second_content}步骤二结果：{result.messages[-1].content}。检测发现步骤二的分类出来的"
                   f"文件并不存在，请给出步骤三的结果。")
    else:
        content = (f"工作目录：{handler.work_path},请对这个文件进行分析： {handler.file_path}, 分配目标目录{settings.output_dir}."
                   f"{first_content}步骤一结果：{result.messages[-1].content}，{second_content}步骤二结果：{result.messages[-1].content}。检测发现步骤二的分类出来的"
                   f"文件存在，并有以下文件{get_sub_files(_file_new_path)}，请给出步骤三的结果。")
    result = await critic_agent.run(task=content)
    _new_path = json.loads(result.messages[-1].content)["res"]
    return  AgentResponse(response=[DataMapping(old=str(handler.file_path), new=_new_path)])
    # if result.finish_reason != "stop":
    #     raise ValueError(result.finish_reason)
    #
    # ar = AgentResponse(response=parse_result(result.content))
    # ar.response[0].old = handler.files[0]
    # return ar

async def main():
    # result = await model_client.create([UserMessage(content="What is the capital of France?", source="user")])
    # print(result)
    # res = await model_client.close()
    # print(res)
    # await Console(agent.run_stream(task = 'whatis太和weather '))
    # await model_client.close()
    # result = await agent.run(task="Find information on AutoGen.")
    df = DirHandler(Path(r"E:\MyDownloads\Download"), settings.analysis_dir[0])
    res = await collating(df)
    print(res)

if __name__ == '__main__':

    asyncio.run(main())