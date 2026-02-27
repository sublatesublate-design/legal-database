"""
爬虫基类
提供通用的爬虫功能和工具方法
"""

import requests
import time
import random
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class BaseCrawler:
    """爬虫基类"""
    
    # User-Agent列表，用于轮换
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    def __init__(self, base_url: str, delay: float = 2.0):
        """
        初始化爬虫
        
        Args:
            base_url: 基础URL
            delay: 请求延迟（秒），避免被封
        """
        self.base_url = base_url
        self.delay = delay
        self.session = requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 设置默认请求头
        self.session.headers.update({
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def get(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """
        发送GET请求（带重试机制）
        
        Args:
            url: 请求URL
            params: URL参数
            max_retries: 最大重试次数
            
        Returns:
            响应对象，失败返回None
        """
        # 构建完整URL
        if not url.startswith('http'):
            url = urljoin(self.base_url, url)
        
        for attempt in range(max_retries):
            try:
                # 随机延迟，模拟人类行为
                time.sleep(self.delay + random.uniform(0, 1))
                
                # 轮换User-Agent
                self.session.headers['User-Agent'] = random.choice(self.USER_AGENTS)
                
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                self.logger.debug(f"✅ 成功获取: {url}")
                return response
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"⚠️ 请求失败 (尝试 {attempt + 1}/{max_retries}): {url} - {e}")
                
                if attempt == max_retries - 1:
                    self.logger.error(f"❌ 请求最终失败: {url}")
                    return None
                
                # 指数退避
                time.sleep(2 ** attempt)
        
        return None
    
    def parse_html(self, html: str) -> Optional[BeautifulSoup]:
        """
        解析HTML
        
        Args:
            html: HTML字符串
            
        Returns:
            BeautifulSoup对象
        """
        try:
            return BeautifulSoup(html, 'lxml')
        except Exception as e:
            self.logger.error(f"❌ HTML解析失败: {e}")
            return None
    
    def extract_text(self, element, default: str = "") -> str:
        """
        安全地提取元素文本
        
        Args:
            element: BeautifulSoup元素
            default: 默认值
            
        Returns:
            文本内容
        """
        if element:
            text = element.get_text(strip=True)
            return text if text else default
        return default
    
    def clean_text(self, text: str) -> str:
        """
        清理文本（去除多余空白字符等）
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ""
        
        # 替换多个空白字符为单个空格
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text
    
    def save_html(self, html: str, filename: str):
        """
        保存HTML到文件（用于调试）
        
        Args:
            html: HTML内容
            filename: 文件名
        """
        import os
        os.makedirs('logs/html', exist_ok=True)
        
        filepath = f'logs/html/{filename}'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        self.logger.info(f"💾 HTML已保存: {filepath}")
    
    def extract_date(self, date_str: str) -> Optional[str]:
        """
        提取并标准化日期
        
        Args:
            date_str: 日期字符串（各种格式）
            
        Returns:
            标准化日期 (YYYY-MM-DD)
        """
        import re
        from datetime import datetime
        
        if not date_str:
            return None
        
        # 尝试各种日期格式
        patterns = [
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '%Y-%m-%d'),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', '%Y-%m-%d'),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y-%m-%d'),
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    year, month, day = groups
                    try:
                        date_obj = datetime(int(year), int(month), int(day))
                        return date_obj.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
        
        return None
    
    def crawl(self):
        """
        爬取方法（子类实现）
        """
        raise NotImplementedError("子类必须实现crawl方法")


# 测试代码
if __name__ == "__main__":
    # 测试基类功能
    crawler = BaseCrawler("https://flk.npc.gov.cn")
    
    # 测试日期提取
    test_dates = [
        "2023年12月31日",
        "2023-12-31",
        "2023.12.31",
        "发布于2023年1月1日生效"
    ]
    
    print("📅 日期提取测试:")
    for date_str in test_dates:
        result = crawler.extract_date(date_str)
        print(f"  {date_str} -> {result}")
