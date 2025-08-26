#!/usr/bin/env python3
"""
CampusWorld 游戏引擎启动脚本

启动游戏引擎并加载可用游戏，提供SSH交互能力。
"""

import os
import sys
import logging
import signal
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.game_engine import game_engine_manager
from app.ssh.server import CampusWorldSSHServer


def setup_logging():
    """设置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/game_engine.log', encoding='utf-8')
        ]
    )


def signal_handler(signum, frame):
    """信号处理器"""
    print(f"\n收到信号 {signum}，正在关闭游戏引擎...")
    
    try:
        # 停止游戏引擎
        if game_engine_manager.get_engine():
            game_engine_manager.stop_engine()
        
        print("游戏引擎已关闭")
        sys.exit(0)
        
    except Exception as e:
        print(f"关闭游戏引擎时出错: {e}")
        sys.exit(1)


def main():
    """主函数"""
    print("=" * 60)
    print("CampusWorld 游戏引擎启动器")
    print("=" * 60)
    
    try:
        # 设置日志
        setup_logging()
        logger = logging.getLogger("main")
        
        # 设置信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        print("正在初始化游戏引擎...")
        logger.info("开始初始化游戏引擎")
        
        # 初始化游戏引擎
        if not game_engine_manager.initialize_engine():
            print("游戏引擎初始化失败")
            logger.error("游戏引擎初始化失败")
            return False
        
        print("游戏引擎初始化成功")
        logger.info("游戏引擎初始化成功")
        
        # 启动游戏引擎
        print("正在启动游戏引擎...")
        if not game_engine_manager.start_engine():
            print("游戏引擎启动失败")
            logger.error("游戏引擎启动失败")
            return False
        
        print("游戏引擎启动成功")
        logger.info("游戏引擎启动成功")
        
        # 显示引擎状态
        status = game_engine_manager.get_engine_status()
        print("\n游戏引擎状态:")
        print(f"  名称: {status.get('name', 'N/A')}")
        print(f"  版本: {status.get('version', 'N/A')}")
        print(f"  状态: {'运行中' if status.get('is_running') else '已停止'}")
        print(f"  游戏数量: {status.get('games_count', 0)}")
        
        # 显示可用游戏
        available_games = game_engine_manager.list_games()
        if available_games:
            print(f"\n可用游戏 ({len(available_games)}):")
            for game_name in available_games:
                print(f"  - {game_name}")
        else:
            print("\n没有找到可用游戏")
        
        # 显示已加载游戏
        loaded_games = status.get('loaded_games', [])
        if loaded_games:
            print(f"\n已加载游戏 ({len(loaded_games)}):")
            for game_name in loaded_games:
                print(f"  - {game_name}")
        else:
            print("\n没有已加载的游戏")
        
        print("\n游戏引擎已启动，可以通过SSH连接进行交互")
        print("使用 'game' 命令管理游戏引擎")
        print("使用 'help' 命令查看可用命令")
        print("\n按 Ctrl+C 停止游戏引擎")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n收到中断信号，正在关闭...")
        
        return True
        
    except Exception as e:
        print(f"启动游戏引擎时出错: {e}")
        logger.error(f"启动游戏引擎时出错: {e}")
        return False
    
    finally:
        # 清理资源
        try:
            if game_engine_manager.get_engine():
                game_engine_manager.stop_engine()
                print("游戏引擎已关闭")
        except Exception as e:
            print(f"关闭游戏引擎时出错: {e}")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
