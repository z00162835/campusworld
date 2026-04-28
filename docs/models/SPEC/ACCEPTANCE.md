# 验收检查表

## 模型注册验收

- [ ] `model_factory.list_all_models()` 返回所有已注册模型
- [ ] `model_factory.register_model("test", TestModel)` 成功注册
- [ ] `model_factory.get_model("test")` 返回 TestModel 类
- [ ] 未注册的模型返回 KeyError

## 实体继承验收

- [ ] `User` 继承 `DefaultAccount`
- [ ] `Character` 继承 `DefaultObject`
- [ ] `Room` 继承 `DefaultObject`
- [ ] `World` 继承 `DefaultObject`
- [ ] `Exit` 继承 `DefaultObject`

## 图结构验收

- [ ] `Node` 表包含：id/uuid/type_code/name/description/attributes
- [ ] `Relationship` 表包含：id/source_id/target_id/type/properties
- [ ] 查询 Room 的所有出口（通过 Relationship）成功
- [ ] 查询 Character 的当前位置（通过 LOCATED_IN 边）成功

## 用户生命周期验收

- [ ] 创建 User 时自动创建对应 Character
- [ ] Character 默认 spawn 到 SingularityRoom
- [ ] `User.find_by_email()` 查询成功
- [ ] `Character.find_by_user_id()` 查询成功

## 组件系统验收

- [ ] `InventoryMixin` 提供 add_item/remove_item/get_items 方法
- [ ] `StatsMixin` 提供 get_stat/set_stat/increase_stat 方法
- [ ] 模型可通过 mixin 组合获得多个组件能力