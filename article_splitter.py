# -*- coding: utf-8 -*-
"""
ArticleSplitter — 法律条文拆分器 (V3)

将整部法律文本拆分为独立条文，提取：
- article_number_int: 整数序号 (用于精确过滤和排序)
- article_number_str: 字符串序号 (保留 "120之一" 等特殊编号)
- chapter_path: 层级路径 (如 "第四编 人格权 > 第四章 肖像权")
- content: 完整条文内容
"""

import re
import logging

logger = logging.getLogger(__name__)

# ========== cn2an 转换 ==========
try:
    import cn2an as _cn2an_lib

    def cn2an_convert(text: str) -> int:
        """使用 cn2an 库将中文数字转为阿拉伯数字"""
        try:
            return _cn2an_lib.cn2an(text, "smart")
        except Exception:
            return 0
except ImportError:
    logger.warning("cn2an 库未安装，使用内置转换 (pip install cn2an)")

    def cn2an_convert(text: str) -> int:
        """内置中文数字转换 (降级方案)"""
        d = {
            '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            '十': 10, '百': 100, '千': 1000, '万': 10000,
        }
        result = 0
        current = 0
        for ch in text:
            v = d.get(ch)
            if v is None:
                continue
            if v >= 10:
                if current == 0:
                    current = 1
                result += current * v
                current = 0
            else:
                current = v
        result += current
        return result


class ArticleSplitter:
    """将法律全文拆分为独立条文的工具类"""

    # 匹配 "第X条" 开头的行 (支持中文数字、阿拉伯数字、"之一/之二" 后缀)
    ARTICLE_PATTERN = re.compile(
        r'^\s*第(?P<num>[零一二三四五六七八九十百千万]+|\d+)条'
        r'(?P<suffix>之[一二三四五六七八九十]+)?'
        r'(?P<rest>.*)'
    )

    # 匹配层级结构标题
    BIAN_PATTERN = re.compile(r'^\s*第[零一二三四五六七八九十]+编\s+')
    FENBIAN_PATTERN = re.compile(r'^\s*第[零一二三四五六七八九十]+分编\s+')
    ZHANG_PATTERN = re.compile(r'^\s*第[零一二三四五六七八九十]+章\s+')
    JIE_PATTERN = re.compile(r'^\s*第[零一二三四五六七八九十]+节\s+')

    def _parse_article_number(self, num_text: str, suffix: str = None):
        """
        解析条文编号。

        Args:
            num_text: 数字部分 (中文或阿拉伯), e.g. "一百二十" or "120"
            suffix: 后缀部分, e.g. "之一" or None

        Returns:
            (article_number_int, article_number_str)
            e.g. (120, "120之一") or (577, "577")
        """
        # 转为整数
        if num_text.isdigit():
            num_int = int(num_text)
        else:
            num_int = cn2an_convert(num_text)

        # 构造字符串表示
        num_str = str(num_int)
        if suffix:
            num_str += suffix  # e.g. "120之一"

        return num_int, num_str

    def split_law(self, content: str) -> list:
        """
        将法律全文拆分为独立条文列表。

        Args:
            content: 法律全文文本

        Returns:
            list[dict]: 每个 dict 包含:
                - article_number_int (int): 整数编号, 用于排序/过滤
                - article_number_str (str): 字符串编号, 保留 "之一" 等
                - chapter_path (str): 层级路径
                - content (str): 完整条文内容 (含标题行)
        """
        if not content:
            return []

        lines = content.split('\n')
        articles = []

        # 层级状态跟踪 (State Machine)
        current_bian = ""    # 编
        current_fenbian = "" # 分编
        current_zhang = ""   # 章
        current_jie = ""     # 节

        # 当前正在收集的条文
        current_num_int = 0
        current_num_str = ""
        current_chapter_path = ""
        current_lines = []
        collecting = False

        def flush():
            """将当前收集的条文保存"""
            nonlocal collecting
            if collecting and current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    articles.append({
                        'article_number_int': current_num_int,
                        'article_number_str': current_num_str,
                        'chapter_path': current_chapter_path,
                        'content': text,
                    })
            collecting = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if collecting:
                    current_lines.append("")  # 保留空行
                # 如果没在收集条文，忽略空行
                continue

            # 1. 检查层级标题 (编/分编/章/节)
            # 状态机逻辑: 高层级出现时，清空低层级
            if self.BIAN_PATTERN.match(stripped):
                current_bian = stripped
                current_fenbian = ""
                current_zhang = ""
                current_jie = ""
                # 标题行本身不作为条文内容的一部分（通常），这里直接跳过
                # 或者如果需要保留在 content 里，得看需求。一般条文内容只包含“第X条...”
                # 此处策略：跳过，但记录在 chapter_path 中
                continue

            if self.FENBIAN_PATTERN.match(stripped):
                current_fenbian = stripped
                current_zhang = ""
                current_jie = ""
                continue
            
            if self.ZHANG_PATTERN.match(stripped):
                current_zhang = stripped
                current_jie = ""
                continue
            
            if self.JIE_PATTERN.match(stripped):
                current_jie = stripped
                continue

            # 2. 检查是否是条文开头
            m = self.ARTICLE_PATTERN.match(stripped)
            if m:
                flush()  # 保存上一条

                num_text = m.group('num')
                suffix = m.group('suffix')  # 可能是 None

                try:
                    current_num_int, current_num_str = self._parse_article_number(num_text, suffix)
                except Exception as e:
                    logger.warning(f"解析条号失败: 第{num_text}条{suffix or ''} -> {e}")
                    current_num_int = 0
                    current_num_str = num_text + (suffix or "")

                # 构造 chapter_path (Book > Part > Chapter > Section)
                parts = [p for p in [current_bian, current_fenbian, current_zhang, current_jie] if p]
                current_chapter_path = " > ".join(parts)

                current_lines = [stripped]
                collecting = True
            else:
                # 3. 非标题行 → 追加到当前条文
                if collecting:
                    current_lines.append(line.rstrip())

        # 最后一条
        flush()

        return articles


# ========== 独立测试 ==========
if __name__ == "__main__":
    splitter = ArticleSplitter()

    test_text = """
    中华人民共和国民法典

    第一编 总则
    
    第一章 基本规定

    第一条 为了保护民事主体的合法权益，本法特此制定。

    第二编 物权
    
    第一分编 通则
    
    第一章 一般规定

    第一百一十四条 民事主体依法享有物权。
    """

    results = splitter.split_law(test_text)
    print(f"解析出 {len(results)} 条:")
    for r in results:
        print(f"  [{r['article_number_int']:>4}] "
              f"Path: {r['chapter_path'][:50]:<50} | {r['content'][:20]}...")
