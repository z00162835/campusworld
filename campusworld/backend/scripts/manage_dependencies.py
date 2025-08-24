#!/usr/bin/env python3
"""
依赖管理脚本
用于检查、安装和更新项目依赖
"""

import os
import sys
import subprocess
import json
import pkg_resources
from pathlib import Path
from typing import Dict, List, Set, Tuple


class DependencyManager:
    """依赖管理器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.requirements_dir = project_root / "requirements"
        self.venv_path = project_root / ".venv"
        
    def get_installed_packages(self) -> Dict[str, str]:
        """获取已安装的包信息"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, check=True
            )
            packages = json.loads(result.stdout)
            return {pkg["name"]: pkg["version"] for pkg in packages}
        except Exception as e:
            print(f"获取已安装包信息失败: {e}")
            return {}
    
    def parse_requirements_file(self, file_path: Path) -> Dict[str, str]:
        """解析requirements文件"""
        requirements = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-r'):
                        if '==' in line:
                            name, version = line.split('==', 1)
                            requirements[name.lower()] = version
                        elif '>=' in line:
                            name, version = line.split('>=', 1)
                            requirements[name.lower()] = f">={version}"
                        elif '<=' in line:
                            name, version = line.split('<=', 1)
                            requirements[name.lower()] = f"<={version}"
        except Exception as e:
            print(f"解析requirements文件失败 {file_path}: {e}")
        return requirements
    
    def get_all_requirements(self) -> Dict[str, str]:
        """获取所有requirements文件中的依赖"""
        all_requirements = {}
        
        # 读取base.txt
        base_file = self.requirements_dir / "base.txt"
        if base_file.exists():
            all_requirements.update(self.parse_requirements_file(base_file))
        
        # 读取其他requirements文件
        for req_file in self.requirements_dir.glob("*.txt"):
            if req_file.name != "base.txt":
                all_requirements.update(self.parse_requirements_file(req_file))
        
        return all_requirements
    
    def check_dependencies(self) -> Tuple[Dict[str, str], Dict[str, str], List[str]]:
        """检查依赖状态"""
        installed = self.get_installed_packages()
        required = self.get_all_requirements()
        
        missing = []
        outdated = []
        
        for package, required_version in required.items():
            if package not in installed:
                missing.append(package)
            else:
                installed_version = installed[package]
                if not self._version_satisfies(installed_version, required_version):
                    outdated.append(f"{package}: {installed_version} -> {required_version}")
        
        return installed, required, missing, outdated
    
    def _version_satisfies(self, installed_version: str, required_version: str) -> bool:
        """检查版本是否满足要求"""
        try:
            if required_version.startswith('>='):
                min_version = required_version[2:]
                return pkg_resources.parse_version(installed_version) >= pkg_resources.parse_version(min_version)
            elif required_version.startswith('<='):
                max_version = required_version[2:]
                return pkg_resources.parse_version(installed_version) <= pkg_resources.parse_version(max_version)
            else:
                return installed_version == required_version
        except Exception:
            return False
    
    def install_dependencies(self, requirements_file: str = "base.txt") -> bool:
        """安装依赖"""
        req_file = self.requirements_dir / requirements_file
        if not req_file.exists():
            print(f"Requirements文件不存在: {req_file}")
            return False
        
        try:
            print(f"正在安装依赖: {requirements_file}")
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(req_file)
            ], check=True)
            print(f"依赖安装完成: {requirements_file}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"依赖安装失败: {e}")
            return False
    
    def install_all_dependencies(self) -> bool:
        """安装所有依赖"""
        success = True
        
        # 安装基础依赖
        if not self.install_dependencies("base.txt"):
            success = False
        
        # 安装开发依赖
        if not self.install_dependencies("dev.txt"):
            success = False
        
        # 安装SSH依赖
        if not self.install_dependencies("ssh.txt"):
            success = False
        
        # 安装监控依赖
        if not self.install_dependencies("monitoring.txt"):
            success = False
        
        # 安装安全依赖
        if not self.install_dependencies("security.txt"):
            success = False
        
        return success
    
    def update_dependencies(self) -> bool:
        """更新依赖"""
        try:
            print("正在更新依赖...")
            subprocess.run([
                sys.executable, "-m", "pip", "install", "--upgrade", "pip"
            ], check=True)
            
            # 更新所有requirements文件中的依赖
            all_requirements = self.get_all_requirements()
            for package in all_requirements.keys():
                try:
                    subprocess.run([
                        sys.executable, "-m", "pip", "install", "--upgrade", package
                    ], check=True)
                    print(f"已更新: {package}")
                except subprocess.CalledProcessError:
                    print(f"更新失败: {package}")
            
            return True
        except Exception as e:
            print(f"更新依赖失败: {e}")
            return False
    
    def generate_report(self) -> str:
        """生成依赖报告"""
        installed, required, missing, outdated = self.check_dependencies()
        
        report = f"""
依赖状态报告
{'='*50}

已安装包数量: {len(installed)}
要求包数量: {len(required)}
缺失包数量: {len(missing)}
过时包数量: {len(outdated)}

"""
        
        if missing:
            report += "缺失的包:\n"
            for package in missing:
                version = required.get(package, "未知版本")
                report += f"  - {package}=={version}\n"
        
        if outdated:
            report += "\n需要更新的包:\n"
            for package_info in outdated:
                report += f"  - {package_info}\n"
        
        if not missing and not outdated:
            report += "✅ 所有依赖都已正确安装且版本匹配！\n"
        
        return report


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    manager = DependencyManager(project_root)
    
    if len(sys.argv) < 2:
        print("用法: python manage_dependencies.py [check|install|install-all|update|report]")
        return
    
    command = sys.argv[1]
    
    if command == "check":
        installed, required, missing, outdated = manager.check_dependencies()
        print(f"已安装: {len(installed)}")
        print(f"要求: {len(required)}")
        print(f"缺失: {len(missing)}")
        print(f"过时: {len(outdated)}")
        
    elif command == "install":
        if len(sys.argv) > 2:
            requirements_file = sys.argv[2]
            manager.install_dependencies(requirements_file)
        else:
            manager.install_dependencies()
            
    elif command == "install-all":
        manager.install_all_dependencies()
        
    elif command == "update":
        manager.update_dependencies()
        
    elif command == "report":
        print(manager.generate_report())
        
    else:
        print(f"未知命令: {command}")
        print("可用命令: check, install, install-all, update, report")


if __name__ == "__main__":
    main()
