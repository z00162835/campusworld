"""
Game package loader with F01 V2 runtime contracts.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys
import threading
from typing import Any, Dict, List, Optional

import yaml

from .base import BaseGame
from .runtime_store import (
    OperationResult,
    WorldErrorCode,
    WorldInstallerService,
    WorldRuntimeRepository,
    WorldRuntimeStatus,
)
from app.core.paths import get_backend_root, get_project_root


class GameLoader:
    """World package loader with persistent runtime state."""

    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger(f"game_engine.{engine.name}.loader")
        self.backend_root = get_backend_root()
        self.project_root = get_project_root()
        self.search_paths = [
            self.backend_root / "app" / "games",
            self.project_root / "games",
            self.backend_root / "games",
        ]
        self.loaded_games: Dict[str, BaseGame] = {}
        self.game_modules: Dict[str, Any] = {}
        self._op_locks: Dict[str, threading.Lock] = {}
        self.repository = WorldRuntimeRepository()
        self.service = WorldInstallerService(self.repository)

    def _result(
        self,
        ok: bool,
        world_id: str,
        status_before: str,
        status_after: str,
        message: str,
        error_code: Optional[WorldErrorCode] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> OperationResult:
        return OperationResult(
            ok=ok,
            world_id=world_id,
            status_before=status_before,
            status_after=status_after,
            message=message,
            error_code=error_code.value if error_code else None,
            details=details or {},
        )

    def _get_world_lock(self, world_id: str) -> threading.Lock:
        if world_id not in self._op_locks:
            self._op_locks[world_id] = threading.Lock()
        return self._op_locks[world_id]

    def get_runtime_state(self, world_id: str) -> Dict[str, Any]:
        return self.repository.get_state(world_id)

    def discover_games(self) -> List[str]:
        available_games: List[str] = []
        for search_path in self.search_paths:
            if not (search_path.exists() and search_path.is_dir()):
                continue
            try:
                for game_dir in search_path.iterdir():
                    if not game_dir.is_dir():
                        continue
                    if self._is_valid_game_directory(game_dir):
                        if game_dir.name not in available_games:
                            available_games.append(game_dir.name)
            except Exception as e:
                self.logger.error(f"搜索路径 {search_path} 时出错: {e}")
        return available_games

    def _is_valid_game_directory(self, game_dir: Path) -> bool:
        required = ["__init__.py", "game.py", "manifest.yaml"]
        for filename in required:
            if not (game_dir / filename).exists():
                return False
        manifest = self._load_manifest(game_dir)
        if not manifest:
            return False
        required_manifest = ["world_id", "version", "api_version", "data_dir"]
        return all(manifest.get(k) for k in required_manifest)

    def _load_manifest(self, game_dir: Path) -> Optional[Dict[str, Any]]:
        manifest_path = game_dir / "manifest.yaml"
        if not manifest_path.exists():
            return None
        try:
            content = manifest_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
            if not isinstance(data, dict):
                return None
            return data
        except Exception as e:
            self.logger.error(f"读取 manifest 失败: {manifest_path} err={e}")
            return None

    def _find_game_path(self, game_name: str) -> Optional[Path]:
        for search_path in self.search_paths:
            game_path = search_path / game_name
            if game_path.exists() and game_path.is_dir():
                return game_path
        return None

    def _load_game_module(self, game_name: str, game_path: Path) -> Optional[Any]:
        try:
            if self.backend_root / "app" / "games" in game_path.parents:
                module_name = f"app.games.{game_name}"
                app_dir = str(self.backend_root / "app")
                if app_dir not in sys.path:
                    sys.path.insert(0, app_dir)
            else:
                module_name = f"games.{game_name}"
                games_parent = str(game_path.parent)
                if games_parent not in sys.path:
                    sys.path.insert(0, games_parent)
            if module_name in sys.modules:
                del sys.modules[module_name]
            spec = importlib.util.spec_from_file_location(module_name, game_path / "__init__.py")
            if not (spec and spec.loader):
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            self.logger.error(f"加载场景模块 '{game_name}' 失败: {e}")
            return None

    def _create_game_instance(self, game_name: str, game_module: Any) -> Optional[BaseGame]:
        try:
            fn = getattr(game_module, "get_game_instance", None)
            if not callable(fn):
                self.logger.error(f"场景模块 '{game_name}' 缺少可调用 get_game_instance")
                return None
            instance = fn()
            return instance
        except Exception as e:
            self.logger.error(f"创建场景实例 '{game_name}' 失败: {e}")
            return None

    def load_game(self, game_name: str) -> Dict[str, Any]:
        state_before = self.repository.get_state(game_name)["status"]
        lock = self._get_world_lock(game_name)
        if not lock.acquire(blocking=False):
            return self._result(
                False,
                game_name,
                state_before,
                state_before,
                "world operation in progress",
                WorldErrorCode.WORLD_BUSY,
            ).to_dict()

        try:
            if game_name in self.loaded_games:
                return self._result(
                    False,
                    game_name,
                    state_before,
                    state_before,
                    "world already loaded in runtime",
                    WorldErrorCode.WORLD_STATE_CONFLICT,
                ).to_dict()

            def _run(job_id: str) -> OperationResult:
                game_path = self._find_game_path(game_name)
                if not game_path:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        f"world package '{game_name}' not found",
                        WorldErrorCode.WORLD_NOT_FOUND,
                    )
                manifest = self._load_manifest(game_path)
                if not manifest:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "manifest.yaml missing or invalid",
                        WorldErrorCode.WORLD_MANIFEST_INVALID,
                    )
                required = ["world_id", "version", "api_version", "data_dir"]
                if not all(manifest.get(k) for k in required):
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "manifest required fields missing",
                        WorldErrorCode.WORLD_MANIFEST_INVALID,
                        details={"manifest_required": required},
                    )
                if str(manifest["world_id"]) != game_name:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "manifest world_id mismatch",
                        WorldErrorCode.WORLD_MANIFEST_INVALID,
                    )

                module = self._load_game_module(game_name, game_path)
                if not module:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "failed to import world module",
                        WorldErrorCode.WORLD_LOAD_FAILED,
                    )
                game_instance = self._create_game_instance(game_name, module)
                if not game_instance:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "failed to create game instance",
                        WorldErrorCode.WORLD_LOAD_FAILED,
                    )

                initialize = getattr(game_instance, "initialize_game", None)
                if callable(initialize) and not initialize():
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "initialize_game returned false",
                        WorldErrorCode.WORLD_LOAD_FAILED,
                    )
                if not game_instance.start():
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "game start failed",
                        WorldErrorCode.WORLD_LOAD_FAILED,
                    )
                if not self.engine.register_game(game_instance):
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "engine register failed",
                        WorldErrorCode.WORLD_LOAD_FAILED,
                    )

                self.loaded_games[game_name] = game_instance
                self.game_modules[game_name] = module
                return self._result(
                    True,
                    game_name,
                    state_before,
                    WorldRuntimeStatus.INSTALLED.value,
                    "world loaded",
                    details={
                        "version": str(manifest.get("version")),
                        "manifest": manifest,
                        "job_id": job_id,
                    },
                )

            try:
                result = self.service.run_with_job(
                    world_id=game_name,
                    action="load",
                    status_before=state_before,
                    enter_status=WorldRuntimeStatus.LOADING.value,
                    exec_fn=_run,
                )
                return result.to_dict()
            except Exception as e:
                return self._result(
                    False,
                    game_name,
                    state_before,
                    WorldRuntimeStatus.BROKEN.value,
                    f"persist runtime state failed: {e}",
                    WorldErrorCode.WORLD_DB_WRITE_FAILED,
                ).to_dict()
        finally:
            lock.release()

    def unload_game(self, game_name: str) -> Dict[str, Any]:
        state_before = self.repository.get_state(game_name)["status"]
        lock = self._get_world_lock(game_name)
        if not lock.acquire(blocking=False):
            return self._result(
                False,
                game_name,
                state_before,
                state_before,
                "world operation in progress",
                WorldErrorCode.WORLD_BUSY,
            ).to_dict()

        try:
            def _run(job_id: str) -> OperationResult:
                game_instance = self.loaded_games.get(game_name)
                if not game_instance:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "world is not loaded",
                        WorldErrorCode.WORLD_NOT_INSTALLED,
                    )

                try:
                    if not game_instance.stop():
                        return self._result(
                            False,
                            game_name,
                            state_before,
                            WorldRuntimeStatus.FAILED.value,
                            "world stop failed",
                            WorldErrorCode.WORLD_UNLOAD_FAILED,
                        )
                    if not self.engine.unregister_game(game_name):
                        return self._result(
                            False,
                            game_name,
                            state_before,
                            WorldRuntimeStatus.FAILED.value,
                            "engine unregister failed",
                            WorldErrorCode.WORLD_UNLOAD_FAILED,
                        )
                    self.loaded_games.pop(game_name, None)
                    self.game_modules.pop(game_name, None)
                    return self._result(
                        True,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.NOT_INSTALLED.value,
                        "world unloaded",
                        details={"job_id": job_id},
                    )
                except Exception as e:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        f"unload exception: {e}",
                        WorldErrorCode.WORLD_UNLOAD_FAILED,
                    )

            try:
                result = self.service.run_with_job(
                    world_id=game_name,
                    action="unload",
                    status_before=state_before,
                    enter_status=WorldRuntimeStatus.UNLOADING.value,
                    exec_fn=_run,
                )
                return result.to_dict()
            except Exception as e:
                return self._result(
                    False,
                    game_name,
                    state_before,
                    WorldRuntimeStatus.BROKEN.value,
                    f"persist runtime state failed: {e}",
                    WorldErrorCode.WORLD_DB_WRITE_FAILED,
                ).to_dict()
        finally:
            lock.release()

    def reload_game(self, game_name: str) -> Dict[str, Any]:
        state_before = self.repository.get_state(game_name)["status"]
        lock = self._get_world_lock(game_name)
        if not lock.acquire(blocking=False):
            return self._result(
                False,
                game_name,
                state_before,
                state_before,
                "world operation in progress",
                WorldErrorCode.WORLD_BUSY,
            ).to_dict()

        try:
            def _run(job_id: str) -> OperationResult:
                game_instance = self.loaded_games.get(game_name)
                if not game_instance:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "world is not loaded",
                        WorldErrorCode.WORLD_RELOAD_FAILED,
                    )
                try:
                    if not game_instance.stop():
                        return self._result(
                            False,
                            game_name,
                            state_before,
                            WorldRuntimeStatus.FAILED.value,
                            "reload failed while stopping current world",
                            WorldErrorCode.WORLD_RELOAD_FAILED,
                        )
                    if not self.engine.unregister_game(game_name):
                        return self._result(
                            False,
                            game_name,
                            state_before,
                            WorldRuntimeStatus.FAILED.value,
                            "reload failed while unregistering current world",
                            WorldErrorCode.WORLD_RELOAD_FAILED,
                        )
                    self.loaded_games.pop(game_name, None)
                    self.game_modules.pop(game_name, None)
                except Exception as e:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        f"reload unload phase exception: {e}",
                        WorldErrorCode.WORLD_RELOAD_FAILED,
                    )

                game_path = self._find_game_path(game_name)
                if not game_path:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        f"world package '{game_name}' not found",
                        WorldErrorCode.WORLD_NOT_FOUND,
                    )
                manifest = self._load_manifest(game_path)
                required = ["world_id", "version", "api_version", "data_dir"]
                if not manifest or not all(manifest.get(k) for k in required):
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "manifest required fields missing",
                        WorldErrorCode.WORLD_MANIFEST_INVALID,
                    )
                module = self._load_game_module(game_name, game_path)
                if not module:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "reload failed while importing world module",
                        WorldErrorCode.WORLD_RELOAD_FAILED,
                    )
                instance = self._create_game_instance(game_name, module)
                if not instance:
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "reload failed while creating world instance",
                        WorldErrorCode.WORLD_RELOAD_FAILED,
                    )
                initialize = getattr(instance, "initialize_game", None)
                if callable(initialize) and not initialize():
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "reload failed while initializing world instance",
                        WorldErrorCode.WORLD_RELOAD_FAILED,
                    )
                if not instance.start():
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "reload failed while starting world instance",
                        WorldErrorCode.WORLD_RELOAD_FAILED,
                    )
                if not self.engine.register_game(instance):
                    return self._result(
                        False,
                        game_name,
                        state_before,
                        WorldRuntimeStatus.FAILED.value,
                        "reload failed while registering world instance",
                        WorldErrorCode.WORLD_RELOAD_FAILED,
                    )
                self.loaded_games[game_name] = instance
                self.game_modules[game_name] = module
                return self._result(
                    True,
                    game_name,
                    state_before,
                    WorldRuntimeStatus.INSTALLED.value,
                    "world reloaded",
                    details={"job_id": job_id, "version": str(manifest.get("version"))},
                )

            try:
                result = self.service.run_with_job(
                    world_id=game_name,
                    action="reload",
                    status_before=state_before,
                    enter_status=WorldRuntimeStatus.RELOADING.value,
                    exec_fn=_run,
                )
                return result.to_dict()
            except Exception as e:
                return self._result(
                    False,
                    game_name,
                    state_before,
                    WorldRuntimeStatus.BROKEN.value,
                    f"persist runtime state failed: {e}",
                    WorldErrorCode.WORLD_DB_WRITE_FAILED,
                ).to_dict()
        finally:
            lock.release()

    def get_loaded_games(self) -> List[str]:
        return list(self.loaded_games.keys())

    def get_game_info(self, game_name: str) -> Optional[Dict[str, Any]]:
        game_instance = self.loaded_games.get(game_name)
        if not game_instance:
            state = self.repository.get_state(game_name)
            return {
                "name": game_name,
                "version": state.get("version"),
                "description": "",
                "author": "",
                "status": state.get("status", WorldRuntimeStatus.NOT_INSTALLED.value),
            }
        state = self.repository.get_state(game_name)
        return {
            "name": game_instance.name,
            "version": game_instance.version,
            "description": getattr(game_instance, "description", ""),
            "author": getattr(game_instance, "author", ""),
            "status": state.get("status", WorldRuntimeStatus.INSTALLED.value),
        }

    def auto_load_games(self) -> List[str]:
        loaded: List[str] = []
        for game_name in self.discover_games():
            result = self.load_game(game_name)
            if result.get("ok"):
                loaded.append(game_name)
            else:
                self.logger.error(f"自动加载场景 '{game_name}' 失败: {result}")
        self.logger.info(f"自动加载完成，成功加载 {len(loaded)} 个场景: {loaded}")
        return loaded
