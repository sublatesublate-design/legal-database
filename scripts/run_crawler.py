"""
运行爬虫脚本
支持测试模式和完整模式
"""

import sys
import os
import argparse
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from crawler.npc_crawler import NPCCrawler


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='法律数据库爬虫')
    parser.add_argument('--test', action='store_true', help='测试模式（只爬取少量数据）')
    parser.add_argument('--limit', type=int, default=10, help='测试模式下爬取数量（默认10）')
    parser.add_argument('--full', action='store_true', help='完整模式（爬取所有数据）')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🕷️  法律数据库爬虫")
    print("=" * 60)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 创建数据库
    print("📊 初始化数据库...")
    db = DatabaseManager()
    
    # 显示当前统计
    stats = db.get_statistics()
    print(f"当前数据库状态：")
    print(f"  - 法律总数: {stats['total_laws']}")
    print(f"  - 法条总数: {stats['total_articles']}")
    print(f"  - 数据库大小: {stats['db_size_mb']:.2f} MB\n")
    
    # 创建爬虫
    print("🔨 创建爬虫实例...")
    crawler = NPCCrawler(db)
    
    # 确定爬取模式
    if args.full:
        print("\n🚀 开始完整爬取（这可能需要数小时）...")
        print("💡 提示：您可以随时按 Ctrl+C 中断爬取\n")
        limit = None
    else:
        limit = args.limit
        print(f"\n🧪 测试模式：爬取 {limit} 部法律\n")
    
    # 开始爬取
    try:
        crawler.crawl(limit=limit)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断爬取")
    except Exception as e:
        print(f"\n\n❌ 爬取过程出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 显示最终统计
    print("\n" + "=" * 60)
    print("📊 最终统计")
    print("=" * 60)
    
    stats = db.get_statistics()
    print(f"  ✅ 法律总数: {stats['total_laws']}")
    print(f"  ✅ 法条总数: {stats['total_articles']}")
    print(f"  ✅ 数据库大小: {stats['db_size_mb']:.2f} MB")
    
    if stats['by_category']:
        print(f"\n  分类统计:")
        for category, count in stats['by_category'].items():
            print(f"    - {category}: {count}")
    
    print(f"\n⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
