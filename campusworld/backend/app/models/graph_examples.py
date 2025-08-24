"""
图数据结构示例和测试

演示如何使用图节点系统：
- 创建和连接节点
- 图遍历和查询
- 性能优化
- 实际应用场景
"""

from typing import Dict, Any, List
from uuid import uuid4
import time

from .graph import (
    GraphNode, 
    Relationship, 
    FriendshipRelationship,
    LocationRelationship,
    OwnershipRelationship,
    Node, 
    GraphDefaultObject, 
    GraphDefaultAccount
)
from .graph_manager import GraphManager, get_graph_manager
from .factory import model_factory


class PlayerObject(GraphDefaultObject):
    """
    玩家对象示例
    
    继承自GraphDefaultObject，自动同步到图节点系统
    """
    
    __tablename__ = "player_objects"
    
    def __init__(self, name: str, level: int = 1, **kwargs):
        super().__init__(name=name, **kwargs)
        self.level = level
        self.experience = 0
        self.inventory = []
        
        # 设置属性
        self.set_attribute("level", level)
        self.set_attribute("experience", 0)
        self.set_attribute("inventory", [])
    
    def gain_experience(self, amount: int) -> None:
        """获得经验"""
        self.experience += amount
        self.set_attribute("experience", self.experience)
        
        # 检查升级
        if self.experience >= self.level * 100:
            self.level_up()
    
    def level_up(self) -> None:
        """升级"""
        self.level += 1
        self.set_attribute("level", self.level)
        print(f"{self.name} 升级到 {self.level} 级！")
    
    def add_item(self, item: str) -> None:
        """添加物品到背包"""
        self.inventory.append(item)
        self.set_attribute("inventory", self.inventory)


class GameWorld(GraphDefaultObject):
    """
    游戏世界示例
    
    继承自GraphDefaultObject，自动同步到图节点系统
    """
    
    __tablename__ = "game_worlds"
    
    def __init__(self, name: str, world_type: str = "fantasy", **kwargs):
        super().__init__(name=name, **kwargs)
        self.world_type = world_type
        self.max_players = 100
        self.current_players = 0
        
        # 设置属性
        self.set_attribute("world_type", world_type)
        self.set_attribute("max_players", 100)
        self.set_attribute("current_players", 0)
    
    def add_player(self, player: PlayerObject) -> bool:
        """添加玩家到世界"""
        if self.current_players >= self.max_players:
            return False
        
        self.current_players += 1
        self.set_attribute("current_players", self.current_players)
        
        # 创建位置关系
        graph_manager = get_graph_manager()
        graph_manager.create_location_relationship(
            self, player, 
            location_type="contains",
            joined_at=time.time(),
            role="player"
        )
        
        return True
    
    def remove_player(self, player: PlayerObject) -> bool:
        """从世界移除玩家"""
        if self.current_players <= 0:
            return False
        
        self.current_players -= 1
        self.set_attribute("current_players", self.current_players)
        
        # 移除关系
        graph_manager = get_graph_manager()
        graph_manager.remove_relationship(self, player, "contains")
        
        return True


class GameItem(GraphDefaultObject):
    """
    游戏物品示例
    
    继承自GraphDefaultObject，自动同步到图节点系统
    """
    
    __tablename__ = "game_items"
    
    def __init__(self, name: str, item_type: str = "weapon", **kwargs):
        super().__init__(name=name, **kwargs)
        self.item_type = item_type
        self.rarity = "common"
        self.durability = 100
        
        # 设置属性
        self.set_attribute("item_type", item_type)
        self.set_attribute("rarity", self.rarity)
        self.set_attribute("durability", self.durability)
    
    def use_item(self, player: PlayerObject) -> bool:
        """使用物品"""
        if self.durability > 0:
            self.durability -= 1
            self.set_attribute("durability", self.durability)
            return True
        return False


def create_sample_graph():
    """创建示例图结构"""
    print("创建示例图结构...")
    
    # 创建图管理器
    graph_manager = get_graph_manager()
    
    # 创建游戏世界
    fantasy_world = GameWorld("艾泽拉斯", "fantasy")
    sci_fi_world = GameWorld("星际联邦", "sci_fi")
    
    # 创建玩家
    players = []
    for i in range(5):
        player = PlayerObject(f"玩家{i+1}", level=i+1)
        players.append(player)
    
    # 创建物品
    items = []
    for i in range(3):
        item = GameItem(f"物品{i+1}", "weapon" if i % 2 == 0 else "armor")
        items.append(item)
    
    # 创建玩家-世界关系（位置关系）
    print("创建玩家-世界关系...")
    for player in players:
        if player.level <= 3:
            fantasy_world.add_player(player)
        else:
            sci_fi_world.add_player(player)
    
    # 创建玩家间关系（友谊关系）
    print("创建玩家间关系...")
    for i, player1 in enumerate(players):
        for j, player2 in enumerate(players[i+1:], i+1):
            if abs(player1.level - player2.level) <= 1:
                graph_manager.create_friendship(
                    player1, player2,
                    friendship_level="close",
                    met_at=time.time(),
                    shared_interests=["gaming", "adventure"]
                )
    
    # 创建玩家-物品关系（所有权关系）
    print("创建玩家-物品关系...")
    for i, player in enumerate(players):
        if i < len(items):
            graph_manager.create_ownership_relationship(
                player, items[i],
                ownership_type="owner",
                acquired_at=time.time()
            )
    
    print("示例图结构创建完成！")
    return fantasy_world, sci_fi_world, players, items


def demonstrate_typed_relationships():
    """演示类型化关系系统"""
    print("\n=== 类型化关系演示 ===")
    
    graph_manager = get_graph_manager()
    
    # 获取不同类型的关系
    friendship_rels = graph_manager.get_friendship_relationships()
    location_rels = graph_manager.get_location_relationships()
    ownership_rels = graph_manager.get_ownership_relationships()
    
    print(f"友谊关系数量: {len(friendship_rels)}")
    print(f"位置关系数量: {len(location_rels)}")
    print(f"所有权关系数量: {len(ownership_rels)}")
    
    # 演示友谊关系升级
    if friendship_rels:
        friendship = friendship_rels[0]
        print(f"友谊等级: {friendship.friendship_level}")
        if friendship.upgrade_friendship("best_friend"):
            print("友谊升级成功！")
    
    # 演示位置关系
    if location_rels:
        location_rel = location_rels[0]
        print(f"位置类型: {location_rel.location_type}")
        location_rel.enter_location()
        print(f"进入位置时间: {location_rel.entered_at}")
    
    # 演示所有权关系
    if ownership_rels:
        ownership_rel = ownership_rels[0]
        print(f"所有权类型: {ownership_rel.ownership_type}")
        print(f"获得时间: {ownership_rel.acquired_at}")


def demonstrate_graph_queries():
    """演示图查询功能"""
    print("\n=== 图查询演示 ===")
    
    graph_manager = get_graph_manager()
    
    # 获取所有节点
    all_nodes = graph_manager.db_session.query(GraphNode).all()
    print(f"总节点数: {len(all_nodes)}")
    
    # 按类型查询
    player_nodes = graph_manager.get_nodes_by_type("PlayerObject")
    world_nodes = graph_manager.get_nodes_by_type("GameWorld")
    item_nodes = graph_manager.get_nodes_by_type("GameItem")
    print(f"玩家节点数: {len(player_nodes)}")
    print(f"世界节点数: {len(world_nodes)}")
    print(f"物品节点数: {len(item_nodes)}")
    
    # 按属性查询
    high_level_players = graph_manager.get_nodes_by_attribute("level", 3)
    print(f"3级玩家数: {len(high_level_players)}")
    
    # 按标签查询
    fantasy_nodes = graph_manager.get_nodes_by_tag("fantasy")
    print(f"奇幻世界节点数: {len(fantasy_nodes)}")
    
    # 搜索功能
    search_results = graph_manager.search_nodes("玩家")
    print(f"搜索'玩家'结果数: {len(search_results)}")


def demonstrate_graph_traversal():
    """演示图遍历功能"""
    print("\n=== 图遍历演示 ===")
    
    graph_manager = get_graph_manager()
    
    # 获取所有节点
    all_nodes = graph_manager.db_session.query(GraphNode).all()
    if len(all_nodes) < 2:
        print("节点数量不足，无法演示遍历")
        return
    
    source = all_nodes[0]
    target = all_nodes[-1]
    
    print(f"从 {source.name} 到 {target.name} 的路径:")
    
    # 查找路径
    path = graph_manager.get_path(source, target, max_depth=3)
    if path:
        path_names = [node.name for node in path]
        print(f"路径: {' -> '.join(path_names)}")
    else:
        print("未找到路径")
    
    # 获取子图
    print(f"\n获取 {source.name} 的2层子图:")
    subgraph = graph_manager.get_subgraph(source, depth=2)
    print(f"子图节点数: {len(subgraph['nodes'])}")
    print(f"子图关系数: {len(subgraph['relationships'])}")


def demonstrate_performance_features():
    """演示性能优化功能"""
    print("\n=== 性能优化演示 ===")
    
    graph_manager = get_graph_manager()
    
    # 批量创建节点
    print("批量创建测试节点...")
    test_nodes_data = []
    for i in range(10):
        test_nodes_data.append({
            "uuid": str(uuid4()),
            "classpath": "app.models.test.TestNode",
            "classname": "TestNode",
            "module_path": "app.models.test",
            "name": f"测试节点{i}",
            "description": f"这是测试节点{i}",
            "attributes": {"test_id": i, "category": "test"},
            "tags": ["test", f"category_{i}"],
            "is_active": True,
            "is_public": True,
            "access_level": "normal"
        })
    
    start_time = time.time()
    created_nodes = graph_manager.bulk_create_nodes(test_nodes_data)
    end_time = time.time()
    
    print(f"批量创建 {len(created_nodes)} 个节点耗时: {end_time - start_time:.4f}秒")
    
    # 批量创建关系
    print("批量创建测试关系...")
    test_rels_data = []
    for i in range(len(created_nodes) - 1):
        test_rels_data.append({
            "uuid": str(uuid4()),
            "type": "test_connection",
            "classpath": "app.models.graph.Relationship",
            "source_id": created_nodes[i].id,
            "target_id": created_nodes[i+1].id,
            "attributes": {"connection_type": "sequential", "order": i},
            "is_active": True,
            "weight": 1
        })
    
    start_time = time.time()
    created_rels = graph_manager.bulk_create_relationships(test_rels_data)
    end_time = time.time()
    
    print(f"批量创建 {len(created_rels)} 个关系耗时: {end_time - start_time:.4f}秒")


def demonstrate_statistics():
    """演示统计功能"""
    print("\n=== 统计信息演示 ===")
    
    graph_manager = get_graph_manager()
    
    # 获取图统计
    stats = graph_manager.get_graph_stats()
    print("图统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 获取节点类型分布
    node_dist = graph_manager.get_node_type_distribution()
    print("\n节点类型分布:")
    for node_type, count in node_dist.items():
        print(f"  {node_type}: {count}")
    
    # 获取关系类型分布
    rel_dist = graph_manager.get_relationship_type_distribution()
    print("\n关系类型分布:")
    for rel_type, count in rel_dist.items():
        print(f"  {rel_type}: {count}")
    
    # 获取关系类分布
    rel_class_dist = graph_manager.get_relationship_class_distribution()
    print("\n关系类分布:")
    for rel_class, count in rel_class_dist.items():
        print(f"  {rel_class}: {count}")


def demonstrate_type_safety():
    """演示类型安全特性"""
    print("\n=== 类型安全演示 ===")
    
    # 演示接口实现
    from .graph import BaseNode, BaseRelationship
    
    # 检查节点类型
    print("检查节点类型层次:")
    print(f"  GraphNode 是 BaseNode 的实例: {isinstance(GraphNode(), BaseNode)}")
    print(f"  PlayerObject 是 BaseNode 的实例: {isinstance(PlayerObject('测试玩家'), BaseNode)}")
    
    # 检查关系类型
    print("检查关系类型层次:")
    print(f"  Relationship 是 BaseRelationship 的实例: {isinstance(Relationship(), BaseRelationship)}")
    print(f"  FriendshipRelationship 是 BaseRelationship 的实例: {isinstance(FriendshipRelationship(), BaseRelationship)}")
    
    # 演示类型化关系创建
    graph_manager = get_graph_manager()
    
    # 创建测试节点
    test_player1 = PlayerObject("测试玩家1")
    test_player2 = PlayerObject("测试玩家2")
    
    # 使用类型化方法创建关系
    friendship = graph_manager.create_friendship(
        test_player1, test_player2,
        friendship_level="best_friend"
    )
    
    print(f"创建友谊关系类型: {type(friendship).__name__}")
    print(f"友谊等级: {friendship.friendship_level}")


def run_graph_demo():
    """运行完整的图演示"""
    print("=== CampusWorld 图数据结构演示 ===\n")
    
    try:
        # 创建示例图
        create_sample_graph()
        
        # 演示各种功能
        demonstrate_typed_relationships()
        demonstrate_graph_queries()
        demonstrate_graph_traversal()
        demonstrate_performance_features()
        demonstrate_statistics()
        demonstrate_type_safety()
        
        print("\n=== 演示完成 ===")
        
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_graph_demo()
