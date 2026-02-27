"""
国家法律法规数据库 - 自动化批量下载工具

使用Selenium自动化浏览器操作，批量下载法律法规数据库中的所有文件。
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_download.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class LegalDatabaseDownloader:
    """法律数据库批量下载器"""
    
    def __init__(self, headless=False, download_dir=None):
        """
        初始化下载器
        
        Args:
            headless: 是否使用无头模式
            download_dir: 下载目录路径
        """
        self.headless = headless
        self.download_dir = download_dir or config.DOWNLOAD_DIR
        self.driver = None
        self.wait = None
        
    def setup_driver(self):
        """设置Chrome浏览器驱动"""
        logger.info("正在初始化Chrome浏览器...")
        
        chrome_options = Options()
        
        # 设置下载目录
        download_path = str(Path(self.download_dir).absolute())
        os.makedirs(download_path, exist_ok=True)
        
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # 其他浏览器选项
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument(f"--window-size={config.WINDOW_SIZE[0]},{config.WINDOW_SIZE[1]}")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # 初始化驱动 - 支持多种方式
        try:
            # 方式0: 尝试使用当前目录下的 chromedriver.exe
            local_driver = Path("chromedriver.exe").absolute()
            if local_driver.exists():
                logger.info(f"发现本地ChromeDriver: {local_driver}")
                service = Service(executable_path=str(local_driver))
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info("成功使用本地ChromeDriver")
            else:
                raise FileNotFoundError("未发现本地ChromeDriver")
                
        except Exception as e0:
            logger.info(f"无法使用本地ChromeDriver: {e0}")
            try:
                # 方式1: 尝试使用系统环境变量中的 ChromeDriver
                logger.info("尝试使用系统ChromeDriver...")
                self.driver = webdriver.Chrome(options=chrome_options)
                logger.info("成功使用系统ChromeDriver")
            except Exception as e1:
                logger.warning(f"无法使用系统ChromeDriver: {e1}")
                try:
                    # 方式2: 尝试使用 webdriver-manager 下载
                    logger.info("尝试使用webdriver-manager下载ChromeDriver...")
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    logger.info("成功使用webdriver-manager")
                except Exception as e2:
                    logger.error(f"无法使用webdriver-manager: {e2}")
                    raise Exception(
                        "无法初始化ChromeDriver。请尝试以下解决方案：\n"
                        "1. 手动下载ChromeDriver并放在程序根目录下\n"
                        "2. 手动下载ChromeDriver并添加到系统PATH\n"
                        "3. 检查网络连接，确保能访问Google服务"
                    )
        
        self.driver.implicitly_wait(config.IMPLICIT_WAIT)
        self.wait = WebDriverWait(self.driver, config.EXPLICIT_WAIT)
        
        logger.info("浏览器初始化完成")
        
    def navigate_to_category(self, category_name):
        """
        导航到指定的法律分类
        
        Args:
            category_name: 分类名称（法律、行政法规、地方性法规、司法解释）
        
        Returns:
            bool: 是否成功导航
        """
        logger.info(f"正在导航到分类: {category_name}")
        
        try:
            # 打开首页
            self.driver.get(config.HOMEPAGE_URL)
            time.sleep(config.PAGE_LOAD_WAIT)
            
            # 查找并点击对应的分类按钮
            # 尝试多种可能的选择器
            selectors = [
                f"//div[text()='{category_name}']",
                f"//div[contains(@class, 'label') and text()='{category_name}']",
                f"//div[contains(@class, 'law')]//div[text()='{category_name}']"
            ]
            
            category_element = None
            for selector in selectors:
                try:
                    category_element = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if category_element:
                        break
                except TimeoutException:
                    continue
            
            if category_element:
                category_element.click()
                logger.info(f"成功点击分类: {category_name}")
                
                # 处理可能打开的新标签页
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    logger.info("切换到新打开的标签页")
                
                time.sleep(config.PAGE_LOAD_WAIT)
                return True
            else:
                logger.error(f"未找到分类按钮: {category_name}")
                return False
                
        except Exception as e:
            logger.error(f"导航到分类时出错: {e}")
            return False
    
    def apply_status_filter(self, status):
        """
        应用法律状态过滤
        
        Args:
            status: 状态名称 (有效, 已修改, 尚未生效, 已废止)
            
        Returns:
            bool: 是否成功应用
        """
        if not status:
            return True
            
        logger.info(f"正在应用状态过滤: {status}")
        
        try:
            # 找到对应的状态值
            status_value = config.STATUS_MAPPING.get(status)
            if not status_value:
                logger.error(f"未知的状态名称: {status}")
                return False
                
            # 找到所有的状态复选框
            js_filter = f"""
            const checkboxes = Array.from(document.querySelectorAll('.el-checkbox'));
            let targetLabel = null;
            let otherLabels = [];
            
            checkboxes.forEach(cb => {{
                const text = cb.innerText.trim();
                const input = cb.querySelector('input');
                if (text === '{status}') {{
                    targetLabel = cb;
                }} else if (['有效', '已修改', '尚未生效', '已废止'].includes(text)) {{
                    otherLabels.push(cb);
                }}
            }});
            
            if (targetLabel) {{
                // 确保目标状态被选中
                const targetInput = targetLabel.querySelector('input');
                if (!targetInput.checked) {{
                    targetLabel.click();
                }}
                
                // 确保其他状态未被选中
                otherLabels.forEach(cb => {{
                    const input = cb.querySelector('input');
                    if (input.checked) {{
                        cb.click();
                    }}
                }});
                return 'Status filter applied';
            }}
            return 'Status filter not found';
            """
            
            result = self.driver.execute_script(js_filter)
            logger.info(f"状态过滤结果: {result}")
            
            if "not found" in result:
                return False
                
            time.sleep(config.PAGE_LOAD_WAIT)
            return True
            
        except Exception as e:
            logger.error(f"应用状态过滤时出错: {e}")
            return False

    def set_items_per_page(self, items=100):
        """
        设置每页显示的条目数
        
        Args:
            items: 每页条目数（默认100）
        
        Returns:
            bool: 是否成功设置
        """
        logger.info(f"正在设置每页显示 {items} 条...")
        
        try:
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 查找并点击选择器
            selector_css = config.SELECTORS["page_size_selector"]
            js_click_selector = f"""
            const el = document.querySelector('{selector_css}');
            if (el) {{
                el.click();
                return 'Selector clicked';
            }}
            return 'Selector not found';
            """
            
            result = self.driver.execute_script(js_click_selector)
            logger.info(f"点击选择器结果: {result}")
            if "not found" in result:
                # 尝试普通点击
                try:
                    el = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector_css)))
                    el.click()
                    logger.info("普通点击选择器成功")
                except Exception as e:
                    logger.error(f"普通点击选择器失败: {e}")
                    return False
            
            time.sleep(2)
            
            # 使用XPath点击选项
            option_xpath = config.SELECTORS["page_size_100_option_xpath"]
            js_select_option = f"""
            const result = document.evaluate("{option_xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (result) {{
                result.click();
                return 'Option clicked';
            }}
            return 'Option not found';
            """
            
            result = self.driver.execute_script(js_select_option)
            logger.info(f"选择选项结果: {result}")
            if "not found" in result:
                try:
                    el = self.wait.until(EC.element_to_be_clickable((By.XPATH, option_xpath)))
                    el.click()
                    logger.info("普通点击选项成功")
                except Exception as e:
                    logger.error(f"普通点击选项失败: {e}")
                    return False
            
            logger.info(f"成功设置每页 {items} 条")
            time.sleep(config.PAGE_LOAD_WAIT)
            
            # 滚动回顶部
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"设置每页条目数时出错: {e}")
            return False
    
    def get_total_pages(self):
        """
        获取总页数
        
        Returns:
            int: 总页数，失败返回0
        """
        try:
            # 滚动到底部查看分页信息
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # 查找所有分页按钮
            pager_xpath = "//ul[@class='el-pager']/li[not(contains(@class, 'is-active'))]"
            page_elements = self.driver.find_elements(By.XPATH, pager_xpath)
            
            if page_elements:
                # 获取最后一个页码
                page_numbers = []
                for elem in page_elements:
                    text = elem.text.strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
                
                if page_numbers:
                    total_pages = max(page_numbers)
                    logger.info(f"总页数: {total_pages}")
                    
                    # 滚动回顶部
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(1)
                    
                    return total_pages
            
            return 1  # 至少有1页
            
        except Exception as e:
            logger.error(f"获取总页数时出错: {e}")
            return 1
    
    def select_all_items(self):
        """
        选中当前页面的所有项目
        
        Returns:
            bool: 是否成功选中
        """
        logger.info("正在全选当前页...")
        
        try:
            # 使用JavaScript点击全选框
            select_all_xpath = config.SELECTORS["select_all_xpath"]
            js_select_all = f"""
            const el = document.evaluate("{select_all_xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (el) {{
                el.click();
                return 'Select all clicked';
            }}
            return 'Select all not found';
            """
            
            result = self.driver.execute_script(js_select_all)
            logger.info(f"全选结果: {result}")
            
            if "not found" in result:
                # 尝试普通点击
                try:
                    el = self.wait.until(EC.element_to_be_clickable((By.XPATH, select_all_xpath)))
                    el.click()
                    logger.info("普通点击全选成功")
                except Exception as e:
                    logger.error(f"全选失败: {e}")
                    return False
            
            logger.info("成功全选当前页")
            time.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"全选时出错: {e}")
            return False
    
    def get_current_page_items(self):
        """
        获取当前页面的法律条目列表 (用于查新测试)
        
        Returns:
            list: 包含条目信息的字典列表
        """
        logger.info("正在提取当前页条目信息...")
        items = []
        try:
            # 等待列表加载
            # 这里的选择器需要根据实际页面结构确定，通常包含标题、发布日期等
            item_selector = "tbody tr" # 假设是表格结构
            # 实际上在中国法律服务网，列表项通常在特定的 table 里
            
            # 使用JS提取更稳定 (适配 flk.npc.gov.cn 的列表结构)
            js_extract = """
            const items = Array.from(document.querySelectorAll('.results-item, .list-file'));
            return items.map(el => {
               const titleEl = el.querySelector('.title, a.file-name');
               const dateEl = el.querySelector('.date, .time');
               if (!titleEl) return null;
               return {
                   title: titleEl.innerText.trim(),
                   publish_date: dateEl ? dateEl.innerText.trim() : 'Unknown',
                   id: el.getAttribute('data-id') || ''
               };
            }).filter(item => item !== null);
            """
            items = self.driver.execute_script(js_extract)
            logger.info(f"成功提取 {len(items)} 条信息")
            return items
        except Exception as e:
            logger.error(f"提取条目信息时出错: {e}")
            return []

    def batch_download(self):
        """
        执行批量下载
        
        Returns:
            bool: 是否成功触发下载
        """
        logger.info("正在执行批量下载...")
        
        try:
            # 使用JavaScript点击批量下载按钮
            download_xpath = config.SELECTORS["batch_download_xpath"]
            js_download = f"""
            const el = document.evaluate("{download_xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (el) {{
                el.click();
                return 'Download button clicked';
            }}
            return 'Download button not found';
            """
            
            result = self.driver.execute_script(js_download)
            logger.info(f"下载按钮点击结果: {result}")
            
            if "not found" in result:
                # 尝试普通点击
                try:
                    el = self.wait.until(EC.element_to_be_clickable((By.XPATH, download_xpath)))
                    el.click()
                    logger.info("普通点击下载按钮成功")
                except Exception as e:
                    logger.error(f"点击下载按钮失败: {e}")
                    return False
            
            logger.info("成功触发批量下载")
            
            # 等待下载开始
            time.sleep(config.DOWNLOAD_WAIT)
            return True
            
        except Exception as e:
            logger.error(f"批量下载时出错: {e}")
            return False
    
    def go_to_next_page(self):
        """
        跳转到下一页
        
        Returns:
            bool: 是否成功跳转
        """
        logger.info("正在跳转到下一页...")
        
        try:
            # 滚动到底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # 查找"下一页"按钮
            next_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, config.SELECTORS["next_page_button"]))
            )
            
            # 检查是否被禁用
            if "is-disabled" in next_button.get_attribute("class"):
                logger.info("已到达最后一页")
                return False
            
            next_button.click()
            logger.info("成功跳转到下一页")
            time.sleep(config.PAGE_LOAD_WAIT)
            
            # 滚动回顶部
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"跳转下一页时出错: {e}")
            return False
    
    def download_category(self, category_name, max_pages=None, status=None):
        """
        下载指定分类的所有法律文件
        
        Args:
            category_name: 分类名称
            max_pages: 最大下载页数（用于测试，None表示下载所有）
            status: 法律状态
        
        Returns:
            int: 成功下载的页数
        """
        logger.info(f"=" * 60)
        logger.info(f"开始下载分类: {category_name}" + (f" (状态: {status})" if status else ""))
        logger.info(f"=" * 60)
        
        # 导航到分类
        if not self.navigate_to_category(category_name):
            logger.error(f"无法导航到分类: {category_name}")
            return 0
            
        # 应用状态过滤
        if status and not self.apply_status_filter(status):
            logger.error(f"无法应用状态过滤: {status}")
            return 0
        
        # 设置每页100条
        if not self.set_items_per_page(config.ITEMS_PER_PAGE):
            logger.error(f"无法设置每页条目数")
            return 0
        
        # 获取总页数
        total_pages = self.get_total_pages()
        if max_pages:
            total_pages = min(total_pages, max_pages)
        
        logger.info(f"准备下载 {total_pages} 页")
        
        # 创建分类下载目录
        if status:
            category_dir = os.path.join(self.download_dir, category_name, status)
        else:
            category_dir = os.path.join(self.download_dir, category_name)
        os.makedirs(category_dir, exist_ok=True)
        
        # 更新浏览器下载目录
        self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(Path(category_dir).absolute())
        })
        
        successful_downloads = 0
        
        # 遍历每一页
        for page_num in range(1, total_pages + 1):
            logger.info(f"\n处理第 {page_num}/{total_pages} 页")
            
            retry_count = 0
            while retry_count < config.MAX_RETRIES:
                try:
                    # 全选当前页
                    if not self.select_all_items():
                        raise Exception("全选失败")
                    
                    # 批量下载
                    if not self.batch_download():
                        raise Exception("批量下载失败")
                    
                    successful_downloads += 1
                    logger.info(f"第 {page_num} 页下载成功")
                    break
                    
                except Exception as e:
                    retry_count += 1
                    logger.warning(f"第 {page_num} 页下载失败 (尝试 {retry_count}/{config.MAX_RETRIES}): {e}")
                    if retry_count < config.MAX_RETRIES:
                        time.sleep(config.RETRY_DELAY)
                    else:
                        logger.error(f"第 {page_num} 页下载失败，已达最大重试次数")
            
            # 如果不是最后一页，跳转到下一页
            if page_num < total_pages:
                if not self.go_to_next_page():
                    logger.warning("无法继续到下一页，提前结束")
                    break
        
        logger.info(f"\n{category_name} 下载完成: {successful_downloads}/{total_pages} 页成功")
        return successful_downloads
    
    def download_all_categories(self, max_pages=None, status=None):
        """
        下载所有分类 (包含各种状态)
        
        Args:
            max_pages: 每个分类的最大下载页数（None表示全量）
            status: 法律状态（None则遍历所有常见状态）
        """
        logger.info("开始全库深度同步流程...")
        
        # 如果未指定状态，则根据常见状态进行全量轮询
        target_statuses = [status] if status else [None, "有效", "已修改", "尚未生效", "已废止"]
        
        results = {}
        for category_name in config.CATEGORIES.keys():
            for s in target_statuses:
                try:
                    downloaded_pages = self.download_category(category_name, max_pages, s)
                    key = f"{category_name}({s if s else '全部'})"
                    results[key] = downloaded_pages
                except Exception as e:
                    logger.error(f"下载分类 {category_name} 状态 {s} 时出错: {e}")
        
        # 输出总结
        logger.info(f"\n" + "=" * 60)
        logger.info("下载总结:")
        logger.info("=" * 60)
        for category, count in results.items():
            logger.info(f"{category}: {count} 页")
        logger.info("=" * 60)
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            logger.info("正在关闭浏览器...")
            self.driver.quit()
            logger.info("浏览器已关闭")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='国家法律法规数据库批量下载工具')
    parser.add_argument('--category', type=str, help='指定下载的分类（法律、行政法规、地方性法规、司法解释）')
    parser.add_argument('--max-pages', type=int, help='每个分类最大下载页数（用于测试）')
    parser.add_argument('--headless', action='store_true', help='使用无头模式运行')
    parser.add_argument('--download-dir', type=str, default=config.DOWNLOAD_DIR, help='下载目录')
    
    parser.add_argument('--status', type=str, help='指定法律状态（有效、已修改、尚未生效、已废止）')
    
    args = parser.parse_args()
    
    downloader = LegalDatabaseDownloader(
        headless=args.headless,
        download_dir=args.download_dir
    )
    
    try:
        # 设置浏览器
        downloader.setup_driver()
        
        if args.category:
            # 下载指定分类
            if args.category in config.CATEGORIES:
                downloader.download_category(args.category, args.max_pages, args.status)
            else:
                logger.error(f"无效的分类名称: {args.category}")
                logger.info(f"有效的分类: {', '.join(config.CATEGORIES.keys())}")
        else:
            # 下载所有分类 (全库更新模式)
            downloader.download_all_categories(args.max_pages, args.status)
    
    except KeyboardInterrupt:
        logger.info("\n用户中断下载")
    except Exception as e:
        logger.error(f"运行出错: {e}", exc_info=True)
    finally:
        downloader.close()
        logger.info("程序结束")


if __name__ == "__main__":
    main()
