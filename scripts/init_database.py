"""
初始化数据库脚本
创建数据库和所有表
"""

import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


def main():
    """主函数"""
    print("🔨 开始初始化法律数据库...")
    
    # 创建数据库管理器（会自动创建数据库和表）
    db = DatabaseManager()
    
    print("\n📊 数据库统计信息:")
    stats = db.get_statistics()
    
    print(f"  ✅ 法律总数: {stats['total_laws']}")
    print(f"  ✅ 法条总数: {stats['total_articles']}")
    print(f"  ✅ 数据库大小: {stats['db_size_mb']:.2f} MB")
    
    if stats['by_category']:
        print(f"  ✅ 分类统计:")
        for category, count in stats['by_category'].items():
            print(f"     - {category}: {count}")
    
    print("\n✅ 数据库初始化完成！")
    print(f"📁 数据库位置: {os.path.abspath(db.db_path)}")


if __name__ == "__main__":
    main()
