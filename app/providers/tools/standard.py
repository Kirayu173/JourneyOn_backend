from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Type

from pydantic import BaseModel, Field

class _StructuredToolFallback:
    """Lightweight fallback StructuredTool implementation."""

    def __init__(
        self,
        *,
        func: Callable[..., Any] | None = None,
        coroutine: Callable[..., Awaitable[Any]] | None = None,
        name: str | None = None,
        description: str = "",
        args_schema: Type[BaseModel] | None = None,
        **_: Any,
    ) -> None:
        self.func = func
        self.coroutine = coroutine
        self.name = name or self.__class__.__name__
        self.description = description
        self.args_schema = args_schema

    def invoke(self, input: Mapping[str, Any] | Any) -> Any:
        if self.coroutine is not None:
            raise RuntimeError("async_only_tool")
        if self.func is None:
            raise NotImplementedError("StructuredTool func not implemented")
        if isinstance(input, Mapping):
            return self.func(**dict(input))
        return self.func(input)

    async def ainvoke(self, input: Mapping[str, Any] | Any) -> Any:
        if self.coroutine is None:
            raise NotImplementedError("StructuredTool coroutine not implemented")
        if isinstance(input, Mapping):
            return await self.coroutine(**dict(input))
        return await self.coroutine(input)

    def run(self, input: Mapping[str, Any] | Any) -> Any:
        return self.invoke(input)

    async def arun(self, input: Mapping[str, Any] | Any) -> Any:
        return await self.ainvoke(input)


try:
    from langchain_core.tools import StructuredTool as _StructuredTool
except ImportError:  # pragma: no cover - fallback for environments without langchain_core
    _StructuredTool = _StructuredToolFallback


class StandardToolInput(BaseModel):
    """Default input schema for JourneyOn standard tools."""

    payload: Dict[str, Any] = Field(default_factory=dict, description="工具执行所需的上下文参数。")


class StandardStructuredTool(_StructuredTool):
    """Skeleton class for building LangGraph-compatible structured tools."""

    name: str = "journeyon_standard_tool"
    description: str = "JourneyOn 标准化工具骨架，用于继承实现具体工具逻辑。"
    args_schema: Type[BaseModel] = StandardToolInput

    def __init__(
        self,
        *,
        func: Callable[..., Any] | None = None,
        coroutine: Callable[..., Awaitable[Any]] | None = None,
        return_direct: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        if func is None and coroutine is None:
            func = self._run
        super().__init__(
            func=func,
            coroutine=coroutine,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
            return_direct=return_direct,
            metadata=metadata,
            tags=tags,
            **kwargs,
        )

    def _run(self, **kwargs: Any) -> Any:  # pragma: no cover - to be implemented by subclasses
        raise NotImplementedError("StandardStructuredTool._run must be implemented by subclasses")

    async def _arun(self, **kwargs: Any) -> Any:
        return self._run(**kwargs)


__all__ = ["StandardStructuredTool", "StandardToolInput"]
