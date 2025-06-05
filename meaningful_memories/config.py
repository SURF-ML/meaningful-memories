import os

import yaml

from . import here


class Config:
    def __init__(self, config_path=os.path.join(here, "configs/config.yaml")):
        with open(config_path, "r") as file:
            config_data = yaml.safe_load(file)

        self._load_config(config_data)

    def _load_config(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, ConfigItem(value))
            else:
                setattr(self, key, value)


class ConfigItem:
    """Helper class to turn a dictionary into an object with attribute access."""

    def __init__(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(
                    self, key, ConfigItem(value)
                )  # Recursively create nested objects
            else:
                setattr(self, key, value)

    def __repr__(self):
        return str(self.__dict__)


config = Config()
