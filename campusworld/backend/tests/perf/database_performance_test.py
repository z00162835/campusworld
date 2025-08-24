#!/usr/bin/env python3
"""
CampusWorld 数据库性能测试脚本

测试新的优化数据库结构的性能
包括查询性能、索引效果、并发性能等

作者：AI Assistant
创建时间：2025-08-24
"""

import os
import sys
import time
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import statistics

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# 配置
DATABASE_URL = os.getenv('DATABASE_URL', "postgresql://campusworld:campusworld@localhost:5433/campusworld")


class DatabasePerformanceTester:
    """数据库性能测试器"""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        
    def generate_test_data(self, node_count: int = 1000, relationship_count: int = 5000):
        """生成测试数据"""
        print(f"🔄 生成测试数据: {node_count} 个节点, {relationship_count} 个关系...")
        
        try:
            with self.Session() as session:
                # 生成节点数据
                nodes = []
                for i in range(node_count):
                    node_type = random.choice(['user', 'campus', 'world', 'world_object'])
                    node = {
                        'uuid': str(uuid.uuid4()),
                        'type_code': node_type,
                        'name': f'测试{node_type}{i}',
                        'description': f'这是第{i}个{node_type}的描述',
                        'is_active': random.choice([True, True, True, False]),  # 75% 活跃
                        'is_public': random.choice([True, True, False]),  # 67% 公开
                        'access_level': random.choice(['normal', 'vip', 'admin']),
                        'attributes': {
                            'score': random.randint(1, 100),
                            'level': random.randint(1, 50),
                            'status': random.choice(['active', 'inactive', 'pending']),
                            'created_by': f'user_{random.randint(1, 100)}',
                            'tags': random.sample(['tag1', 'tag2', 'tag3', 'tag4', 'tag5'], random.randint(1, 3))
                        },
                        'tags': random.sample(['热门', '推荐', '新用户', '活跃', 'VIP'], random.randint(1, 3))
                    }
                    nodes.append(node)
                
                # 批量插入节点
                for node_data in nodes:
                    session.execute(text("""
                        INSERT INTO nodes (
                            uuid, type_id, type_code, name, description, is_active, 
                            is_public, access_level, attributes, tags
                        )
                        SELECT 
                            :uuid::uuid,
                            nt.id,
                            :type_code,
                            :name,
                            :description,
                            :is_active,
                            :is_public,
                            :access_level,
                            :attributes::jsonb,
                            :tags::jsonb
                        FROM node_types nt
                        WHERE nt.type_code = :type_code
                    """), node_data)
                
                session.commit()
                print(f"  ✅ 生成了 {node_count} 个节点")
                
                # 生成关系数据
                relationships = []
                for i in range(relationship_count):
                    source_id = random.randint(1, node_count)
                    target_id = random.randint(1, node_count)
                    if source_id != target_id:
                        rel_type = random.choice(['member', 'friend', 'owns', 'location'])
                        relationship = {
                            'uuid': str(uuid.uuid4()),
                            'type_code': rel_type,
                            'source_id': source_id,
                            'target_id': target_id,
                            'is_active': random.choice([True, True, True, False]),
                            'weight': random.randint(1, 10),
                            'attributes': {
                                'created_at': datetime.now().isoformat(),
                                'reason': f'关系原因{i}',
                                'strength': random.randint(1, 100)
                            }
                        }
                        relationships.append(relationship)
                
                # 批量插入关系
                for rel_data in relationships:
                    session.execute(text("""
                        INSERT INTO relationships (
                            uuid, type_id, type_code, source_id, target_id, 
                            is_active, weight, attributes
                        )
                        SELECT 
                            :uuid::uuid,
                            rt.id,
                            :type_code,
                            :source_id,
                            :target_id,
                            :is_active,
                            :weight,
                            :attributes::jsonb
                        FROM relationship_types rt
                        WHERE rt.type_code = :type_code
                    """), rel_data)
                
                session.commit()
                print(f"  ✅ 生成了 {len(relationships)} 个关系")
                
                return True
                
        except SQLAlchemyError as e:
            print(f"  ❌ 生成测试数据失败: {e}")
            return False
            
    def test_basic_queries(self):
        """测试基础查询性能"""
        print("🧪 测试基础查询性能...")
        
        results = {}
        
        try:
            with self.Session() as session:
                # 测试1: 简单查询
                start_time = time.time()
                result = session.execute(text("SELECT COUNT(*) FROM nodes WHERE is_active = TRUE"))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['simple_count'] = query_time
                print(f"  ✅ 简单计数查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试2: 类型查询
                start_time = time.time()
                result = session.execute(text("SELECT COUNT(*) FROM nodes WHERE type_code = 'user'"))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['type_query'] = query_time
                print(f"  ✅ 类型查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试3: 属性查询
                start_time = time.time()
                result = session.execute(text("SELECT COUNT(*) FROM nodes WHERE attributes @> '{\"status\": \"active\"}'::jsonb"))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['attribute_query'] = query_time
                print(f"  ✅ 属性查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试4: 标签查询
                start_time = time.time()
                result = session.execute(text("SELECT COUNT(*) FROM nodes WHERE tags ? '热门'"))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['tag_query'] = query_time
                print(f"  ✅ 标签查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试5: 复合查询
                start_time = time.time()
                result = session.execute(text("""
                    SELECT COUNT(*) FROM nodes 
                    WHERE type_code = 'user' 
                    AND is_active = TRUE 
                    AND attributes @> '{"level": 10}'::jsonb
                """))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['complex_query'] = query_time
                print(f"  ✅ 复合查询: {query_time:.4f}s ({count} 条记录)")
                
        except SQLAlchemyError as e:
            print(f"  ❌ 基础查询测试失败: {e}")
            return {}
            
        return results
        
    def test_graph_queries(self):
        """测试图查询性能"""
        print("🧪 测试图查询性能...")
        
        results = {}
        
        try:
            with self.Session() as session:
                # 测试1: 关系查询
                start_time = time.time()
                result = session.execute(text("""
                    SELECT COUNT(*) FROM relationships r
                    JOIN nodes n1 ON r.source_id = n1.id
                    JOIN nodes n2 ON r.target_id = n2.id
                    WHERE r.type_code = 'member' AND r.is_active = TRUE
                """))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['relationship_query'] = query_time
                print(f"  ✅ 关系查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试2: 路径查询（2跳）
                start_time = time.time()
                result = session.execute(text("""
                    SELECT COUNT(*) FROM (
                        SELECT DISTINCT r1.source_id, r2.target_id
                        FROM relationships r1
                        JOIN relationships r2 ON r1.target_id = r2.source_id
                        WHERE r1.type_code = 'member' AND r2.type_code = 'owns'
                        AND r1.is_active = TRUE AND r2.is_active = TRUE
                    ) paths
                """))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['path_query_2hop'] = query_time
                print(f"  ✅ 2跳路径查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试3: 聚合查询
                start_time = time.time()
                result = session.execute(text("""
                    SELECT 
                        n.type_code,
                        COUNT(*) as node_count,
                        AVG((n.attributes->>'score')::int) as avg_score
                    FROM nodes n
                    WHERE n.is_active = TRUE
                    GROUP BY n.type_code
                    ORDER BY node_count DESC
                """))
                rows = result.fetchall()
                query_time = time.time() - start_time
                results['aggregation_query'] = query_time
                print(f"  ✅ 聚合查询: {query_time:.4f}s ({len(rows)} 个分组)")
                
        except SQLAlchemyError as e:
            print(f"  ❌ 图查询测试失败: {e}")
            return {}
            
        return results
        
    def test_index_performance(self):
        """测试索引性能"""
        print("🧪 测试索引性能...")
        
        results = {}
        
        try:
            with self.Session() as session:
                # 测试1: 无索引查询（模拟）
                start_time = time.time()
                result = session.execute(text("""
                    SELECT COUNT(*) FROM nodes 
                    WHERE name ILIKE '%测试%'
                """))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['no_index_query'] = query_time
                print(f"  ✅ 无索引查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试2: 有索引查询
                start_time = time.time()
                result = session.execute(text("""
                    SELECT COUNT(*) FROM nodes 
                    WHERE type_code = 'user' AND is_active = TRUE
                """))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['indexed_query'] = query_time
                print(f"  ✅ 有索引查询: {query_time:.4f}s ({count} 条记录)")
                
                # 测试3: JSONB索引查询
                start_time = time.time()
                result = session.execute(text("""
                    SELECT COUNT(*) FROM nodes 
                    WHERE attributes @> '{"status": "active", "level": 10}'::jsonb
                """))
                count = result.fetchone()[0]
                query_time = time.time() - start_time
                results['jsonb_index_query'] = query_time
                print(f"  ✅ JSONB索引查询: {query_time:.4f}s ({count} 条记录)")
                
        except SQLAlchemyError as e:
            print(f"  ❌ 索引性能测试失败: {e}")
            return {}
            
        return results
        
    def test_concurrent_performance(self, concurrent_users: int = 10, queries_per_user: int = 100):
        """测试并发性能"""
        print(f"🧪 测试并发性能: {concurrent_users} 个并发用户, 每个 {queries_per_user} 次查询...")
        
        import threading
        import queue
        
        results_queue = queue.Queue()
        
        def worker(worker_id: int):
            """工作线程"""
            try:
                engine = create_engine(DATABASE_URL)
                Session = sessionmaker(bind=engine)
                
                query_times = []
                for i in range(queries_per_user):
                    query_type = random.choice(['simple', 'type', 'attribute', 'tag'])
                    
                    with Session() as session:
                        start_time = time.time()
                        
                        if query_type == 'simple':
                            session.execute(text("SELECT COUNT(*) FROM nodes WHERE is_active = TRUE"))
                        elif query_type == 'type':
                            session.execute(text("SELECT COUNT(*) FROM nodes WHERE type_code = 'user'"))
                        elif query_type == 'attribute':
                            session.execute(text("SELECT COUNT(*) FROM nodes WHERE attributes @> '{\"status\": \"active\"}'::jsonb"))
                        elif query_type == 'tag':
                            session.execute(text("SELECT COUNT(*) FROM nodes WHERE tags ? '热门'"))
                        
                        query_time = time.time() - start_time
                        query_times.append(query_time)
                        
                results_queue.put({
                    'worker_id': worker_id,
                    'query_times': query_times,
                    'avg_time': statistics.mean(query_times),
                    'total_time': sum(query_times)
                })
                
            except Exception as e:
                results_queue.put({
                    'worker_id': worker_id,
                    'error': str(e)
                })
        
        # 启动工作线程
        threads = []
        start_time = time.time()
        
        for i in range(concurrent_users):
            thread = threading.Thread(target=worker, args=(i,))
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # 收集结果
        worker_results = []
        while not results_queue.empty():
            worker_results.append(results_queue.get())
        
        # 计算统计信息
        all_query_times = []
        successful_workers = 0
        
        for result in worker_results:
            if 'error' not in result:
                successful_workers += 1
                all_query_times.extend(result['query_times'])
        
        if all_query_times:
            avg_query_time = statistics.mean(all_query_times)
            total_queries = len(all_query_times)
            qps = total_queries / total_time  # 每秒查询数
            
            print(f"  ✅ 并发测试完成:")
            print(f"     - 成功工作线程: {successful_workers}/{concurrent_users}")
            print(f"     - 总查询数: {total_queries}")
            print(f"     - 总时间: {total_time:.2f}s")
            print(f"     - 平均查询时间: {avg_query_time:.4f}s")
            print(f"     - 查询吞吐量: {qps:.2f} QPS")
            
            return {
                'concurrent_users': concurrent_users,
                'successful_workers': successful_workers,
                'total_queries': total_queries,
                'total_time': total_time,
                'avg_query_time': avg_query_time,
                'qps': qps
            }
        else:
            print(f"  ❌ 并发测试失败: 没有成功的查询")
            return {}
            
    def run_performance_test(self):
        """运行完整性能测试"""
        print("🚀 开始数据库性能测试...")
        print("=" * 60)
        
        # 1. 生成测试数据
        if not self.generate_test_data():
            return False
            
        print()
        
        # 2. 基础查询性能测试
        basic_results = self.test_basic_queries()
        print()
        
        # 3. 图查询性能测试
        graph_results = self.test_graph_queries()
        print()
        
        # 4. 索引性能测试
        index_results = self.test_index_performance()
        print()
        
        # 5. 并发性能测试
        concurrent_results = self.test_concurrent_performance()
        print()
        
        # 6. 生成性能报告
        self.generate_performance_report(basic_results, graph_results, index_results, concurrent_results)
        
        return True
        
    def generate_performance_report(self, basic_results, graph_results, index_results, concurrent_results):
        """生成性能测试报告"""
        print("📊 性能测试报告")
        print("=" * 60)
        
        # 基础查询性能
        if basic_results:
            print("\n🔍 基础查询性能:")
            for query_type, time_taken in basic_results.items():
                print(f"  - {query_type}: {time_taken:.4f}s")
            
            avg_basic_time = statistics.mean(basic_results.values())
            print(f"  - 平均查询时间: {avg_basic_time:.4f}s")
        
        # 图查询性能
        if graph_results:
            print("\n🔍 图查询性能:")
            for query_type, time_taken in graph_results.items():
                print(f"  - {query_type}: {time_taken:.4f}s")
            
            avg_graph_time = statistics.mean(graph_results.values())
            print(f"  - 平均查询时间: {avg_graph_time:.4f}s")
        
        # 索引性能
        if index_results:
            print("\n🔍 索引性能:")
            for query_type, time_taken in index_results.items():
                print(f"  - {query_type}: {time_taken:.4f}s")
            
            # 计算索引效果
            if 'no_index_query' in index_results and 'indexed_query' in index_results:
                improvement = (index_results['no_index_query'] - index_results['indexed_query']) / index_results['no_index_query'] * 100
                print(f"  - 索引优化效果: {improvement:.1f}%")
        
        # 并发性能
        if concurrent_results:
            print("\n🔍 并发性能:")
            print(f"  - 并发用户数: {concurrent_results.get('concurrent_users', 0)}")
            print(f"  - 成功工作线程: {concurrent_results.get('successful_workers', 0)}")
            print(f"  - 总查询数: {concurrent_results.get('total_queries', 0)}")
            print(f"  - 总时间: {concurrent_results.get('total_time', 0):.2f}s")
            print(f"  - 平均查询时间: {concurrent_results.get('avg_query_time', 0):.4f}s")
            print(f"  - 查询吞吐量: {concurrent_results.get('qps', 0):.2f} QPS")
        
        print("\n" + "=" * 60)
        print("🎉 性能测试完成！")


def main():
    """主函数"""
    print("CampusWorld 数据库性能测试工具")
    print("=" * 60)
    
    # 检查环境变量
    database_url = os.getenv('DATABASE_URL', DATABASE_URL)
    
    # 创建测试器
    tester = DatabasePerformanceTester(database_url)
    
    # 运行性能测试
    success = tester.run_performance_test()
    
    if success:
        print("\n✅ 性能测试完成！")
        print("\n📋 建议:")
        print("1. 根据测试结果优化数据库配置")
        print("2. 调整索引策略以提高查询性能")
        print("3. 监控生产环境的实际性能表现")
    else:
        print("\n❌ 性能测试失败！请检查错误日志。")
        sys.exit(1)


if __name__ == "__main__":
    main()
