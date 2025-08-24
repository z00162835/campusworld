#!/usr/bin/env python3
"""
依赖安装脚本
用于安装CampusWorld项目所需的Python依赖
"""

import subprocess
import sys
import os

def run_command(command, description):
    """运行命令并显示结果"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description}成功")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}失败: {e}")
        if e.stderr:
            print(f"错误信息: {e.stderr}")
        return False

def check_python_version():
    """检查Python版本"""
    print("🐍 检查Python版本...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python版本过低: {version.major}.{version.minor}.{version.micro}")
        print("需要Python 3.9或更高版本")
        return False

def install_pip_deps():
    """安装pip依赖"""
    print("\n📦 安装pip依赖...")
    
    # 升级pip
    if not run_command("pip install --upgrade pip", "升级pip"):
        return False
    
    # 安装基础依赖
    if not run_command("pip install -r requirements/base.txt", "安装基础依赖"):
        return False
    
    # 安装开发依赖
    if not run_command("pip install -r requirements/dev.txt", "安装开发依赖"):
        return False
    
    return True

def install_conda_deps():
    """安装conda依赖"""
    print("\n📦 安装conda依赖...")
    
    # 检查conda是否可用
    try:
        subprocess.run("conda --version", shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("⚠️  conda不可用，跳过conda依赖安装")
        return True
    
    # 安装PyYAML
    if not run_command("conda install -y pyyaml", "安装PyYAML"):
        print("⚠️  conda安装PyYAML失败，尝试pip安装")
        if not run_command("pip install pyyaml", "pip安装PyYAML"):
            return False
    
    return True

def verify_installation():
    """验证安装"""
    print("\n🔍 验证安装...")
    
    # 测试导入关键模块
    modules_to_test = [
        ("yaml", "PyYAML"),
        ("pydantic", "Pydantic"),
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
    ]
    
    all_success = True
    for module_name, display_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {display_name} 导入成功")
        except ImportError:
            print(f"❌ {display_name} 导入失败")
            all_success = False
    
    return all_success

def main():
    """主函数"""
    print("🚀 CampusWorld 依赖安装脚本")
    print("=" * 50)
    
    # 检查Python版本
    if not check_python_version():
        sys.exit(1)
    
    # 安装依赖
    if not install_pip_deps():
        print("❌ pip依赖安装失败")
        sys.exit(1)
    
    if not install_conda_deps():
        print("❌ conda依赖安装失败")
        sys.exit(1)
    
    # 验证安装
    if not verify_installation():
        print("❌ 依赖验证失败")
        sys.exit(1)
    
    print("\n🎉 所有依赖安装完成！")
    print("\n💡 下一步:")
    print("1. 运行配置测试: python test_config_manager.py")
    print("2. 运行项目初始化: ../scripts/setup.sh")
    print("3. 启动开发服务器: uvicorn app.main:app --reload")

if __name__ == "__main__":
    main()
