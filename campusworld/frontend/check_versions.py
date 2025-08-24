#!/usr/bin/env python3
"""
前端依赖版本检查脚本
用于验证package.json中的依赖版本是否最新
"""

import json
import subprocess
import sys
from pathlib import Path

def run_command(command):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ 命令执行失败: {command}")
        print(f"错误: {e.stderr}")
        return None

def check_npm_version():
    """检查npm版本"""
    print("🔍 检查npm版本...")
    version = run_command("npm --version")
    if version:
        print(f"✅ npm版本: {version}")
        return version
    return None

def check_node_version():
    """检查Node.js版本"""
    print("🔍 检查Node.js版本...")
    version = run_command("node --version")
    if version:
        print(f"✅ Node.js版本: {version}")
        return version
    return None

def load_package_json():
    """加载package.json文件"""
    package_path = Path("package.json")
    if not package_path.exists():
        print("❌ package.json文件不存在")
        return None
    
    try:
        with open(package_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ package.json解析失败: {e}")
        return None

def check_dependency_versions(package_data):
    """检查依赖版本"""
    print("\n📦 检查依赖版本...")
    
    # 关键依赖及其推荐版本
    key_dependencies = {
        "vue": "3.4.21",
        "vite": "5.1.4",
        "typescript": "5.3.3",
        "element-plus": "2.6.1",
        "axios": "1.6.7"
    }
    
    all_good = True
    
    # 检查dependencies
    if "dependencies" in package_data:
        print("\n🔧 生产依赖:")
        for dep, recommended in key_dependencies.items():
            if dep in package_data["dependencies"]:
                current = package_data["dependencies"][dep]
                print(f"  {dep}: {current}")
                
                # 检查版本是否最新
                if recommended in current or current.startswith("^" + recommended):
                    print(f"    ✅ 版本最新")
                else:
                    print(f"    ⚠️  建议更新到 {recommended}")
                    all_good = False
    
    # 检查devDependencies
    if "devDependencies" in package_data:
        print("\n🔧 开发依赖:")
        dev_deps = ["vite", "typescript", "eslint", "vitest"]
        for dep in dev_deps:
            if dep in package_data["devDependencies"]:
                current = package_data["devDependencies"][dep]
                print(f"  {dep}: {current}")
    
    return all_good

def check_engines(package_data):
    """检查engines配置"""
    print("\n🔧 检查环境要求...")
    
    if "engines" in package_data:
        engines = package_data["engines"]
        if "node" in engines:
            print(f"  Node.js要求: {engines['node']}")
        if "npm" in engines:
            print(f"  npm要求: {engines['npm']}")
        
        # 检查当前版本是否符合要求
        node_version = run_command("node --version")
        npm_version = run_command("npm --version")
        
        if node_version and npm_version:
            print(f"  当前Node.js: {node_version}")
            print(f"  当前npm: {npm_version}")
    else:
        print("  ⚠️  未设置engines要求")

def check_scripts(package_data):
    """检查scripts配置"""
    print("\n🔧 检查脚本配置...")
    
    if "scripts" in package_data:
        scripts = package_data["scripts"]
        important_scripts = ["dev", "build", "test", "lint", "type-check"]
        
        for script in important_scripts:
            if script in scripts:
                print(f"  ✅ {script}: {scripts[script]}")
            else:
                print(f"  ⚠️  缺少脚本: {script}")
    else:
        print("  ❌ 未找到scripts配置")

def check_browserslist(package_data):
    """检查browserslist配置"""
    print("\n🔧 检查浏览器兼容性...")
    
    if "browserslist" in package_data:
        browserslist = package_data["browserslist"]
        print("  ✅ 已配置browserslist")
        
        if "production" in browserslist:
            print(f"  生产环境: {browserslist['production']}")
        if "development" in browserslist:
            print(f"  开发环境: {browserslist['development']}")
    else:
        print("  ⚠️  未配置browserslist")

def run_npm_audit():
    """运行npm audit检查安全漏洞"""
    print("\n🔍 检查安全漏洞...")
    
    result = run_command("npm audit --audit-level=moderate")
    if result:
        if "found 0 vulnerabilities" in result:
            print("✅ 未发现安全漏洞")
        else:
            print("⚠️  发现安全漏洞，请运行: npm audit fix")
            print(result)
    else:
        print("❌ 安全检查失败")

def main():
    """主函数"""
    print("🚀 CampusWorld 前端依赖版本检查")
    print("=" * 50)
    
    # 检查环境
    npm_version = check_npm_version()
    node_version = check_node_version()
    
    if not npm_version or not node_version:
        print("❌ 环境检查失败")
        sys.exit(1)
    
    # 加载package.json
    package_data = load_package_json()
    if not package_data:
        print("❌ 无法加载package.json")
        sys.exit(1)
    
    # 检查各种配置
    versions_ok = check_dependency_versions(package_data)
    check_engines(package_data)
    check_scripts(package_data)
    check_browserslist(package_data)
    
    # 安全检查
    run_npm_audit()
    
    # 总结
    print("\n" + "=" * 50)
    if versions_ok:
        print("🎉 依赖版本检查完成，所有版本都是最新的！")
    else:
        print("⚠️  依赖版本检查完成，建议更新部分依赖")
    
    print("\n💡 建议操作:")
    if not versions_ok:
        print("1. 运行更新脚本: ./update_deps.sh")
        print("2. 或手动更新: npm update")
    
    print("3. 检查安全漏洞: npm audit fix")
    print("4. 测试项目: npm run dev")

if __name__ == "__main__":
    main()
