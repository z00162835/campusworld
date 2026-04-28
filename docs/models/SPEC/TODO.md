# TODO - 数据模型开发任务

## 验收追踪

- 统一验收文档：`docs/ssh/SPEC/ACCEPTANCE.md`
- 入口语义约束：`SingularityRoom` 是系统全局入口，不是每用户独有空间。

## 实体扩展

### 高优先级

- [ ] **Room 类型完善**
  - 定义预定义空间：library/campus/canteen/dormitory
  - 空间属性：capacity（容量）/is_public（是否公开）
  - 空间坐标：x/y/z（可选，用于空间布局可视化）

- [ ] **Exit 类型完善**
  - 定义空间之间的连接关系
  - 属性：locked（是否锁定）/key_id（钥匙对象）
  - 方向：north/south/east/west 或自定义方向

- [ ] **SingularityRoom 完善**
  - 系统级全局单例入口空间（非每用户独有）
  - 创建用户后默认可进入系统入口 `SingularityRoom`
  - 与世界入口策略联动（进入世界后再落到世界内默认出生点）
  - 验收映射：`ACCEPTANCE 场景 A/B/C/D`

### 中优先级

- [ ] **Building 模型实现**
  - 包含多个 Room
  - 属性：floors（楼层数）/name/description

- [ ] **Character 模型完善**
  - 与 User 一对一关联
  - 属性：location_id（当前位置）/inventory（物品列表）
  - stats：energy/hunger/knowledge/social

- [ ] **Campus 模型实现**
  - 包含多个 World
  - 属性：name/location/owner

- [ ] **World 模型完善**
  - 包含多个 Building 和 Room
  - 属性：name/is_public/owner

### 低优先级

- [ ] **Item 模型**: 可交互的物品（书桌/食物等）
- [ ] **Equipment 模型**: 可穿戴/使用的设备
- [ ] **Event 模型**: 园区事件记录

## 语义边扩展

- [ ] 定义标准语义边类型枚举：LOCATED_IN/CONNECTED/OWNS/CONTAINS/HAS
- [ ] Exit 模型与语义边统一（Exit 即语义边的具象化）
- [ ] 支持语义边属性（如关系创建时间）

## 模型工厂扩展

- [ ] 自动发现机制：扫描 models/ 目录自动注册所有模型类
- [ ] 模型验证：注册时检查模型是否实现必要的接口
- [ ] 模型关系注册：声明模型间的关系（而非硬编码）

## 验收检查清单

- [ ] `model_factory.get_model("user")` 返回 User 类
- [ ] `model_factory.get_model("room")` 返回 Room 类
- [ ] `User` 继承 `DefaultAccount`
- [ ] `Room` 继承 `DefaultObject`
- [ ] 新建用户后可通过入口策略进入 `SingularityRoom`
- [ ] `SingularityRoom` 语义为系统全局入口（非每用户单例）