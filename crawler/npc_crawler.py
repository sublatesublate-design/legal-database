"""
全国人大法律法规数据库爬虫
从 flk.npc.gov.cn 采集法律数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.base_crawler import BaseCrawler
from database.db_manager import DatabaseManager
import re
from typing import List, Dict, Optional
from tqdm import tqdm


class NPCCrawler(BaseCrawler):
    """全国人大法规库爬虫"""
    
    # 法律分类映射
    CATEGORIES = {
        'law': '法律',
        'admin_reg': '行政法规',
        'judicial_interpretation': '司法解释',
    }
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化爬虫
        
        Args:
            db_manager: 数据库管理器实例
        """
        super().__init__(base_url="https://flk.npc.gov.cn", delay=3.0)
        self.db = db_manager
    
    def crawl_law_list(self, category: str = 'law', limit: int = None) -> List[Dict]:
        """
        爬取法律列表
        
        Args:
            category: 法律类别
            limit: 限制数量（测试用）
            
        Returns:
            法律基本信息列表
        """
        self.logger.info(f"🔍 开始爬取法律列表: {self.CATEGORIES.get(category, category)}")
        
        laws = []
        page = 1
        
        while True:
            # 构建列表页URL（需要根据实际网站调整）
            url = f"/fl.html"  # 法律首页
            
            response = self.get(url)
            if not response:
                break
            
            soup = self.parse_html(response.text)
            if not soup:
                break
            
            # 解析法律列表（需要根据实际HTML结构调整）
            law_items = soup.select('.law-item')  # 示例选择器
            
            if not law_items:
                self.logger.warning("⚠️ 未找到法律条目，可能需要调整选择器")
                break
            
            for item in law_items:
                try:
                    law_info = self._parse_law_item(item)
                    if law_info:
                        laws.append(law_info)
                        
                        if limit and len(laws) >= limit:
                            return laws
                except Exception as e:
                    self.logger.error(f"❌ 解析法律条目失败: {e}")
                    continue
            
            page += 1
            
            # 检查是否有下一页
            if not soup.select('.next-page'):
                break
        
        self.logger.info(f"✅ 共找到 {len(laws)} 部法律")
        return laws
    
    def _parse_law_item(self, item) -> Optional[Dict]:
        """
        解析单个法律条目
        
        Args:
            item: BeautifulSoup元素
            
        Returns:
            法律基本信息字典
        """
        try:
            # 提取标题和链接（需要根据实际HTML调整）
            title_elem = item.select_one('.title a')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            detail_url = title_elem.get('href', '')
            
            # 提取其他信息
            info = {
                'title': title,
                'detail_url': detail_url,
                'category': '法律',
                'status': 'active'
            }
            
            # 提取发布日期
            date_elem = item.select_one('.publish-date')
            if date_elem:
                date_str = self.extract_text(date_elem)
                info['publish_date'] = self.extract_date(date_str)
            
            # 提取文号
            doc_num_elem = item.select_one('.doc-number')
            if doc_num_elem:
                info['document_number'] = self.extract_text(doc_num_elem)
            
            return info
            
        except Exception as e:
            self.logger.error(f"❌ 解析条目失败: {e}")
            return None
    
    def crawl_law_detail(self, law_info: Dict) -> Optional[Dict]:
        """
        爬取法律详情（全文和法条）
        
        Args:
            law_info: 法律基本信息
            
        Returns:
            完整的法律数据
        """
        url = law_info.get('detail_url')
        if not url:
            return None
        
        self.logger.info(f"📖 爬取法律详情: {law_info['title']}")
        
        response = self.get(url)
        if not response:
            return None
        
        soup = self.parse_html(response.text)
        if not soup:
            return None
        
        # 提取全文
        content_elem = soup.select_one('.law-content')
        if content_elem:
            full_text = content_elem.get_text(separator='\n', strip=True)
            law_info['full_text'] = full_text
            law_info['source_url'] = url
            
            # 提取法条
            articles = self._extract_articles(content_elem)
            law_info['articles'] = articles
        
        return law_info
    
    def _extract_articles(self, content_elem) -> List[Dict]:
        """
        从全文中提取法条
        
        Args:
            content_elem: 内容元素
            
        Returns:
            法条列表
        """
        articles = []
        
        # 查找所有条文（通常以"第X条"开头）
        text = content_elem.get_text()
        pattern = r'第([一二三四五六七八九十百千\d]+)条\s+(.*?)(?=第[一二三四五六七八九十百千\d]+条|$)'
        
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for idx, match in enumerate(matches, 1):
            article_num_cn = match.group(1)
            article_content = match.group(2).strip()
            
            articles.append({
                'article_number': f'第{article_num_cn}条',
                'article_index': idx,
                'content': article_content
            })
        
        self.logger.debug(f"  提取了 {len(articles)} 条法条")
        return articles
    
    def save_law(self, law_data: Dict) -> bool:
        """
        保存法律到数据库
        
        Args:
            law_data: 法律数据
            
        Returns:
            是否成功
        """
        try:
            # 检查是否已存在
            existing = self.db.get_law_by_title(law_data['title'])
            if existing:
                self.logger.info(f"⏭️  法律已存在: {law_data['title']}")
                return False
            
            # 插入法律主记录
            law_id = self.db.insert_law(law_data)
            self.logger.info(f"✅ 保存法律: {law_data['title']} (ID: {law_id})")
            
            # 插入法条
            if 'articles' in law_data:
                for article in law_data['articles']:
                    article['law_id'] = law_id
                    self.db.insert_article(article)
                
                self.logger.debug(f"  保存了 {len(law_data['articles'])} 条法条")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 保存法律失败: {e}")
            return False
    
    def crawl(self, limit: int = None):
        """
        执行完整爬取流程
        
        Args:
            limit: 限制爬取数量
        """
        self.logger.info("🚀 开始爬取全国人大法律数据库")
        
        # 1. 爬取法律列表
        law_list = self.crawl_law_list(limit=limit)
        
        # 2. 爬取每部法律的详情
        success_count = 0
        
        for law_info in tqdm(law_list, desc="爬取法律详情"):
            # 获取详情
            law_data = self.crawl_law_detail(law_info)
            
            if law_data:
                # 保存到数据库
                if self.save_law(law_data):
                    success_count += 1
        
        self.logger.info(f"✅ 爬取完成！成功保存 {success_count}/{len(law_list)} 部法律")
        
        # 显示统计
        stats = self.db.get_statistics()
        self.logger.info(f"📊 数据库统计: {stats}")


# 测试代码
if __name__ == "__main__":
    # 创建数据库
    db = DatabaseManager()
    
    # 创建爬虫
    crawler = NPCCrawler(db)
    
    # 测试模式：只爬取5部法律
    crawler.crawl(limit=5)
