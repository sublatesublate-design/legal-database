"""
法律数据库 MCP 服务器
提供法律查询、搜索等工具供 Antigravity 调用
"""

import sys
import os
import asyncio
import json
from typing import Any, Sequence

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import mcp.server.stdio

from database.db_manager import DatabaseManager


# 创建服务器实例
app = Server("legal-database")

# 创建数据库管理器
db = DatabaseManager()


@app.list_resources()
async def list_resources() -> list[Resource]:
    """列出可用资源"""
    stats = db.get_statistics()
    
    return [
        Resource(
            uri="legal://stats",
            name="数据库统计信息",
            mimeType="application/json",
            description=f"包含 {stats['total_laws']} 部法律，{stats['total_articles']} 条法条"
        ),
        Resource(
            uri="legal://categories",
            name="法律分类列表",
            mimeType="application/json",
            description="所有法律分类及统计"
        )
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """读取资源内容"""
    if uri == "legal://stats":
        stats = db.get_statistics()
        return json.dumps(stats, ensure_ascii=False, indent=2)
    
    elif uri == "legal://categories":
        stats = db.get_statistics()
        return json.dumps(stats['by_category'], ensure_ascii=False, indent=2)
    
    else:
        raise ValueError(f"未知资源: {uri}")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用工具"""
    return [
        Tool(
            name="search_law",
            description="按名称搜索法律。支持模糊搜索，返回匹配的法律列表及基本信息。",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（法律名称或简称）"
                    },
                   "category": {
                        "type": "string",
                        "description": "可选：法律类别过滤（法律/行政法规/司法解释）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量限制（默认10）",
                        "default": 10
                    }
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="get_law_detail",
            description="获取法律的完整信息和全文。需要提供法律的准确名称。",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "法律名称（需要准确匹配）"
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="search_article",
            description="全文搜索法条内容。可用于查找包含特定关键词的所有法条。",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量限制（默认20）",
                        "default": 20
                    }
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="get_article",
            description="获取法律的特定条文。例如获取《公司法》第三条。",
            inputSchema={
                "type": "object",
                "properties": {
                    "law_title": {
                        "type": "string",
                        "description": "法律名称"
                    },
                    "article_number": {
                        "type": "string",
                        "description": "条文编号（如'第三条'）"
                    }
                },
                "required": ["law_title", "article_number"]
            }
        ),
        Tool(
            name="get_law_articles",
            description="获取某部法律的所有法条。返回结构化的法条列表。",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "法律名称"
                    }
                },
                "required": ["title"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """执行工具调用"""
    
    try:
        if name == "search_law":
            # 搜索法律
            keyword = arguments["keyword"]
            category = arguments.get("category")
            limit = arguments.get("limit", 10)
            
            results = db.search_laws(keyword, category=category, limit=limit)
            
            if not results:
                return [TextContent(
                    type="text",
                    text=f"❌ 未找到匹配 '{keyword}' 的法律"
                )]
            
            # 格式化输出
            output = f"## 搜索结果：'{keyword}'\n\n找到 {len(results)} 部法律：\n\n"
            
            for idx, law in enumerate(results, 1):
                output += f"### {idx}. {law['title']}\n"
                output += f"- **类别**: {law['category']}\n"
                if law.get('document_number'):
                    output += f"- **文号**: {law['document_number']}\n"
                if law.get('publish_date'):
                    output += f"- **发布日期**: {law['publish_date']}\n"
                output += f"- **状态**: {law['status']}\n\n"
            
            return [TextContent(type="text", text=output)]
        
        elif name == "get_law_detail":
            # 获取法律详情
            title = arguments["title"]
            law = db.get_law_by_title(title)
            
            if not law:
                return [TextContent(
                    type="text",
                    text=f"❌ 未找到法律: {title}\n\n提示：请使用search_law工具先搜索准确的法律名称。"
                )]
            
            output = f"# {law['title']}\n\n"
            output += f"**类别**: {law['category']}\n"
            if law.get('issuing_authority'):
                output += f"**发布机关**: {law['issuing_authority']}\n"
            if law.get('document_number'):
                output += f"**文号**: {law['document_number']}\n"
            if law.get('publish_date'):
                output += f"**发布日期**: {law['publish_date']}\n"
            if law.get('effective_date'):
                output += f"**生效日期**: {law['effective_date']}\n"
            output += f"**状态**: {law['status']}\n\n"
            
            if law.get('full_text'):
                output += "## 全文\n\n"
                output += law['full_text']
            
            return [TextContent(type="text", text=output)]
        
        elif name == "search_article":
            # 搜索法条
            keyword = arguments["keyword"]
            limit = arguments.get("limit", 20)
            
            results = db.search_articles(keyword, limit=limit)
            
            if not results:
                return [TextContent(
                    type="text",
                    text=f"❌ 未找到包含 '{keyword}' 的法条"
                )]
            
            output = f"## 法条搜索：'{keyword}'\n\n找到 {len(results)} 条相关法条：\n\n"
            
            for idx, article in enumerate(results, 1):
                output += f"### {idx}. {article['law_title']} - {article['article_number']}\n\n"
                output += f"{article['content']}\n\n"
                output += "---\n\n"
            
            return [TextContent(type="text", text=output)]
        
        elif name == "get_article":
            # 获取特定法条
            law_title = arguments["law_title"]
            article_number = arguments["article_number"]
            
            # 先找到法律
            law = db.get_law_by_title(law_title)
            if not law:
                return [TextContent(
                    type="text",
                    text=f"❌ 未找到法律: {law_title}"
                )]
            
            # 获取所有法条
            articles = db.get_articles_by_law(law['id'])
            
            # 查找指定法条
            target_article = None
            for article in articles:
                if article['article_number'] == article_number:
                    target_article = article
                    break
            
            if not target_article:
                return [TextContent(
                    type="text",
                    text=f"❌ 在《{law_title}》中未找到 {article_number}"
                )]
            
            output = f"## {law['title']} - {article_number}\n\n"
            output += target_article['content']
            
            return [TextContent(type="text", text=output)]
        
        elif name == "get_law_articles":
            # 获取法律所有法条
            title = arguments["title"]
            
            law = db.get_law_by_title(title)
            if not law:
                return [TextContent(
                    type="text",
                    text=f"❌ 未找到法律: {title}"
                )]
            
            articles = db.get_articles_by_law(law['id'])
            
            if not articles:
                return [TextContent(
                    type="text",
                    text=f"⚠️ 《{title}》暂无法条数据"
                )]
            
            output = f"# {law['title']}\n\n"
            output += f"共 {len(articles)} 条\n\n"
            
            for article in articles:
                output += f"## {article['article_number']}\n\n"
                output += f"{article['content']}\n\n"
            
            return [TextContent(type="text", text=output)]
        
        else:
            return [TextContent(
                type="text",
                text=f"❌ 未知工具: {name}"
            )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"❌ 工具执行错误: {str(e)}"
        )]


async def main():
    """运行MCP服务器"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
