# Demo Building Generator

基于项目模型能力，参考Evennia设计，构建和测试demo building的完整解决方案。

## 功能特性

### 建筑结构
- **地下2层，地上8层**：总共10层建筑
- **楼层配置**：
  - 地下2层：30个停车场房间
  - 地下1层：1个冷机房 + 29个停车场房间
  - 1楼：10个房间
  - 2楼：20个房间
  - 3楼：50个房间
  - 4-6楼：每层32个房间
  - 7楼：16个房间
  - 8楼：36个房间

### 房间连接系统
- **物理合理的连接**：只连接物理上相邻的房间
- **网格布局模拟**：基于房间编号模拟实际建筑网格布局
- **方向计算**：准确计算房间间的方向关系
- **连接数量控制**：每个房间随机连接1-3个相邻房间

### 家具和物品
- **每个房间必须有WiFi AP**：确保网络覆盖
- **随机家具生成**：根据房间类型生成相应家具
- **随机物品**：水杯、笔记本、笔等日常用品
- **特殊设备**：冷机房配备专业制冷设备

### 特殊房间
- **冷机房**：地下1层第1个房间，配备冷机设备和监控系统
- **停车场**：地下1-2层大部分房间，配备停车位和充电桩

## 文件结构

```
tests/
├── test_demo_building_generator.py  # 主要测试脚本
├── demo_building_example.py        # 使用示例
├── room_connection_visualizer.py    # 房间连接可视化工具
├── run_demo_building.py            # 测试运行器
└── README_demo_building.md         # 本文档
```

## 使用方法

### 1. 运行完整测试

```bash
cd campusworld/backend
python tests/test_demo_building_generator.py
```

### 2. 运行使用示例

```bash
cd campusworld/backend
python tests/demo_building_example.py
```

### 4. 可视化房间连接

```bash
cd campusworld/backend
python tests/room_connection_visualizer.py
```

### 5. 在代码中使用

```python
from tests.test_demo_building_generator import DemoBuildingGenerator

# 创建生成器
generator = DemoBuildingGenerator()

# 生成建筑
success = generator.generate_building()

if success:
    # 获取摘要信息
    summary = generator.get_building_summary()
    
    # 打印摘要
    generator.print_building_summary()
```

## 技术实现

### 架构设计
- **参考Evennia模式**：使用钩子函数和生命周期管理
- **纯图数据设计**：所有数据存储在Node中
- **模型工厂模式**：使用工厂模式创建对象
- **组件化设计**：模块化的房间和对象生成

### 核心类

#### DemoBuildingGenerator
主要的生成器类，负责：
- 建筑创建和管理
- 楼层生成和配置
- 房间创建和连接
- 家具和物品生成
- 特殊房间处理

#### 支持的模型类型
- **Building**: 建筑模型
- **BuildingFloor**: 楼层模型
- **Room**: 房间模型
- **WorldObject**: 世界对象模型（家具、设备等）

### 房间连接算法

#### 核心方法
- **`_get_room_coordinates()`**: 根据房间编号计算网格坐标
- **`_find_adjacent_rooms()`**: 找到物理上相邻的房间
- **`_calculate_direction()`**: 计算房间间的方向关系
- **`_generate_room_connections()`**: 生成合理的房间连接

#### 布局策略
```python
# 根据房间数量确定楼层布局
if room_count <= 10:
    cols = 5  # 2x5 布局
elif room_count <= 20:
    cols = 5  # 4x5 布局
elif room_count <= 32:
    cols = 6  # 6x6 布局
else:
    cols = 8  # 8x7 布局
```

#### 相邻关系
- **8方向相邻**: 上下左右 + 4个对角线方向
- **边界检查**: 确保不超出楼层范围
- **物理约束**: 只连接真正相邻的房间

#### 楼层配置
```python
floor_config = {
    -2: {"room_count": 30, "room_type": "parking", "floor_type": "basement"},
    -1: {"room_count": 30, "room_type": "mixed", "floor_type": "basement"},
    1: {"room_count": 10, "room_type": "normal", "floor_type": "normal"},
    # ... 更多楼层配置
}
```

#### 家具模板
```python
furniture_templates = {
    "office": ["办公桌", "办公椅", "文件柜", "书架", "打印机"],
    "classroom": ["讲台", "黑板", "课桌椅", "投影仪"],
    "meeting": ["会议桌", "会议椅", "投影屏幕"],
    # ... 更多家具类型
}
```

## 验证和测试

### 自动验证
生成器包含完整的验证逻辑：
- 建筑创建验证
- 楼层数量验证
- 房间数量验证
- 特殊房间验证
- WiFi AP覆盖验证

### 测试覆盖
- **房间坐标计算测试**: 验证网格坐标计算的正确性
- **房间连接逻辑测试**: 验证物理连接的合理性
- **建筑生成测试**: 验证整体功能
- **连接可视化**: 直观展示连接关系

## 输出示例

```
================================================================================
DEMO BUILDING 生成摘要
================================================================================
建筑名称: Demo Building
楼层数量: 10
房间数量: 280
对象数量: 1120

楼层详情:
  第-2层: 30个房间, 面积1800.0㎡
  第-1层: 30个房间, 面积1800.0㎡
  第1层: 10个房间, 面积500.0㎡
  第2层: 20个房间, 面积1000.0㎡
  第3层: 50个房间, 面积2500.0㎡
  第4层: 32个房间, 面积1600.0㎡
  第5层: 32个房间, 面积1600.0㎡
  第6层: 32个房间, 面积1600.0㎡
  第7层: 16个房间, 面积800.0㎡
  第8层: 36个房间, 面积1800.0㎡

房间类型统计:
  parking: 59个
  office: 45个
  classroom: 38个
  meeting: 30个
  lab: 23个
  common: 15个
  cold_room: 1个

对象类型统计:
  equipment: 280个
  furniture: 840个
  item: 280个
================================================================================
```

## 扩展性

### 添加新的房间类型
1. 在`furniture_templates`中添加新类型
2. 在`_get_random_room_type`中添加权重
3. 在`_generate_random_room_area`中添加面积范围
4. 在`_calculate_room_capacity`中添加容量范围

### 添加新的家具类型
1. 在`furniture_templates`中添加家具列表
2. 在`_create_furniture`中添加特定逻辑

### 自定义楼层配置
修改`floor_config`字典来调整楼层数量和房间配置。

## 注意事项

1. **数据库连接**：确保数据库连接正常
2. **模型注册**：确保所有模型类型已正确注册
3. **内存使用**：大量对象生成可能消耗较多内存
4. **并发安全**：多线程环境下需要适当的同步机制

## 故障排除

### 常见问题
1. **导入错误**：检查Python路径设置
2. **数据库错误**：检查数据库连接和权限
3. **模型错误**：检查模型类是否正确导入
4. **内存不足**：减少房间数量或分批生成

### 调试建议
1. 启用详细日志记录
2. 使用小规模测试数据
3. 检查模型属性设置
4. 验证数据库状态

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 添加测试用例
4. 提交Pull Request

## 许可证

本项目遵循项目主许可证。
