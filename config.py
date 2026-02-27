"""
配置文件 - 国家法律法规数据库批量下载工具
"""

# 网站配置
BASE_URL = "https://flk.npc.gov.cn"
HOMEPAGE_URL = f"{BASE_URL}/index"

# 法律分类配置
# 每个分类的名称和对应的索引位置（首页点击位置）
CATEGORIES = {
    "法律": {
        "name": "法律",
        "index": 0
    },
    "行政法规": {
        "name": "行政法规",
        "index": 1
    },
    "地方性法规": {
        "name": "地方性法规",
        "index": 2
    },
    "监察法规": {
        "name": "监察法规",
        "index": 3
    },
    "司法解释": {
        "name": "司法解释",
        "index": 4
    }
}

# 下载配置
DOWNLOAD_DIR = "downloads"  # 下载文件保存目录
ITEMS_PER_PAGE = 100  # 每页显示条目数

# 浏览器配置
HEADLESS = False  # 是否无头模式运行（True=不显示浏览器窗口）
WINDOW_SIZE = (1920, 1080)  # 浏览器窗口大小

# 等待配置
IMPLICIT_WAIT = 10  # 隐式等待时间（秒）
EXPLICIT_WAIT = 20  # 显式等待时间（秒）
DOWNLOAD_WAIT = 5  # 每次下载后等待时间（秒）
PAGE_LOAD_WAIT = 3  # 页面加载等待时间（秒）

# 重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）

# 法律状态配置
STATUS_MAPPING = {
    "有效": "3",
    "已修改": "2",
    "尚未生效": "4",
    "已废止": "1"
}

# UI元素选择器
SELECTORS = {
    # 状态过滤器 (时效性)
    "status_checkbox_xpath": "//label[contains(@class, 'el-checkbox')]//span[contains(., '{status_name}')]",
    "status_input_xpath": "//input[@class='el-checkbox__original' and @value='{status_value}']",

    # 页面大小选择器
    "page_size_selector": ".el-pagination .el-select__wrapper",
    "page_size_100_option_xpath": "//li[contains(@class, 'el-select-dropdown__item')]//span[contains(., '100')]",
    
    # 批量操作选择器
    "select_all_xpath": "//label[contains(@class, 'el-checkbox')]//span[contains(., '全选')]",
    "batch_download_xpath": "//button[contains(@class, 'el-button')]//span[contains(., '批量下载文件')]",
    
    # 分页选择器
    "pagination": ".el-pagination",
    "next_page_button": "button.btn-next",
    "prev_page_button": "button.btn-prev",
    "current_page": ".el-pager li.is-active",
    
    # 总数信息
    "total_count": "span.el-pagination__total"
}
