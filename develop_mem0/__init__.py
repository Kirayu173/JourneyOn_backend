import importlib.metadata

__version__ = importlib.metadata.version("mem0ai")

from develop_mem0.client.main import AsyncMemoryClient, MemoryClient  # noqa
from develop_mem0.memory.main import AsyncMemory, Memory  # noqa
