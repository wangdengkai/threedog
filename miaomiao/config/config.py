import os
from typing import List
from pathlib import Path

import miaomiao
from pydantic import BaseModel, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource, TomlConfigSettingsSource

if miaomiao.__file__:
    install_path = Path(miaomiao.__file__)
else:
    install_path = Path(__file__).parent.parent

class ModelInfo(BaseModel):
    vision: bool = False
    function_calling: bool = False
    json_output: bool = True
    family: str = "gpt-4"
    structured_output: bool = True
    multiple_system_messages: bool = False

class AIConfig(BaseModel):
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    model_info: ModelInfo = ModelInfo()

class DataConfig(BaseModel):
    profile: AnyUrl = "neo4j://127.0.0.1:7687"
    auth: tuple = ("neo4j", "stu_example")

class Settings(BaseSettings):
    analysis_dir: List[Path] = ["~"]
    top_field: List[str] = ["工作", "生活"]
    neo4j: DataConfig = DataConfig()
    ai: AIConfig = AIConfig()
    output_dir: Path = Path("~").expanduser()


    model_config = SettingsConfigDict(toml_file = [install_path.joinpath("config.toml"), '~/.miaomiao/config.toml'])

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)


settings = Settings()